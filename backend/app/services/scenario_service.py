"""ScenarioService — the computation behind `POST /scenarios/{id}/run` and
the `compare_scenarios` AI tool. Pure Python: takes assumptions and account
data, returns a typed result. CRUD persistence for Scenario itself stays in
`ScenarioRepository` / the route layer, since that's plain storage with no
math in it — this service is only the "run a scenario" computation.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import Account
from app.services.net_worth_projection_service import NetWorthProjection, NetWorthProjectionService
from app.services.retirement_projection_service import RetirementProjection, RetirementProjectionService
from app.simulation.assumptions import PlanningAssumptions
from app.simulation.monte_carlo import MonteCarloResult, run_monte_carlo

ENGINE_VERSION = "1.0.0"


@dataclass(slots=True, frozen=True)
class ScenarioRunResult:
    net_worth_projection: NetWorthProjection
    retirement_projection: RetirementProjection
    monte_carlo: MonteCarloResult | None
    engine_version: str = ENGINE_VERSION


class ScenarioService:
    def __init__(self):
        self._net_worth_service = NetWorthProjectionService()
        self._retirement_service = RetirementProjectionService()

    def run(
        self,
        accounts: list[Account],
        assumptions: PlanningAssumptions,
        current_retirement_balance: Decimal,
        annual_contribution: Decimal,
        annual_spending_target: Decimal | None = None,
        include_monte_carlo: bool = True,
        monte_carlo_trials: int = 1000,
        return_volatility: Decimal = Decimal("0.15"),
        monte_carlo_seed: int = 42,
    ) -> ScenarioRunResult:
        years = assumptions.years_to_retirement

        net_worth = self._net_worth_service.project(
            accounts=accounts,
            assumptions=assumptions,
            years=years,
            annual_net_contribution=annual_contribution,
        )
        retirement = self._retirement_service.project(
            current_retirement_balance=current_retirement_balance,
            annual_contribution=annual_contribution,
            assumptions=assumptions,
            annual_spending_target=annual_spending_target,
        )

        monte_carlo = None
        if include_monte_carlo:
            target = annual_spending_target / assumptions.withdrawal_rate if annual_spending_target else (
                retirement.projected_balance_at_retirement
            )
            monte_carlo = run_monte_carlo(
                starting_balance=current_retirement_balance,
                annual_contribution=annual_contribution,
                expected_return=assumptions.expected_return,
                return_volatility=return_volatility,
                years=years,
                starting_age=assumptions.current_age,
                target_balance=target,
                trials=monte_carlo_trials,
                seed=monte_carlo_seed,
            )

        return ScenarioRunResult(
            net_worth_projection=net_worth,
            retirement_projection=retirement,
            monte_carlo=monte_carlo,
        )
