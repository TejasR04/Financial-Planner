"""The single input contract for every projection in the simulation engine.

Both the REST API (ad-hoc `/simulations/*` calls) and a saved `Scenario`
resolve to this same object before being handed to the engine or a service —
this is what lets `POST /simulations/net-worth` and `POST /scenarios/{id}/run`
share one code path.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class PlanningAssumptions:
    current_age: int
    retirement_age: int
    life_expectancy_age: int = 95
    savings_rate: Decimal = Decimal("0.20")          # fraction of gross income saved
    monthly_contribution: Decimal = Decimal("0")       # flat override, if set takes precedence
    expected_return: Decimal = Decimal("0.065")          # nominal annual return, pre-inflation
    inflation_rate: Decimal = Decimal("0.028")
    withdrawal_rate: Decimal = Decimal("0.04")             # in retirement
    employer_match_rate: Decimal = Decimal("0")               # fraction of salary matched
    employer_match_cap: Decimal = Decimal("0")                 # fraction of salary, cap on match
    # If set, this REPLACES the withdrawal_rate-derived spending target for
    # both the deterministic projection and Monte Carlo: the user names a
    # monthly lifestyle cost in TODAY's purchasing power, it gets inflated
    # forward to the dollar amount actually needed at retirement, and (in
    # Monte Carlo) continues escalating with inflation through retirement
    # so purchasing power stays constant rather than eroding. When None,
    # scenarios fall back to the old withdrawal_rate % of balance.
    desired_monthly_income_today: Decimal | None = None
    # User's target equity allocation (0-1), used to derive a return-
    # volatility assumption for Monte Carlo (see
    # app/simulation/engine.py:implied_return_volatility) instead of one
    # fixed number for every user regardless of actual risk profile.
    target_equity_allocation: Decimal = Decimal("0.60")

    def __post_init__(self):
        if self.retirement_age <= self.current_age:
            raise ValueError("retirement_age must be greater than current_age")
        if self.life_expectancy_age <= self.retirement_age:
            raise ValueError("life_expectancy_age must be greater than retirement_age")

    @property
    def years_to_retirement(self) -> int:
        return self.retirement_age - self.current_age

    @property
    def years_in_retirement(self) -> int:
        return self.life_expectancy_age - self.retirement_age

    @property
    def real_return(self) -> Decimal:
        """Inflation-adjusted (real) rate of return, via the Fisher equation."""
        one = Decimal("1")
        return (one + self.expected_return) / (one + self.inflation_rate) - one
