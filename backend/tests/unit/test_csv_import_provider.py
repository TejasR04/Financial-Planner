from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.enums import TransactionType
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
