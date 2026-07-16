"""NetWorthProjectionService — projects combined asset/liability trajectory.

Backs the Overview page's net-worth chart ("projected" points) and the
Projections page's scenario trajectories.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import Account
from app.simulation.assumptions import PlanningAssumptions
from app.simulation.engine import compound_growth

ZERO = Decimal("0")


@dataclass(slots=True, frozen=True)
class NetWorthYearPoint:
    year_index: int
    age: int
    assets: Decimal
    liabilities: Decimal
    net: Decimal


@dataclass(slots=True, frozen=True)
class NetWorthProjection:
    series: list[NetWorthYearPoint]
    net_worth_today: Decimal
    projected_net_worth_at_horizon: Decimal


class NetWorthProjectionService:
    def project(
        self,
        accounts: list[Account],
        assumptions: PlanningAssumptions,
        years: int,
        annual_net_contribution: Decimal = ZERO,
        liability_payoff_rate: Decimal = Decimal("0.03"),
    ) -> NetWorthProjection:
        """Simplified combined projection: asset accounts grow at
        `expected_return` plus new net contributions; liability accounts
        shrink at `liability_payoff_rate` (approximation for a mixed debt
        book — for a specific loan, prefer DebtOptimizationService's real
        amortization schedule).
        """
        assets_balance = sum((a.balance for a in accounts if a.balance > 0), ZERO)
        liabilities_balance = sum((-a.balance for a in accounts if a.balance < 0), ZERO)

        net_worth_today = assets_balance - liabilities_balance
        series: list[NetWorthYearPoint] = []
        growth_factor = Decimal("1") + assumptions.expected_return
        payoff_factor = Decimal("1") - liability_payoff_rate

        for i in range(1, years + 1):
            assets_balance = assets_balance * growth_factor + annual_net_contribution
            liabilities_balance = max(ZERO, liabilities_balance * payoff_factor)
            series.append(
                NetWorthYearPoint(
                    year_index=i,
                    age=assumptions.current_age + i,
                    assets=assets_balance.quantize(Decimal("0.01")),
                    liabilities=liabilities_balance.quantize(Decimal("0.01")),
                    net=(assets_balance - liabilities_balance).quantize(Decimal("0.01")),
                )
            )

        horizon_net = series[-1].net if series else net_worth_today
        return NetWorthProjection(
            series=series,
            net_worth_today=net_worth_today,
            projected_net_worth_at_horizon=horizon_net,
        )
