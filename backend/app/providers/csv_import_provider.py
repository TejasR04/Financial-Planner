from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from app.domain.entities import Account, Holding, Transaction
from app.domain.enums import TransactionStatus, TransactionType
from app.providers.base import FinancialDataProvider

EXPECTED_COLUMNS = {"date", "merchant", "category", "amount"}
GENERIC_FLOW_CATEGORIES = {"withdrawal", "money in", "interest payment", "deposit", "transfer"}


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
        csv_text = self.csv_text.lstrip("\ufeff")
        try:
            dialect = csv.Sniffer().sniff(csv_text[:4096], delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)
        header = {h.strip().lower() for h in (reader.fieldnames or [])}
        missing = EXPECTED_COLUMNS - header
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        transactions: list[Transaction] = []
        for line_number, raw_row in enumerate(reader, start=2):
            row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw_row.items()}
            if not any(row.values()):
                continue
            try:
                posted_at = _parse_date(row["date"])
                amount = _parse_amount(row["amount"])
            except (ValueError, KeyError) as exc:
                raise ValueError(f"Row {line_number}: {exc}") from exc
            if posted_at < since:
                continue
            category = row["category"]
            normalized_category = " ".join(category.lower().replace("_", " ").split())
            if normalized_category == "withdrawal":
                amount = -abs(amount)
            elif normalized_category in {"money in", "interest payment", "deposit"}:
                amount = abs(amount)
            transaction_type = (
                TransactionType.TRANSFER
                if normalized_category == "transfer"
                else TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE
            )
            transactions.append(
                Transaction(
                    id=uuid4(),
                    account_id=self.account_id,
                    posted_at=posted_at,
                    merchant=row["merchant"],
                    category="uncategorized" if normalized_category in GENERIC_FLOW_CATEGORIES else category,
                    amount=amount,
                    type=transaction_type,
                    status=TransactionStatus.CLEARED,
                )
            )
        return transactions


def _parse_date(raw: str) -> date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {raw!r}")


def _parse_amount(raw: str) -> Decimal:
    value = raw.strip().replace("$", "").replace(",", "").replace("−", "-")
    if value.startswith("(") and value.endswith(")"):
        value = f"-{value[1:-1]}"
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Unrecognized amount: {raw!r}") from exc
