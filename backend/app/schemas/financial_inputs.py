from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import AssetClass


class IncomeSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    annual_amount: Decimal = Field(ge=0)
    growth_rate: Decimal = Field(default=Decimal("0.03"), ge=-1, le=1)
    active: bool = True


class IncomeSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    annual_amount: Decimal | None = Field(default=None, ge=0)
    growth_rate: Decimal | None = Field(default=None, ge=-1, le=1)
    active: bool | None = None


class IncomeSourceResponse(IncomeSourceCreate):
    id: UUID


class LiabilityDetails(BaseModel):
    principal: Decimal = Field(ge=0)
    interest_rate: Decimal = Field(ge=0, le=1)
    term_months: int = Field(gt=0, le=1200)
    minimum_payment: Decimal = Field(ge=0)
    origination_date: date


class LiabilityResponse(LiabilityDetails):
    id: UUID
    account_id: UUID


class HoldingInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    quantity: Decimal = Field(ge=0)
    cost_basis: Decimal = Field(ge=0)
    market_value: Decimal = Field(ge=0)
    asset_class: AssetClass
    as_of: date


class HoldingUpdate(BaseModel):
    symbol: str | None = Field(default=None, min_length=1, max_length=20)
    quantity: Decimal | None = Field(default=None, ge=0)
    cost_basis: Decimal | None = Field(default=None, ge=0)
    market_value: Decimal | None = Field(default=None, ge=0)
    asset_class: AssetClass | None = None
    as_of: date | None = None


class HoldingResponse(HoldingInput):
    id: UUID
    account_id: UUID
