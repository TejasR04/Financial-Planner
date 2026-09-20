from decimal import Decimal
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.routes import scenarios
from app.api.v1.routes.scenarios import _new_scenario_assumptions
from app.domain.entities import PlanningProfile, User
from app.schemas.scenario import ScenarioCreateRequest


def test_omitted_scenario_market_assumptions_are_profile_seeded_by_route():
    body = ScenarioCreateRequest(
        name="Plan", current_age=35, retirement_age=65,
    )

    assert body.expected_return is None
    assert body.inflation_rate is None
    assert body.withdrawal_rate is None


def test_new_scenario_uses_saved_profile_defaults_when_omitted():
    profile = PlanningProfile(
        user_id=uuid4(), expected_return=Decimal("0.051"),
        inflation_rate=Decimal("0.021"), default_withdrawal_rate=Decimal("0.03"),
    )
    body = ScenarioCreateRequest(name="Plan", current_age=35, retirement_age=65)

    assumptions = _new_scenario_assumptions(body, profile)

    assert assumptions.expected_return == Decimal("0.051")
    assert assumptions.inflation_rate == Decimal("0.021")
    assert assumptions.withdrawal_rate == Decimal("0.03")


def test_new_scenario_preserves_explicit_overrides():
    profile = PlanningProfile(user_id=uuid4())
    body = ScenarioCreateRequest(
        name="Plan", current_age=35, retirement_age=65,
        expected_return=Decimal("0.04"), inflation_rate=Decimal("0.02"),
        withdrawal_rate=Decimal("0.035"),
    )

    assumptions = _new_scenario_assumptions(body, profile)

    assert assumptions.expected_return == Decimal("0.04")
    assert assumptions.inflation_rate == Decimal("0.02")
    assert assumptions.withdrawal_rate == Decimal("0.035")


@pytest.mark.asyncio
async def test_create_scenario_route_seeds_omitted_values_from_profile(monkeypatch):
    profile = PlanningProfile(
        user_id=uuid4(), expected_return=Decimal("0.051"),
        inflation_rate=Decimal("0.021"), default_withdrawal_rate=Decimal("0.03"),
    )
    captured = {}

    async def get_profile(self, user_id):
        return profile

    async def create(self, user_id, name, description, assumptions, is_baseline=False):
        captured["assumptions"] = assumptions
        now = datetime.now(timezone.utc)
        return SimpleNamespace(
            id=uuid4(), name=name, description=description, is_baseline=is_baseline,
            retirement_age=assumptions.retirement_age, savings_rate=assumptions.savings_rate,
            monthly_contribution=assumptions.monthly_contribution,
            expected_return=assumptions.expected_return,
            inflation_rate=assumptions.inflation_rate,
            withdrawal_rate=assumptions.withdrawal_rate,
            desired_monthly_income_today=assumptions.desired_monthly_income_today,
            created_at=now, updated_at=now,
        )

    class FakeDb:
        async def commit(self):
            return None

    monkeypatch.setattr(scenarios.UserRepository, "get_planning_profile", get_profile)
    monkeypatch.setattr(scenarios.ScenarioRepository, "create", create)
    user = User(id=profile.user_id, email="person@example.com", full_name="Person")
    body = ScenarioCreateRequest(name="Plan", current_age=35, retirement_age=65)

    response = await scenarios.create_scenario(body, user, FakeDb())

    assert response.expected_return == Decimal("0.051")
    assert response.inflation_rate == Decimal("0.021")
    assert response.withdrawal_rate == Decimal("0.03")
    assert captured["assumptions"].withdrawal_rate == Decimal("0.03")
