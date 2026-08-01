from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from uuid import UUID


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


class CashFlowSimulationRequest(BaseModel):
    months: int = Field(default=12, ge=1, le=60)
    income_basis: Literal["gross", "take_home"] = "take_home"
    estimated_effective_tax_rate: Decimal | None = Field(default=None, ge=0, lt=1)


class CashFlowMonthPointResponse(BaseModel):
    month_index: int
    income: Decimal
    expenses: Decimal
    net: Decimal


class CashFlowSimulationResponse(BaseModel):
    series: list[CashFlowMonthPointResponse]
    average_monthly_surplus: Decimal
    projected_savings_rate: Decimal
    income_source: str
    expense_source: str
    income_basis: Literal["gross", "take_home"]


class MonteCarloSimulationRequest(BaseModel):
    current_age: int = Field(ge=18, le=100)
    starting_balance: Decimal = Field(ge=0, le=Decimal("1000000000"))
    annual_contribution: Decimal = Field(ge=0, le=Decimal("10000000"))
    years: int = Field(ge=1, le=100)
    target_balance: Decimal = Field(ge=0, le=Decimal("10000000000"))
    expected_return: Decimal = Field(default=Decimal("0.065"), ge=Decimal("-0.50"), le=Decimal("0.50"))
    # See app/simulation/engine.py:implied_return_volatility — matches the
    # calibrated 60/40-portfolio default used elsewhere in the app.
    return_volatility: Decimal = Field(default=Decimal("0.106"), ge=0, le=1)
    trials: int = Field(default=1000, ge=100, le=100000)
    seed: int = 42
    annual_fee_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)


class MonteCarloSimulationResponse(BaseModel):
    trials: int
    success_rate: float
    median_ending_balance: Decimal
    p10_ending_balance: Decimal
    p90_ending_balance: Decimal
    seed: int
    success_metric: str
    model_version: str
    percentile_method: str
    estimate_disclosure: str
    exclusions: list[str]


class DebtOptimizationRequest(BaseModel):
    account_ids: list[UUID] = Field(min_length=1)
    extra_monthly_payment: Decimal = Field(ge=0)
    strategy: str = "avalanche"


class DebtOptimizationResponse(BaseModel):
    strategy: str
    months_to_debt_free: int
    total_interest_paid: Decimal
    payoff_order: list[str]
    paid_off: bool
    warning: str | None = None
