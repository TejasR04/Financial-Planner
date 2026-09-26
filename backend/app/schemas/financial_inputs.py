from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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
    principal: Decimal | None = Field(default=None, ge=0)
    interest_rate: Decimal | None = Field(default=None, ge=0, le=1)
    term_months: int | None = Field(default=None, gt=0, le=1200)
    minimum_payment: Decimal | None = Field(default=None, ge=0)
    origination_date: date | None = None


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
    pricing_mode: Literal["manual", "automatic"] = "manual"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must contain a non-whitespace character")
        return normalized


class HoldingUpdate(BaseModel):
    symbol: str | None = Field(default=None, min_length=1, max_length=20)
    quantity: Decimal | None = Field(default=None, ge=0)
    cost_basis: Decimal | None = Field(default=None, ge=0)
    market_value: Decimal | None = Field(default=None, ge=0)
    asset_class: AssetClass | None = None
    as_of: date | None = None
    pricing_mode: Literal["manual", "automatic"] | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must contain a non-whitespace character")
        return normalized


class HoldingResponse(HoldingInput):
    id: UUID
    account_id: UUID
    last_price: Decimal | None = None
