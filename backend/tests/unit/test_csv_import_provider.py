from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.enums import TransactionType
from app.api.v1.routes.transactions import _normalized_import_rows
from app.persistence.repositories.transaction_repository import TransactionRepository, import_fingerprints
from app.schemas.transaction import CSVImportRequest, CSVImportRowOverride
from app.providers.csv_import_provider import CSVImportProvider


@pytest.mark.asyncio
async def test_import_accepts_tsv_and_case_insensitive_headers():
    text = (
        "date\tmerchant\tcategory\tAmount\n"
        "08/01/2026\tExternal transfer\tWithdrawal\t25.50\n"
        "08/02/2026\tInterest\tInterest payment\t$1.25\n"
        "08/03/2026\tEmployer\tMoney in\t1,234.56\n"
        "08/04/2026\tBank transfer\tDeposit\t(40.00)\n"
    )
    rows = await CSVImportProvider(uuid4(), text).get_transactions(uuid4(), date(1970, 1, 1))

    assert [row.amount for row in rows] == [
        Decimal("-25.50"), Decimal("1.25"), Decimal("1234.56"), Decimal("40.00")
    ]
    assert [row.type for row in rows] == [
        TransactionType.EXPENSE,
        TransactionType.INCOME,
        TransactionType.INCOME,
        TransactionType.INCOME,
    ]
    assert {row.category for row in rows} == {"uncategorized"}


@pytest.mark.asyncio
async def test_generic_transfer_is_uncategorized_and_excluded_from_cash_flow():
    text = "date,merchant,category,Amount\n08/01/2026,Internal move,Transfer,-50.00\n"
    rows = await CSVImportProvider(uuid4(), text).get_transactions(uuid4(), date(1970, 1, 1))
    assert rows[0].category == "uncategorized"
    assert rows[0].type == TransactionType.TRANSFER


@pytest.mark.asyncio
async def test_import_reports_the_bad_row_number():
    text = "date,merchant,category,Amount\n08/01/2026,Store,Withdrawal,not-money\n"
    with pytest.raises(ValueError, match="Row 2: Unrecognized amount"):
        await CSVImportProvider(uuid4(), text).get_transactions(uuid4(), date(1970, 1, 1))


@pytest.mark.asyncio
async def test_import_honors_an_explicit_type_column():
    text = "date,merchant,category,amount,type\n08/01/2026,Card payoff,Payment,50.00,credit_card_payment\n"
    rows = await CSVImportProvider(uuid4(), text).get_transactions(uuid4(), date(1970, 1, 1))
    assert rows[0].type == TransactionType.CREDIT_CARD_PAYMENT
    assert rows[0].amount == Decimal("50.00")


@pytest.mark.asyncio
async def test_explicit_expense_type_preserves_positive_refund_amount():
    text = "date,merchant,category,amount,type\n08/01/2026,Store,Returns,25.00,expense\n"
    rows = await CSVImportProvider(uuid4(), text).get_transactions(uuid4(), date(1970, 1, 1))
    assert rows[0].type == TransactionType.EXPENSE
    assert rows[0].amount == Decimal("25.00")


@pytest.mark.asyncio
async def test_explicit_expense_keeps_positive_debit_magnitude_convention():
    text = "date,merchant,category,amount,type\n08/01/2026,Store,Debit,25.00,expense\n"
    rows = await CSVImportProvider(uuid4(), text).get_transactions(uuid4(), date(1970, 1, 1))
    assert rows[0].type == TransactionType.EXPENSE
    assert rows[0].amount == Decimal("-25.00")


@pytest.mark.asyncio
async def test_preview_expense_override_preserves_positive_refund_amount():
    account_id = uuid4()
    body = CSVImportRequest(
        account_id=account_id,
        csv_text="date,merchant,category,amount\n08/01/2026,Store,Returns,25.00\n",
        overrides=[CSVImportRowOverride(row_number=2, type=TransactionType.EXPENSE, amount=Decimal("25.00"))],
    )
    rows = _normalized_import_rows(body)
    assert rows[0].transaction.type == TransactionType.EXPENSE
    assert rows[0].transaction.amount == Decimal("25.00")


@pytest.mark.asyncio
async def test_preview_signed_expense_override_beats_generic_debit_label():
    body = CSVImportRequest(
        account_id=uuid4(),
        csv_text="date,merchant,category,amount,type\n08/01/2026,Store,Debit,25.00,expense\n",
        overrides=[CSVImportRowOverride(row_number=2, type=TransactionType.EXPENSE, amount=Decimal("25.00"))],
    )
    rows = _normalized_import_rows(body)
    assert rows[0].transaction.amount == Decimal("25.00")


@pytest.mark.asyncio
async def test_csv_replay_identity_survives_inserted_rows_and_excluded_occurrences():
    account_id = uuid4()
    original = CSVImportRequest(
        account_id=account_id,
        csv_text="date,merchant,category,amount\n08/01/2026,Store,Shopping,-25.00\n",
    )
    shifted = CSVImportRequest(
        account_id=account_id,
        csv_text="date,merchant,category,amount\n08/02/2026,Cafe,Food,-4.00\n08/01/2026,Store,Shopping,-25.00\n",
    )
    original_row = _normalized_import_rows(original)[0]
    shifted_row = _normalized_import_rows(shifted)[1]
    assert original_row.row_number != shifted_row.row_number
    assert original_row.identity_number == shifted_row.identity_number == 1

    existing_fingerprint = import_fingerprints(
        [original_row.transaction], [original_row.identity_number]
    )[0]
    existing = SimpleNamespace(
        account_id=account_id,
        posted_at=original_row.transaction.posted_at,
        merchant=original_row.transaction.merchant,
        amount=original_row.transaction.amount,
        import_fingerprint=existing_fingerprint,
        deleted_at=None,
    )
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [existing]))
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    assert await TransactionRepository(session).import_duplicate_flags(
        [shifted_row.transaction], [shifted_row.identity_number]
    ) == [True]

    duplicate_text = (
        "date,merchant,category,amount\n"
        "08/01/2026,Store,Shopping,-25.00\n"
        "08/01/2026,Store,Shopping,-25.00\n"
    )
    excluded_body = CSVImportRequest(
        account_id=account_id,
        csv_text=duplicate_text,
        overrides=[CSVImportRowOverride(row_number=2, include=False)],
    )
    remaining = _normalized_import_rows(excluded_body)
    assert len(remaining) == 1
    assert remaining[0].identity_number == 2
    assert await TransactionRepository(session).import_duplicate_flags(
        [remaining[0].transaction], [int(remaining[0].identity_number)]
    ) == [False]


def test_preview_warns_when_type_is_inferred_from_amount():
    text = "date,merchant,category,amount\n08/01/2026,Corner Store,Shopping,-12.34\n"
    rows = CSVImportProvider(uuid4(), text).parse_rows(date(1970, 1, 1))
    assert rows[0].warnings == ["Type was inferred from the amount sign; review before importing."]


@pytest.mark.asyncio
async def test_import_rejects_zero_amount_and_blank_merchant():
    with pytest.raises(ValueError, match="Merchant is required"):
        await CSVImportProvider(uuid4(), "date,merchant,category,amount\n08/01/2026,,Other,-1\n").get_transactions(uuid4(), date(1970, 1, 1))
    with pytest.raises(ValueError, match="Amount cannot be zero"):
        await CSVImportProvider(uuid4(), "date,merchant,category,amount\n08/01/2026,Store,Other,0\n").get_transactions(uuid4(), date(1970, 1, 1))


@pytest.mark.asyncio
async def test_bank_credit_and_debit_labels_do_not_become_categories():
    text = (
        "category,date,Merchant,Amount,Type,Balance,Check or Slip #\n"
        "CREDIT,8/10/2026,ZELLE PAYMENT FROM JULIA YOON 30349766605,160,QUICKPAY_CREDIT,,\n"
        "DEBIT,8/11/2026,CARD PURCHASE,-25,DEBIT_CARD,,\n"
    )

    parsed = CSVImportProvider(uuid4(), text).parse_rows(date(1970, 1, 1))

    assert [row.transaction.category for row in parsed] == ["uncategorized", "uncategorized"]
    assert [row.transaction.type for row in parsed] == [TransactionType.INCOME, TransactionType.EXPENSE]
    assert [row.transaction.amount for row in parsed] == [Decimal("160"), Decimal("-25")]
    assert "Bank type 'QUICKPAY_CREDIT'" in parsed[0].warnings[0]
