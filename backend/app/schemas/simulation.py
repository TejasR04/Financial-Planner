from decimal import Decimal

from pydantic import BaseModel


class RetirementSimulationRequest(BaseModel):
    current_age: int
    retirement_age: int
    life_expectancy_age: int = 95
    current_retirement_balance: Decimal
    annual_contribution: Decimal
    expected_return: Decimal = Decimal("0.065")
    inflation_rate: Decimal = Decimal("0.028")
    withdrawal_rate: Decimal = Decimal("0.04")
    annual_spending_target: Decimal | None = None


class RetirementSimulationResponse(BaseModel):
    projected_balance_at_retirement: Decimal
    annual_sustainable_withdrawal: Decimal
    monthly_sustainable_withdrawal: Decimal
    is_feasible: bool
    shortfall_or_surplus: Decimal
    years_to_retirement: int


class NetWorthSimulationRequest(BaseModel):
    current_age: int
    retirement_age: int
    years: int
    expected_return: Decimal = Decimal("0.065")
    annual_net_contribution: Decimal = Decimal("0")


class NetWorthYearPointResponse(BaseModel):
    year_index: int
    age: int
    assets: Decimal
    liabilities: Decimal
    net: Decimal


class NetWorthSimulationResponse(BaseModel):
    net_worth_today: Decimal
    projected_net_worth_at_horizon: Decimal
    series: list[NetWorthYearPointResponse]


class ScenarioCompareRequest(BaseModel):
    scenario_ids: list[str]


class ScenarioMetricsResponse(BaseModel):
    scenario_id: str
    name: str
    net_worth_at_target_age: Decimal
    retirement_age: int
    monthly_contribution: Decimal
    success_rate: Decimal | None
