from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    is_baseline: bool
    retirement_age: int
    savings_rate: Decimal
    monthly_contribution: Decimal
    expected_return: Decimal
    inflation_rate: Decimal
    withdrawal_rate: Decimal
    created_at: datetime
    updated_at: datetime


class ScenarioCreateRequest(BaseModel):
    name: str
    description: str | None = None
    current_age: int
    retirement_age: int
    savings_rate: Decimal = Decimal("0.20")
    monthly_contribution: Decimal = Decimal("0")
    expected_return: Decimal = Decimal("0.065")
    inflation_rate: Decimal = Decimal("0.028")
    withdrawal_rate: Decimal = Decimal("0.04")
    is_baseline: bool = False


class ScenarioRunRequest(BaseModel):
    current_age: int
    current_retirement_balance: Decimal
    annual_spending_target: Decimal | None = None
    include_monte_carlo: bool = True
    monte_carlo_trials: int = 1000


class ScenarioRunResponse(BaseModel):
    id: UUID
    scenario_id: UUID
    engine_version: str
    method: str
    net_worth_at_target_age: Decimal
    success_rate: Decimal | None
    trajectory: list[dict]
    created_at: datetime


class ScenarioRunHistoryResponse(BaseModel):
    data: list[ScenarioRunResponse]


class ScenarioCompareRequest(BaseModel):
    scenario_ids: list[UUID]


class ScenarioCompareRow(BaseModel):
    scenario_id: UUID
    name: str
    net_worth_at_target_age: Decimal | None
    retirement_age: int
    monthly_contribution: Decimal
    success_rate: Decimal | None
    has_run: bool


class ScenarioCompareResponse(BaseModel):
    rows: list[ScenarioCompareRow]
