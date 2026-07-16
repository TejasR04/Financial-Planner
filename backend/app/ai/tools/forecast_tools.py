"""Forecast tools. Each function does exactly three things: validate typed
input (handled by the registry before the handler runs), call one service,
return the service's typed result. No arithmetic lives here.
"""
from decimal import Decimal

from pydantic import BaseModel

from app.ai.tool_registry import registry
from app.domain.entities import IncomeSource
from app.services.cash_flow_projection_service import CashFlowProjectionService
from app.services.net_worth_projection_service import NetWorthProjectionService
from app.services.retirement_projection_service import RetirementProjectionService
from app.simulation.assumptions import PlanningAssumptions

_retirement_service = RetirementProjectionService()
_net_worth_service = NetWorthProjectionService()
_cash_flow_service = CashFlowProjectionService()


class ForecastRetirementInput(BaseModel):
    current_age: int
    retirement_age: int
    current_retirement_balance: Decimal
    annual_contribution: Decimal
    expected_return: Decimal = Decimal("0.065")
    withdrawal_rate: Decimal = Decimal("0.04")
    annual_spending_target: Decimal | None = None


@registry.register(
    "forecast_retirement",
    "Project retirement account balance forward and evaluate whether the "
    "target retirement age is financially feasible under a fixed "
    "withdrawal-rate rule.",
    ForecastRetirementInput,
)
def forecast_retirement(args: ForecastRetirementInput):
    assumptions = PlanningAssumptions(
        current_age=args.current_age,
        retirement_age=args.retirement_age,
        expected_return=args.expected_return,
        withdrawal_rate=args.withdrawal_rate,
    )
    return _retirement_service.project(
        current_retirement_balance=args.current_retirement_balance,
        annual_contribution=args.annual_contribution,
        assumptions=assumptions,
        annual_spending_target=args.annual_spending_target,
    )


class EarliestRetirementAgeInput(BaseModel):
    current_age: int
    current_retirement_balance: Decimal
    annual_contribution: Decimal
    annual_spending_target: Decimal
    expected_return: Decimal = Decimal("0.065")
    withdrawal_rate: Decimal = Decimal("0.04")
    search_to_age: int = 75


@registry.register(
    "find_earliest_retirement_age",
    "Find the earliest age at which retirement is financially feasible "
    "given current savings, contributions, and spending needs. Use this "
    "for questions like 'can I retire at 58'.",
    EarliestRetirementAgeInput,
)
def find_earliest_retirement_age(args: EarliestRetirementAgeInput):
    base_assumptions = PlanningAssumptions(
        current_age=args.current_age,
        retirement_age=args.current_age + 1,
        expected_return=args.expected_return,
        withdrawal_rate=args.withdrawal_rate,
    )
    age = _retirement_service.earliest_feasible_retirement_age(
        current_retirement_balance=args.current_retirement_balance,
        annual_contribution=args.annual_contribution,
        base_assumptions=base_assumptions,
        annual_spending_target=args.annual_spending_target,
        search_to_age=args.search_to_age,
    )
    return {"earliest_feasible_retirement_age": age}


class ForecastCashFlowInput(BaseModel):
    monthly_gross_income: Decimal
    monthly_expenses: Decimal
    months: int = 12
    income_growth_rate: Decimal = Decimal("0.03")
    inflation_rate: Decimal = Decimal("0.028")


@registry.register(
    "forecast_cash_flow",
    "Project monthly income vs. expenses forward, accounting for income "
    "growth and inflation on expenses.",
    ForecastCashFlowInput,
)
def forecast_cash_flow(args: ForecastCashFlowInput):
    from uuid import uuid4

    income_sources = [
        IncomeSource(
            id=uuid4(),
            user_id=uuid4(),
            name="Primary income",
            annual_amount=args.monthly_gross_income * 12,
            growth_rate=args.income_growth_rate,
        )
    ]
    return _cash_flow_service.project(
        income_sources=income_sources,
        monthly_expenses=args.monthly_expenses,
        months=args.months,
        inflation_rate=args.inflation_rate,
    )
