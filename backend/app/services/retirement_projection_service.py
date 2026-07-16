"""RetirementProjectionService — the service behind `forecast_retirement`
(AI tool), `POST /simulations/retirement`, and `POST /scenarios/{id}/run`.

Pure Python. No FastAPI, no SQLAlchemy, no I/O. Takes domain objects and
assumptions, returns a typed result.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.simulation.assumptions import PlanningAssumptions
from app.simulation.engine import (
    YearProjection,
    project_balance_series,
    safe_withdrawal_amount,
)

ZERO = Decimal("0")


@dataclass(slots=True, frozen=True)
class RetirementProjection:
    assumptions: PlanningAssumptions
    accumulation_series: list[YearProjection]
    projected_balance_at_retirement: Decimal
    annual_sustainable_withdrawal: Decimal
    monthly_sustainable_withdrawal: Decimal
    years_of_income_at_withdrawal_rate: int | None
    is_feasible: bool
    shortfall_or_surplus: Decimal  # positive = surplus vs. a simple spending target, if provided


class RetirementProjectionService:
    """Projects retirement account balances forward and evaluates whether a
    target retirement age is feasible under a fixed withdrawal-rate rule.
    """

    def project(
        self,
        current_retirement_balance: Decimal,
        annual_contribution: Decimal,
        assumptions: PlanningAssumptions,
        contribution_growth_rate: Decimal = ZERO,
        annual_spending_target: Decimal | None = None,
    ) -> RetirementProjection:
        current_age = assumptions.current_age
        years = assumptions.years_to_retirement

        series = project_balance_series(
            starting_balance=current_retirement_balance,
            annual_contribution=annual_contribution,
            annual_rate=assumptions.expected_return,
            years=years,
            starting_age=current_age,
            contribution_growth_rate=contribution_growth_rate,
        )

        balance_at_retirement = (
            series[-1].ending_balance if series else current_retirement_balance
        ).quantize(Decimal("0.01"))
        annual_withdrawal = safe_withdrawal_amount(balance_at_retirement, assumptions.withdrawal_rate).quantize(
            Decimal("0.01")
        )
        monthly_withdrawal = (annual_withdrawal / Decimal(12)).quantize(Decimal("0.01"))

        years_of_income = None
        if annual_spending_target and annual_spending_target > ZERO:
            years_of_income = int(balance_at_retirement // annual_spending_target)

        shortfall_or_surplus = ZERO
        is_feasible = True
        if annual_spending_target is not None:
            shortfall_or_surplus = annual_withdrawal - annual_spending_target
            is_feasible = shortfall_or_surplus >= ZERO

        return RetirementProjection(
            assumptions=assumptions,
            accumulation_series=series,
            projected_balance_at_retirement=balance_at_retirement,
            annual_sustainable_withdrawal=annual_withdrawal,
            monthly_sustainable_withdrawal=monthly_withdrawal,
            years_of_income_at_withdrawal_rate=years_of_income,
            is_feasible=is_feasible,
            shortfall_or_surplus=shortfall_or_surplus,
        )

    def earliest_feasible_retirement_age(
        self,
        current_retirement_balance: Decimal,
        annual_contribution: Decimal,
        base_assumptions: PlanningAssumptions,
        annual_spending_target: Decimal,
        contribution_growth_rate: Decimal = ZERO,
        search_from_age: int | None = None,
        search_to_age: int = 75,
    ) -> int | None:
        """Answers "what's the earliest age I can retire?" by scanning ages
        upward and returning the first one where the withdrawal rule covers
        the spending target. Backs the agent workflow example in the spec
        ("Can I retire at 58 if...")."""
        start = search_from_age or (base_assumptions.current_age + 1)
        for candidate_age in range(start, search_to_age + 1):
            trial_assumptions = PlanningAssumptions(
                current_age=base_assumptions.current_age,
                retirement_age=candidate_age,
                life_expectancy_age=base_assumptions.life_expectancy_age,
                savings_rate=base_assumptions.savings_rate,
                monthly_contribution=base_assumptions.monthly_contribution,
                expected_return=base_assumptions.expected_return,
                inflation_rate=base_assumptions.inflation_rate,
                withdrawal_rate=base_assumptions.withdrawal_rate,
                employer_match_rate=base_assumptions.employer_match_rate,
                employer_match_cap=base_assumptions.employer_match_cap,
            )
            result = self.project(
                current_retirement_balance=current_retirement_balance,
                annual_contribution=annual_contribution,
                assumptions=trial_assumptions,
                contribution_growth_rate=contribution_growth_rate,
                annual_spending_target=annual_spending_target,
            )
            if result.is_feasible:
                return candidate_age
        return None
