from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class InvestmentAccountResponse(BaseModel):
    id: UUID
    name: str
    type: str
    balance: Decimal
    institution: str | None = None
    updated_at: date | None = None


class InvestmentHoldingResponse(BaseModel):
    account_id: UUID
    account_name: str
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    market_value: Decimal
    gain_loss: Decimal
    asset_class: str
    as_of: date


class InvestmentAllocationResponse(BaseModel):
    asset_class: str
    market_value: Decimal
    weight: Decimal


class InvestmentValuePointResponse(BaseModel):
    date: date
    value: Decimal


class InvestmentDashboardResponse(BaseModel):
    total_value: Decimal
    total_holdings_value: Decimal
    total_cost_basis: Decimal
    total_gain_loss: Decimal
    account_count: int
    holding_count: int
    accounts: list[InvestmentAccountResponse]
    holdings: list[InvestmentHoldingResponse]
    allocation: list[InvestmentAllocationResponse]
    history: list[InvestmentValuePointResponse]
