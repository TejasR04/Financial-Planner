from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities import Account, Holding, Transaction
from app.domain.enums import TransactionStatus, TransactionType
from app.providers.base import FinancialDataProvider

EXPECTED_COLUMNS = {"date", "merchant", "category", "amount"}


class CSVImportProvider(FinancialDataProvider):
    """Parses a user-uploaded CSV of transactions into normalized
    `Transaction` objects. Does not provide accounts or holdings — CSV
    import is always attached to an existing account chosen by the user in
    `POST /transactions/import/csv`.
    """

    def __init__(self, account_id: UUID, csv_text: str):
        self.account_id = account_id
        self.csv_text = csv_text

    async def get_accounts(self, user_id: UUID) -> list[Account]:
        raise NotImplementedError("CSVImportProvider only normalizes transactions")

    async def get_holdings(self, user_id: UUID, account_id: UUID) -> list[Holding]:
        raise NotImplementedError("CSVImportProvider only normalizes transactions")

    async def get_transactions(self, user_id: UUID, since: date) -> list[Transaction]:
        reader = csv.DictReader(io.StringIO(self.csv_text))
        header = {h.strip().lower() for h in (reader.fieldnames or [])}
        missing = EXPECTED_COLUMNS - header
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        transactions: list[Transaction] = []
        for row in reader:
            posted_at = _parse_date(row["date"])
            if posted_at < since:
                continue
            amount = Decimal(row["amount"])
            transactions.append(
                Transaction(
                    id=uuid4(),
                    account_id=self.account_id,
                    posted_at=posted_at,
                    merchant=row["merchant"].strip(),
                    category=row["category"].strip(),
                    amount=amount,
                    type=TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE,
                    status=TransactionStatus.CLEARED,
                )
            )
        return transactions


def _parse_date(raw: str) -> date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {raw!r}")
