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
    project_balance_series_monthly_contributions,
    project_retirement_withdrawal_series,
    safe_withdrawal_amount,
)

ZERO = Decimal("0")


@dataclass(slots=True, frozen=True)
class RetirementProjection:
    assumptions: PlanningAssumptions
    accumulation_series: list[YearProjection]
    decumulation_series: list[YearProjection]
    projected_balance_at_retirement: Decimal
    annual_sustainable_withdrawal: Decimal
    monthly_sustainable_withdrawal: Decimal
    years_of_income_at_withdrawal_rate: int | None
    is_feasible: bool
    shortfall_or_surplus: Decimal  # positive = surplus vs. a simple spending target, if provided
    # Populated only when the user sets an income target. Every number in
    # this model is in today's purchasing-power dollars.
    target_annual_income_real: Decimal | None = None
    target_monthly_income_real: Decimal | None = None


class RetirementProjectionService:
    """Projects retirement finances entirely in today's purchasing power.

    ``PlanningAssumptions.expected_return`` is nominal, so this service uses
    its Fisher-adjusted real return. Balances, contributions, income targets,
    withdrawals, and every amount returned by this service therefore share
    one dollar basis.
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

        series = project_balance_series_monthly_contributions(
            starting_balance=current_retirement_balance,
            annual_contribution=annual_contribution,
            annual_rate=assumptions.real_return,
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

        # The model is entirely real-dollar based. An explicit annual target
        # is already a today's-dollars value; otherwise use the scenario's
        # monthly today-dollar income goal without inflating it.
        effective_spending_target = annual_spending_target
        target_annual_income_real: Decimal | None = None
        target_monthly_income_real: Decimal | None = None
        if effective_spending_target is None and assumptions.desired_monthly_income_today is not None:
            effective_spending_target = assumptions.desired_monthly_income_today * 12

        if assumptions.desired_monthly_income_today is not None:
            target_annual_income_real = (assumptions.desired_monthly_income_today * 12).quantize(Decimal("0.01"))
            target_monthly_income_real = assumptions.desired_monthly_income_today.quantize(Decimal("0.01"))

        years_of_income = None
        if effective_spending_target and effective_spending_target > ZERO:
            years_of_income = int(balance_at_retirement // effective_spending_target)

        shortfall_or_surplus = ZERO
        if effective_spending_target is not None:
            shortfall_or_surplus = annual_withdrawal - effective_spending_target

        retirement_withdrawal = (
            effective_spending_target
            if effective_spending_target is not None
            else annual_withdrawal
        )
        decumulation_series = project_retirement_withdrawal_series(
            starting_balance=balance_at_retirement,
            annual_withdrawal=retirement_withdrawal,
            annual_rate=assumptions.real_return,
            years=assumptions.years_in_retirement,
            starting_age=assumptions.retirement_age,
            withdrawal_growth_rate=ZERO,
        )

        # Feasibility means the requested real withdrawal is paid in full in
        # every retirement year, not merely that the first-year 4% amount
        # covers the target. Exact exhaustion after the final requested
        # withdrawal still counts as funded through the chosen horizon.
        is_feasible = all(
            -row.contributions == retirement_withdrawal
            for row in decumulation_series
        )

        return RetirementProjection(
            assumptions=assumptions,
            accumulation_series=series,
            decumulation_series=decumulation_series,
            projected_balance_at_retirement=balance_at_retirement,
            annual_sustainable_withdrawal=annual_withdrawal,
            monthly_sustainable_withdrawal=monthly_withdrawal,
            years_of_income_at_withdrawal_rate=years_of_income,
            is_feasible=is_feasible,
            shortfall_or_surplus=shortfall_or_surplus,
            target_annual_income_real=target_annual_income_real,
            target_monthly_income_real=target_monthly_income_real,
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
