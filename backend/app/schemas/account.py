from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import AccountStatus, AccountType


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: AccountType
    balance: Decimal
    reported_cash_balance: Decimal | None = None
    reported_cash_is_liquid: bool = False
    currency: Literal["USD"]
    mask: str | None
    apy: Decimal | None
    status: AccountStatus
    institution: str | None = None
    institution_id: UUID | None = None
    institution_status: str | None = None
    institution_last_synced_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None


class AccountCreateRequest(BaseModel):
    name: str
    type: AccountType
    balance: Decimal
    currency: Literal["USD"] = "USD"
    mask: str | None = None
    apy: Decimal | None = None


class AccountUpdateRequest(BaseModel):
    name: str | None = None
    balance: Decimal | None = None
    mask: str | None = None
    apy: Decimal | None = None


class AccountRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def name_cannot_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Account name cannot be blank.")
        return normalized


class ReportedCashUpdateRequest(BaseModel):
    balance: Decimal | None = Field(default=None, ge=0)
    is_liquid: bool = False


class InstitutionResponse(BaseModel):
    id: UUID
    name: str
    provider: str
    status: str
    last_synced_at: datetime | None = None
    account_count: int


class AccountListResponse(BaseModel):
    data: list[AccountResponse]
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal


class DisconnectedDataSummary(BaseModel):
    account_count: int
    transaction_count: int


class DisconnectedDataDeleteResponse(DisconnectedDataSummary):
    deleted: bool = True
