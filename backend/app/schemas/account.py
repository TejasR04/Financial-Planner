from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import AccountStatus, AccountType


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: AccountType
    balance: Decimal
    currency: Literal["USD"]
    mask: str | None
    apy: Decimal | None
    status: AccountStatus
    institution: str | None = None
    institution_id: UUID | None = None
    institution_status: str | None = None
    institution_last_synced_at: datetime | None = None
    updated_at: datetime | None = None


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
