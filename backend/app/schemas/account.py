from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import AccountStatus, AccountType


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: AccountType
    balance: Decimal
    currency: str
    mask: str | None
    apy: Decimal | None
    status: AccountStatus
    institution: str | None = None
    updated_at: datetime | None = None


class AccountCreateRequest(BaseModel):
    name: str
    type: AccountType
    balance: Decimal
    currency: str = "USD"
    mask: str | None = None
    apy: Decimal | None = None


class AccountListResponse(BaseModel):
    data: list[AccountResponse]
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
