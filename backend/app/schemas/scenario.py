from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    desired_monthly_income_today: Decimal | None
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
    # Monthly retirement income target in TODAY's dollars. If set, this
    # replaces withdrawal_rate as what drives feasibility + Monte Carlo.
    desired_monthly_income_today: Decimal | None = None
    is_baseline: bool = False


class ScenarioUpdateRequest(BaseModel):
    """All fields optional — only what's provided gets updated. Note
    `current_age` deliberately isn't here: it's not stored on Scenario (see
    the duplicate-scenario route note), it's supplied fresh on each /run."""

    name: str | None = None
    description: str | None = None
    retirement_age: int | None = None
    savings_rate: Decimal | None = None
    monthly_contribution: Decimal | None = None
    expected_return: Decimal | None = None
    inflation_rate: Decimal | None = None
    withdrawal_rate: Decimal | None = None
    desired_monthly_income_today: Decimal | None = None
    # Explicit flag to CLEAR desired_monthly_income_today and go back to
    # rate-based mode — needed because ScenarioRepository.update_for_user() skips
    # any field that's None, so passing desired_monthly_income_today=None
    # alone can't distinguish "don't touch it" from "clear it".
    clear_income_target: bool = False


class ScenarioRunRequest(BaseModel):
    current_age: int = Field(ge=18, le=100)
    current_retirement_balance: Decimal = Field(ge=0, le=Decimal("1000000000"))
    annual_spending_target: Decimal | None = Field(default=None, ge=0, le=Decimal("100000000"))
    include_monte_carlo: bool = True
    monte_carlo_trials: int = Field(default=1000, ge=100, le=100000)


class ScenarioRunResponse(BaseModel):
    id: UUID
    scenario_id: UUID
    engine_version: str
    method: str
    net_worth_at_target_age: Decimal
    monthly_sustainable_withdrawal: Decimal | None
    success_rate: Decimal | None
    trajectory: list[dict]
    retirement_trajectory: list[dict] | None = None
    created_at: datetime
    assumptions_snapshot: dict | None = None


class ScenarioRunHistoryResponse(BaseModel):
    data: list[ScenarioRunResponse]


class ScenarioPreviewResponse(BaseModel):
    """An on-demand scenario result. Unlike ScenarioRunResponse, it is not
    persisted, so the projections page can always reflect current balances
    and assumptions without a manual "run" action or run-history noise.
    """

    net_worth_at_target_age: Decimal
    monthly_sustainable_withdrawal: Decimal | None
    success_rate: Decimal | None
    trajectory: list[dict]
    retirement_trajectory: list[dict]
    model_metadata: dict | None = None


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


class ScenarioSensitivityRequest(BaseModel):
    current_age: int
    current_retirement_balance: Decimal


class SensitivityRowResponse(BaseModel):
    label: str
    kind: str
    value: Decimal
    note: str


class ScenarioSensitivityResponse(BaseModel):
    baseline_balance_at_retirement: Decimal
    baseline_success_rate: Decimal | None
    rows: list[SensitivityRowResponse]
