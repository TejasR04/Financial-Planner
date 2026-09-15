from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import TransactionStatus, TransactionType


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    posted_at: date
    merchant: str
    category: str
    amount: Decimal
    type: TransactionType
    status: TransactionStatus
    budget_category_id: UUID | None = None
    budget_category_name: str | None = None
    ignored_from_budget: bool = False
    account_name: str | None = None
    account_archived: bool = False


class TransactionListResponse(BaseModel):
    data: list[TransactionResponse]
    total: int
    limit: int
    offset: int
    totals: dict[str, Decimal] | None = None


class TransactionCreateRequest(BaseModel):
    account_id: UUID
    posted_at: date
    merchant: str
    category: str
    amount: Decimal
    type: TransactionType
    status: TransactionStatus = TransactionStatus.CLEARED


class TransactionUpdateRequest(BaseModel):
    posted_at: date | None = None
    merchant: str | None = None
    category: str | None = None
    amount: Decimal | None = None
    type: TransactionType | None = None


class TransactionClassificationRequest(BaseModel):
    type: TransactionType


class CSVImportRowOverride(BaseModel):
    row_number: int = Field(ge=2)
    include: bool = True
    posted_at: date | None = None
    merchant: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    amount: Decimal | None = None
    type: TransactionType | None = None


class CSVImportRequest(BaseModel):
    account_id: UUID
    csv_text: str = Field(min_length=1, max_length=5_000_000)
    since: date | None = None
    overrides: list[CSVImportRowOverride] = Field(default_factory=list, max_length=10_000)


class CSVImportPreviewRow(BaseModel):
    row_number: int
    posted_at: date
    merchant: str
    category: str
    amount: Decimal
    type: TransactionType
    likely_duplicate: bool
    warnings: list[str] = Field(default_factory=list)


class CSVImportPreviewResponse(BaseModel):
    rows: list[CSVImportPreviewRow]
    importable_count: int
    duplicate_count: int


class CSVImportResponse(BaseModel):
    imported_count: int
    skipped_duplicate_count: int = 0
    data: list[TransactionResponse]
