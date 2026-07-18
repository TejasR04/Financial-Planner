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


class CashFlowSimulationRequest(BaseModel):
    monthly_gross_income: Decimal
    monthly_expenses: Decimal
    months: int = 12
    income_growth_rate: Decimal = Decimal("0.03")
    inflation_rate: Decimal = Decimal("0.028")


class CashFlowMonthPointResponse(BaseModel):
    month_index: int
    income: Decimal
    expenses: Decimal
    net: Decimal


class CashFlowSimulationResponse(BaseModel):
    series: list[CashFlowMonthPointResponse]
    average_monthly_surplus: Decimal
    projected_savings_rate: Decimal


class MonteCarloSimulationRequest(BaseModel):
    current_age: int
    starting_balance: Decimal
    annual_contribution: Decimal
    years: int
    target_balance: Decimal
    expected_return: Decimal = Decimal("0.065")
    return_volatility: Decimal = Decimal("0.15")
    trials: int = 1000
    seed: int = 42


class MonteCarloSimulationResponse(BaseModel):
    trials: int
    success_rate: float
    median_ending_balance: Decimal
    p10_ending_balance: Decimal
    p90_ending_balance: Decimal
    seed: int


class DebtLiabilityInput(BaseModel):
    name: str
    principal: Decimal
    interest_rate: Decimal
    minimum_payment: Decimal
    term_months: int = 360


class DebtOptimizationRequest(BaseModel):
    liabilities: list[DebtLiabilityInput]
    extra_monthly_payment: Decimal
    strategy: str = "avalanche"


class DebtOptimizationResponse(BaseModel):
    strategy: str
    months_to_debt_free: int
    total_interest_paid: Decimal
    payoff_order: list[str]
