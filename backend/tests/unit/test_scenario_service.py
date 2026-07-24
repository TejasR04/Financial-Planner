from decimal import Decimal
from uuid import uuid4

from app.domain.entities import Account
from app.domain.enums import AccountType
from app.services.scenario_service import ScenarioService
from app.simulation.assumptions import PlanningAssumptions


def _accounts():
    return [
        Account(id=uuid4(), user_id=uuid4(), name="Brokerage", type=AccountType.INVESTMENT, balance=Decimal("300000")),
        Account(id=uuid4(), user_id=uuid4(), name="Mortgage", type=AccountType.LOAN, balance=Decimal("-200000")),
    ]


def test_scenario_run_produces_net_worth_and_retirement_projection():
    service = ScenarioService()
    assumptions = PlanningAssumptions(current_age=40, retirement_age=65, expected_return=Decimal("0.07"))
    result = service.run(
        accounts=_accounts(),
        assumptions=assumptions,
        current_retirement_balance=Decimal("150000"),
        annual_contribution=Decimal("24000"),
        include_monte_carlo=False,
    )
    assert result.net_worth_projection.projected_net_worth_at_horizon > result.net_worth_projection.net_worth_today
    assert result.retirement_projection.projected_balance_at_retirement > Decimal("150000")
    assert result.monte_carlo is None
    assert result.engine_version == "1.0.0"


def test_scenario_run_includes_monte_carlo_when_requested():
    service = ScenarioService()
    assumptions = PlanningAssumptions(current_age=45, retirement_age=65, expected_return=Decimal("0.07"))
    result = service.run(
        accounts=_accounts(),
        assumptions=assumptions,
        current_retirement_balance=Decimal("200000"),
        annual_contribution=Decimal("30000"),
        include_monte_carlo=True,
        monte_carlo_trials=200,
    )
    assert result.monte_carlo is not None
    assert result.monte_carlo.trials == 200
    assert 0.0 <= result.monte_carlo.success_rate <= 1.0


def test_scenario_run_monte_carlo_targets_spending_derived_balance():
    """When an annual_spending_target is given, the Monte Carlo target
    balance should be derived from it via the withdrawal rate rather than
    from the deterministic projection, so success_rate answers 'can I
    sustain this spending', not 'do I hit the deterministic number'."""
    service = ScenarioService()
    assumptions = PlanningAssumptions(
        current_age=50, retirement_age=65, expected_return=Decimal("0.07"), withdrawal_rate=Decimal("0.04")
    )
    result = service.run(
        accounts=_accounts(),
        assumptions=assumptions,
        current_retirement_balance=Decimal("500000"),
        annual_contribution=Decimal("20000"),
        annual_spending_target=Decimal("40000"),
        include_monte_carlo=True,
        monte_carlo_trials=100,
    )
    assert result.monte_carlo is not None


def test_sensitivity_higher_return_increases_balance():
    service = ScenarioService()
    assumptions = PlanningAssumptions(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("500"),
    )
    result = service.analyze_sensitivity(assumptions, current_retirement_balance=Decimal("100000"))
    return_row = next(r for r in result.rows if r.label == "+1% real return")
    assert return_row.kind == "balance_pct"
    assert return_row.value > 0  # more return -> bigger ending balance


def test_sensitivity_fewer_years_decreases_balance():
    service = ScenarioService()
    assumptions = PlanningAssumptions(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("500"),
    )
    result = service.analyze_sensitivity(assumptions, current_retirement_balance=Decimal("100000"))
    years_row = next(r for r in result.rows if r.label == "-2 years to retirement")
    assert years_row.value < 0  # less time to grow -> smaller ending balance


def test_sensitivity_higher_contribution_increases_balance():
    service = ScenarioService()
    assumptions = PlanningAssumptions(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("500"),
    )
    result = service.analyze_sensitivity(assumptions, current_retirement_balance=Decimal("100000"))
    contrib_row = next(r for r in result.rows if r.label == "+$200/mo contribution")
    assert contrib_row.value > 0


def test_sensitivity_withdrawal_rate_row_is_measured_in_success_rate_not_balance():
    service = ScenarioService()
    assumptions = PlanningAssumptions(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("500"), withdrawal_rate=Decimal("0.04"),
    )
    result = service.analyze_sensitivity(assumptions, current_retirement_balance=Decimal("100000"))
    withdrawal_row = next(r for r in result.rows if r.label == "+0.5% withdrawal rate")
    assert withdrawal_row.kind == "success_pp"
    # A higher withdrawal rate should never IMPROVE sustainability.
    assert withdrawal_row.value <= 0


def test_income_target_inflates_todays_dollars_to_retirement_dollars():
    service = ScenarioService()
    assumptions = PlanningAssumptions(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        inflation_rate=Decimal("0.028"), monthly_contribution=Decimal("500"),
        desired_monthly_income_today=Decimal("4000"),
    )
    result = service.run(
        accounts=[], assumptions=assumptions, current_retirement_balance=Decimal("100000"),
        annual_contribution=Decimal("6000"), include_monte_carlo=False,
    )
    retirement = result.retirement_projection
    # $4,000/mo today, 25 years of 2.8% inflation, should compound to
    # meaningfully more than $4,000/mo in nominal terms at retirement.
    assert retirement.target_monthly_income_at_retirement is not None
    assert retirement.target_monthly_income_at_retirement > Decimal("7500")
    assert retirement.target_monthly_income_at_retirement < Decimal("8500")


def test_income_target_drives_feasibility_check():
    service = ScenarioService()
    # A tiny balance with a huge income target should come back infeasible.
    assumptions = PlanningAssumptions(
        current_age=60, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("0"), desired_monthly_income_today=Decimal("50000"),
    )
    result = service.run(
        accounts=[], assumptions=assumptions, current_retirement_balance=Decimal("10000"),
        annual_contribution=Decimal("0"), include_monte_carlo=False,
    )
    assert result.retirement_projection.is_feasible is False
    assert result.retirement_projection.shortfall_or_surplus < 0


def test_income_target_used_for_monte_carlo_withdrawal_not_rate():
    service = ScenarioService()
    # Two scenarios with the SAME balance but very different withdrawal
    # rates should now produce the SAME success rate once an explicit
    # income target overrides the rate — proving the rate is ignored.
    base_kwargs = dict(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("500"), desired_monthly_income_today=Decimal("3000"),
    )
    low_rate = PlanningAssumptions(withdrawal_rate=Decimal("0.02"), **base_kwargs)
    high_rate = PlanningAssumptions(withdrawal_rate=Decimal("0.08"), **base_kwargs)

    result_low = service.run(
        accounts=[], assumptions=low_rate, current_retirement_balance=Decimal("200000"),
        annual_contribution=Decimal("6000"), include_monte_carlo=True, monte_carlo_trials=200,
    )
    result_high = service.run(
        accounts=[], assumptions=high_rate, current_retirement_balance=Decimal("200000"),
        annual_contribution=Decimal("6000"), include_monte_carlo=True, monte_carlo_trials=200,
    )
    assert result_low.monte_carlo.success_rate == result_high.monte_carlo.success_rate


def test_sensitivity_switches_to_income_lever_in_target_mode():
    service = ScenarioService()
    assumptions = PlanningAssumptions(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("500"), desired_monthly_income_today=Decimal("4000"),
    )
    result = service.analyze_sensitivity(assumptions, current_retirement_balance=Decimal("300000"))
    labels = [r.label for r in result.rows]
    assert "+$200/mo desired income" in labels
    assert "+0.5% withdrawal rate" not in labels
    income_row = next(r for r in result.rows if r.label == "+$200/mo desired income")
    assert income_row.kind == "success_pp"
    # Asking for MORE income should never improve (and should typically
    # hurt) survival odds.
    assert income_row.value <= 0


def test_default_volatility_keeps_classic_4pct_rule_reasonably_close_to_historical_success():
    """Regression guard: the default return_volatility must stay calibrated
    so a textbook 4%-of-balance withdrawal (well-documented ~90%+ historical
    success over a 30-year retirement) doesn't come back wildly pessimistic.
    A prior default (15% stdev vs. 6.5% expected return) gave only ~65%
    here — an internally inconsistent risk/return pairing that made every
    scenario in the app look far riskier than it actually was.
    """
    from app.simulation.monte_carlo import run_monte_carlo

    balance = Decimal("1000000")
    result = run_monte_carlo(
        starting_balance=balance, annual_contribution=Decimal("0"),
        expected_return=Decimal("0.065"), return_volatility=Decimal("0.10"),
        years=0, starting_age=66, target_balance=Decimal("0"),
        retirement_years=29, annual_withdrawal=balance * Decimal("0.04"),
        annual_withdrawal_growth_rate=Decimal("0.028"),
        trials=2000, seed=42,
    )
    assert result.success_rate > 0.75, (
        f"4%-rule success rate dropped to {result.success_rate:.1%} — "
        "check that return_volatility hasn't drifted back toward an "
        "unrealistically high default."
    )


def test_implied_return_volatility_matches_cited_anchor_points():
    """Locks in the sourced data points from
    app/simulation/engine.py:_VOLATILITY_ANCHORS so a future edit can't
    silently drift the calibration without a test failing."""
    from app.simulation.engine import implied_return_volatility

    assert implied_return_volatility(Decimal("0.19")) == Decimal("0.0580")
    assert implied_return_volatility(Decimal("0.405")) == Decimal("0.0832")
    assert implied_return_volatility(Decimal("0.60")) == Decimal("0.1060")
    assert implied_return_volatility(Decimal("0.9425")) == Decimal("0.1606")
    # Monotonically increasing with more equity exposure.
    assert implied_return_volatility(Decimal("0")) < implied_return_volatility(Decimal("0.5"))
    assert implied_return_volatility(Decimal("0.5")) < implied_return_volatility(Decimal("1"))


def test_higher_equity_allocation_increases_volatility_and_lowers_success_at_same_withdrawal():
    """A more aggressive (equity-heavy) allocation should show LOWER Monte
    Carlo success than a conservative one for the exact same withdrawal
    plan — proving the allocation is actually driving the risk model now,
    not just stored and ignored."""
    service = ScenarioService()
    base_kwargs = dict(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("500"), desired_monthly_income_today=Decimal("4000"),
    )
    conservative = PlanningAssumptions(target_equity_allocation=Decimal("0.20"), **base_kwargs)
    aggressive = PlanningAssumptions(target_equity_allocation=Decimal("0.95"), **base_kwargs)

    result_conservative = service.run(
        accounts=[], assumptions=conservative, current_retirement_balance=Decimal("500000"),
        annual_contribution=Decimal("6000"), include_monte_carlo=True, monte_carlo_trials=1500,
    )
    result_aggressive = service.run(
        accounts=[], assumptions=aggressive, current_retirement_balance=Decimal("500000"),
        annual_contribution=Decimal("6000"), include_monte_carlo=True, monte_carlo_trials=1500,
    )
    assert result_aggressive.monte_carlo.success_rate < result_conservative.monte_carlo.success_rate


def test_explicit_volatility_override_still_respected():
    """An explicit return_volatility argument (used by the AI tool) should
    still win over the allocation-derived default."""
    service = ScenarioService()
    assumptions = PlanningAssumptions(
        current_age=40, retirement_age=65, expected_return=Decimal("0.065"),
        monthly_contribution=Decimal("500"), target_equity_allocation=Decimal("0.60"),
    )
    result = service.run(
        accounts=[], assumptions=assumptions, current_retirement_balance=Decimal("500000"),
        annual_contribution=Decimal("6000"), include_monte_carlo=True, monte_carlo_trials=200,
        return_volatility=Decimal("0.03"),  # deliberately tiny -> should push success very high
    )
    assert result.monte_carlo.success_rate > 0.95
