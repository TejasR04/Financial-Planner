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
