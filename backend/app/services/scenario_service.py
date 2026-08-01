"""ScenarioService — the computation behind `POST /scenarios/{id}/run` and
the `compare_scenarios` AI tool. Pure Python: takes assumptions and account
data, returns a typed result. CRUD persistence for Scenario itself stays in
`ScenarioRepository` / the route layer, since that's plain storage with no
math in it — this service is only the "run a scenario" computation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from app.domain.entities import Account
from app.services.net_worth_projection_service import NetWorthProjection, NetWorthProjectionService
from app.services.retirement_projection_service import RetirementProjection, RetirementProjectionService
from app.simulation.assumptions import PlanningAssumptions
from app.simulation.engine import implied_return_volatility
from app.simulation.monte_carlo import MonteCarloResult, run_monte_carlo

ENGINE_VERSION = "1.1.0"


@dataclass(slots=True, frozen=True)
class ScenarioRunResult:
    net_worth_projection: NetWorthProjection
    retirement_projection: RetirementProjection
    monte_carlo: MonteCarloResult | None
    engine_version: str = ENGINE_VERSION


@dataclass(slots=True, frozen=True)
class SensitivityRow:
    label: str
    # "balance_pct": value is % change in projected balance at retirement.
    # "success_pp": value is percentage-POINT change in Monte Carlo success
    # rate (withdrawal rate doesn't move the accumulated balance at all —
    # it only affects whether that balance survives retirement).
    kind: str
    value: Decimal
    note: str


@dataclass(slots=True, frozen=True)
class SensitivityResult:
    baseline_balance_at_retirement: Decimal
    baseline_success_rate: Decimal | None
    rows: list[SensitivityRow]


def _effective_withdrawal(
    retirement: RetirementProjection, assumptions: PlanningAssumptions, annual_spending_target: Decimal | None
) -> Decimal:
    """The real annual amount withdrawn in year 1 of retirement, for
    Monte Carlo. Priority: an explicit annual spending target > the user's
    today's-dollars income goal > the withdrawal-rate-derived figure.
    """
    if annual_spending_target is not None:
        return annual_spending_target
    if retirement.target_annual_income_real is not None:
        return retirement.target_annual_income_real
    return retirement.annual_sustainable_withdrawal


def _real_volatility(nominal_volatility: Decimal, inflation_rate: Decimal) -> Decimal:
    """Scale nominal-return volatility into constant-inflation real terms."""
    return nominal_volatility / (Decimal("1") + inflation_rate)


def _nominal_return_for_real_increase(
    assumptions: PlanningAssumptions, increase: Decimal
) -> Decimal:
    """Return the nominal assumption that raises real return by ``increase``."""
    return (
        (Decimal("1") + assumptions.real_return + increase)
        * (Decimal("1") + assumptions.inflation_rate)
        - Decimal("1")
    )


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
        return_volatility: Decimal | None = None,
        monte_carlo_seed: int = 42,
    ) -> ScenarioRunResult:
        years = assumptions.years_to_retirement
        # Derive volatility from the user's own target equity allocation
        # (see implied_return_volatility) unless a caller explicitly wants
        # to override it — e.g. an AI tool call with its own risk figure.
        effective_volatility = (
            return_volatility
            if return_volatility is not None
            else implied_return_volatility(assumptions.target_equity_allocation)
        )

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
            withdrawal = _effective_withdrawal(retirement, assumptions, annual_spending_target)
            target = annual_spending_target / assumptions.withdrawal_rate if annual_spending_target else (
                retirement.projected_balance_at_retirement
            )
            monte_carlo = run_monte_carlo(
                starting_balance=current_retirement_balance,
                annual_contribution=annual_contribution,
                expected_return=assumptions.real_return,
                return_volatility=_real_volatility(
                    effective_volatility, assumptions.inflation_rate
                ),
                years=years,
                starting_age=assumptions.current_age,
                target_balance=target,
                retirement_years=assumptions.years_in_retirement,
                annual_withdrawal=withdrawal,
                # A flat real withdrawal already preserves purchasing power.
                annual_withdrawal_growth_rate=Decimal("0"),
                trials=monte_carlo_trials,
                seed=monte_carlo_seed,
            )

        return ScenarioRunResult(
            net_worth_projection=net_worth,
            retirement_projection=retirement,
            monte_carlo=monte_carlo,
        )

    def analyze_sensitivity(
        self,
        assumptions: PlanningAssumptions,
        current_retirement_balance: Decimal,
        monte_carlo_trials: int = 500,
        monte_carlo_seed: int = 42,
    ) -> SensitivityResult:
        """Genuinely computes each row by re-running the same deterministic/
        Monte Carlo engine with one assumption nudged, rather than showing
        canned numbers. Only includes levers this app can actually compute
        from stored assumptions — no fabricated rows (e.g. nothing here
        claims to model tax-advantaged account space, since there's no
        contribution-limit data backing that).
        """
        annual_contribution = assumptions.monthly_contribution * 12

        baseline_retirement = self._retirement_service.project(
            current_retirement_balance=current_retirement_balance,
            annual_contribution=annual_contribution,
            assumptions=assumptions,
        )
        baseline_balance = baseline_retirement.projected_balance_at_retirement

        baseline_mc = run_monte_carlo(
            starting_balance=current_retirement_balance,
            annual_contribution=annual_contribution,
            expected_return=assumptions.real_return,
            return_volatility=_real_volatility(
                implied_return_volatility(assumptions.target_equity_allocation),
                assumptions.inflation_rate,
            ),
            years=assumptions.years_to_retirement,
            starting_age=assumptions.current_age,
            target_balance=baseline_balance,
            retirement_years=assumptions.years_in_retirement,
            annual_withdrawal=_effective_withdrawal(baseline_retirement, assumptions, None),
            annual_withdrawal_growth_rate=Decimal("0"),
            trials=monte_carlo_trials,
            seed=monte_carlo_seed,
        )

        def balance_pct_row(label: str, varied: PlanningAssumptions, note_suffix: str) -> SensitivityRow:
            varied_result = self._retirement_service.project(
                current_retirement_balance=current_retirement_balance,
                annual_contribution=varied.monthly_contribution * 12,
                assumptions=varied,
            )
            varied_balance = varied_result.projected_balance_at_retirement
            if baseline_balance == 0:
                pct = Decimal("0")
            else:
                pct = ((varied_balance - baseline_balance) / baseline_balance) * 100
            return SensitivityRow(
                label=label, kind="balance_pct", value=round(pct, 1),
                note=f"{note_suffix}: {varied_balance:,.0f}",
            )

        rows: list[SensitivityRow] = []

        # +1% expected return
        rows.append(
            balance_pct_row(
                "+1% real return",
                replace(
                    assumptions,
                    expected_return=_nominal_return_for_real_increase(
                        assumptions, Decimal("0.01")
                    ),
                ),
                "Balance at retirement",
            )
        )

        # -2 years to retirement (guarded against going below current_age+1)
        shorter_age = max(assumptions.current_age + 1, assumptions.retirement_age - 2)
        rows.append(
            balance_pct_row(
                "-2 years to retirement",
                replace(assumptions, retirement_age=shorter_age),
                "Balance at retirement",
            )
        )

        # +$200/mo contribution
        rows.append(
            balance_pct_row(
                "+$200/mo contribution",
                replace(assumptions, monthly_contribution=assumptions.monthly_contribution + Decimal("200")),
                "Balance at retirement",
            )
        )

        if assumptions.desired_monthly_income_today is not None:
            # Income-target mode: withdrawal_rate isn't in play at all here,
            # so the meaningful "cost of a bigger lifestyle" lever is the
            # target itself — how much does asking for $200/mo more cost
            # you in survival odds.
            varied_income = replace(
                assumptions,
                desired_monthly_income_today=assumptions.desired_monthly_income_today + Decimal("200"),
            )
            varied_retirement = self._retirement_service.project(
                current_retirement_balance=current_retirement_balance,
                annual_contribution=annual_contribution,
                assumptions=varied_income,
            )
            varied_mc = run_monte_carlo(
                starting_balance=current_retirement_balance,
                annual_contribution=annual_contribution,
                expected_return=varied_income.real_return,
                return_volatility=_real_volatility(
                    implied_return_volatility(assumptions.target_equity_allocation),
                    varied_income.inflation_rate,
                ),
                years=varied_income.years_to_retirement,
                starting_age=varied_income.current_age,
                target_balance=varied_retirement.projected_balance_at_retirement,
                retirement_years=varied_income.years_in_retirement,
                annual_withdrawal=_effective_withdrawal(varied_retirement, varied_income, None),
                annual_withdrawal_growth_rate=Decimal("0"),
                trials=monte_carlo_trials,
                seed=monte_carlo_seed,
            )
            success_delta_pp = round(
                (Decimal(str(varied_mc.success_rate)) - Decimal(str(baseline_mc.success_rate))) * 100, 1
            )
            rows.append(
                SensitivityRow(
                    label="+$200/mo desired income",
                    kind="success_pp",
                    value=success_delta_pp,
                    note=f"Success rate: {round(varied_mc.success_rate * 100, 1)}%",
                )
            )
        else:
            # Legacy rate-based mode — withdrawal_rate doesn't change the
            # accumulated balance at all (withdrawal only happens after
            # retirement), so this row is measured in Monte Carlo
            # success-rate percentage points instead.
            varied_withdrawal = replace(assumptions, withdrawal_rate=assumptions.withdrawal_rate + Decimal("0.005"))
            varied_retirement = self._retirement_service.project(
                current_retirement_balance=current_retirement_balance,
                annual_contribution=annual_contribution,
                assumptions=varied_withdrawal,
            )
            varied_mc = run_monte_carlo(
                starting_balance=current_retirement_balance,
                annual_contribution=annual_contribution,
                expected_return=varied_withdrawal.real_return,
                return_volatility=_real_volatility(
                    implied_return_volatility(assumptions.target_equity_allocation),
                    varied_withdrawal.inflation_rate,
                ),
                years=varied_withdrawal.years_to_retirement,
                starting_age=varied_withdrawal.current_age,
                target_balance=varied_retirement.projected_balance_at_retirement,
                retirement_years=varied_withdrawal.years_in_retirement,
                annual_withdrawal=varied_retirement.annual_sustainable_withdrawal,
                annual_withdrawal_growth_rate=Decimal("0"),
                trials=monte_carlo_trials,
                seed=monte_carlo_seed,
            )
            success_delta_pp = round(
                (Decimal(str(varied_mc.success_rate)) - Decimal(str(baseline_mc.success_rate))) * 100, 1
            )
            rows.append(
                SensitivityRow(
                    label="+0.5% withdrawal rate",
                    kind="success_pp",
                    value=success_delta_pp,
                    note=f"Success rate: {round(varied_mc.success_rate * 100, 1)}%",
                )
            )

        return SensitivityResult(
            baseline_balance_at_retirement=baseline_balance,
            baseline_success_rate=Decimal(str(round(baseline_mc.success_rate, 4))),
            rows=rows,
        )
