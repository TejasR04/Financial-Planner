"""NetWorthProjectionService — projects combined asset/liability trajectory.

Backs the Overview page's net-worth chart ("projected" points) and the
Projections page's scenario trajectories.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import Account
from app.domain.enums import AccountType
from app.simulation.assumptions import PlanningAssumptions

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
        """Account-aware projection using the assumptions available here.

        Investment and retirement accounts use ``expected_return``, deposits
        use their own APY (or 0 when unknown), and property tracks inflation.
        New contributions are assigned to invested assets. Liabilities still
        use the explicitly approximate payoff rate because this service does
        not receive loan terms; specific debts should use
        ``DebtOptimizationService``.
        """
        asset_balances = {
            account.id: account.balance
            for account in accounts
            if not account.is_liability and account.balance > ZERO
        }
        liability_balances = {
            account.id: abs(account.balance)
            for account in accounts
            if account.is_liability and account.balance != ZERO
        }

        assets_balance = sum(asset_balances.values(), ZERO)
        liabilities_balance = sum(liability_balances.values(), ZERO)
        net_worth_today = assets_balance - liabilities_balance
        series: list[NetWorthYearPoint] = []
        payoff_factor = Decimal("1") - liability_payoff_rate
        invested_contributions_balance = ZERO

        for i in range(1, years + 1):
            for account in accounts:
                if account.id not in asset_balances:
                    continue
                if account.type in (AccountType.INVESTMENT, AccountType.RETIREMENT):
                    rate = assumptions.expected_return
                elif account.type == AccountType.DEPOSITORY:
                    rate = (account.apy or ZERO) / Decimal("100")
                elif account.type == AccountType.PROPERTY:
                    rate = assumptions.inflation_rate
                else:
                    rate = ZERO
                asset_balances[account.id] *= Decimal("1") + rate

            # The input is explicitly a net contribution to financial assets;
            # without a destination account, treat it as invested rather than
            # granting portfolio returns to every existing asset.
            invested_contributions_balance = (
                invested_contributions_balance
                * (Decimal("1") + assumptions.expected_return)
                + annual_net_contribution
            )
            assets_balance = sum(asset_balances.values(), ZERO) + invested_contributions_balance

            liability_balances = {
                account_id: max(ZERO, balance * payoff_factor)
                for account_id, balance in liability_balances.items()
            }
            liabilities_balance = sum(liability_balances.values(), ZERO)
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
