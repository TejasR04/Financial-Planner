from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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


class TransactionListResponse(BaseModel):
    data: list[TransactionResponse]
    total: int
    limit: int
    offset: int


class TransactionCreateRequest(BaseModel):
    account_id: UUID
    posted_at: date
    merchant: str
    category: str
    amount: Decimal
    type: TransactionType
    status: TransactionStatus = TransactionStatus.CLEARED


class TransactionUpdateRequest(BaseModel):
    category: str


class CSVImportRequest(BaseModel):
    account_id: UUID
    csv_text: str
    since: date | None = None


class CSVImportResponse(BaseModel):
    imported_count: int
    data: list[TransactionResponse]
