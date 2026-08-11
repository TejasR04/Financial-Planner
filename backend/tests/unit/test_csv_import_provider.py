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
