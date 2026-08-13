from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from app.domain.entities import Account, Holding, Transaction
from app.domain.enums import TransactionStatus, TransactionType
from app.providers.base import FinancialDataProvider

EXPECTED_COLUMNS = {"date", "merchant", "category", "amount"}
GENERIC_FLOW_CATEGORIES = {
    "credit", "debit", "withdrawal", "money in", "interest payment", "deposit", "transfer"
}
SUPPORTED_EXPLICIT_TYPES = {transaction_type.value for transaction_type in TransactionType}
MAX_IMPORT_ROWS = 10_000


@dataclass(slots=True)
class ParsedCSVRow:
    row_number: int
    transaction: Transaction
    warnings: list[str]


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
        return [row.transaction for row in self.parse_rows(since)]

    def parse_rows(self, since: date) -> list[ParsedCSVRow]:
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

        transactions: list[ParsedCSVRow] = []
        for line_number, raw_row in enumerate(reader, start=2):
            if line_number > MAX_IMPORT_ROWS + 1:
                raise ValueError(f"CSV contains more than {MAX_IMPORT_ROWS:,} data rows. Split it into smaller files.")
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
            merchant = row["merchant"].strip()
            if not merchant:
                raise ValueError(f"Row {line_number}: Merchant is required")
            if len(merchant) > 255:
                raise ValueError(f"Row {line_number}: Merchant must be 255 characters or fewer")
            category = row["category"]
            if len(category) > 100:
                raise ValueError(f"Row {line_number}: Category must be 100 characters or fewer")
            normalized_category = " ".join(category.lower().replace("_", " ").split())
            warnings: list[str] = []
            if normalized_category in {"withdrawal", "debit"}:
                amount = -abs(amount)
            elif normalized_category in {"credit", "money in", "interest payment", "deposit"}:
                amount = abs(amount)
            if amount == 0:
                raise ValueError(f"Row {line_number}: Amount cannot be zero")
            explicit_type = row.get("type", "").strip().lower().replace(" ", "_")
            if explicit_type in SUPPORTED_EXPLICIT_TYPES:
                try:
                    transaction_type = TransactionType(explicit_type)
                except ValueError as exc:
                    raise ValueError(f"Row {line_number}: Unrecognized type: {row.get('type')!r}") from exc
                expected_positive = transaction_type in {TransactionType.INCOME, TransactionType.CONTRIBUTION}
                amount = abs(amount) if expected_positive else -abs(amount) if transaction_type == TransactionType.EXPENSE else amount
            elif normalized_category == "transfer":
                transaction_type = TransactionType.TRANSFER
            elif "credit card payment" in normalized_category:
                transaction_type = TransactionType.CREDIT_CARD_PAYMENT
            else:
                transaction_type = TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE
                if normalized_category not in GENERIC_FLOW_CATEGORIES:
                    warnings.append("Type was inferred from the amount sign; review before importing.")
                if explicit_type:
                    warnings.append(f"Bank type {row.get('type')!r} was treated as source metadata and not used as an app category.")
            transactions.append(
                ParsedCSVRow(
                    row_number=line_number,
                    warnings=warnings,
                    transaction=Transaction(
                        id=uuid4(),
                        account_id=self.account_id,
                        posted_at=posted_at,
                        merchant=merchant,
                        category="uncategorized" if normalized_category in GENERIC_FLOW_CATEGORIES else (category or "uncategorized"),
                        amount=amount,
                        type=transaction_type,
                        status=TransactionStatus.CLEARED,
                    ),
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
