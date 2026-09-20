import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from unittest.mock import ANY, AsyncMock

from app.ai import context
from app.domain.entities import FinancialSnapshot, PlanningProfile, User
from app.services.activity_history import ActivityHistory


@pytest.mark.asyncio
async def test_context_uses_completed_history_average(monkeypatch):
    history = ActivityHistory(
        [date(2026, 6, 1), date(2026, 7, 1), date(2026, 8, 1)], []
    )
    async def fake_history(session, user_id, reference=None):
        return history, (Decimal("4000"), Decimal("2000"))

    monkeypatch.setattr(context, "load_budget_activity_summary", fake_history)
    user = User(id=uuid4(), email="person@example.com", full_name="Person")
    snapshot = FinancialSnapshot(
        user=user, profile=PlanningProfile(user.id), as_of=date(2026, 9, 17)
    )

    payload = json.loads(await context.build_user_financial_context(object(), snapshot))

    assert payload["summary"]["average_monthly_classified_income_completed_history"] == "4000.00"
    assert payload["summary"]["average_monthly_budget_spending_completed_history"] == "2000.00"
    assert payload["summary"]["history_window"].startswith("3 completed months")


@pytest.mark.asyncio
async def test_context_marks_averages_unavailable_without_completed_history(monkeypatch):
    async def fake_history(session, user_id, reference=None):
        return ActivityHistory([], []), (Decimal("0"), Decimal("0"))

    monkeypatch.setattr(context, "load_budget_activity_summary", fake_history)
    user = User(id=uuid4(), email="person@example.com", full_name="Person")
    snapshot = FinancialSnapshot(user=user, profile=PlanningProfile(user.id))

    payload = json.loads(await context.build_user_financial_context(object(), snapshot))

    assert payload["summary"]["average_monthly_classified_income_completed_history"] is None
    assert payload["summary"]["average_monthly_budget_spending_completed_history"] is None


@pytest.mark.asyncio
async def test_context_adds_only_activity_selected_for_the_question(monkeypatch):
    async def fake_history(session, user_id, reference=None):
        return ActivityHistory([], []), (Decimal("0"), Decimal("0"))

    selected = {
        "period": {"label": "last month"},
        "transactions": [{"merchant": "Named merchant", "amount": "-25.00"}],
    }
    selector = AsyncMock(return_value=selected)
    monkeypatch.setattr(context, "load_budget_activity_summary", fake_history)
    monkeypatch.setattr(context, "build_relevant_activity_context", selector)
    user = User(id=uuid4(), email="person@example.com", full_name="Person")
    snapshot = FinancialSnapshot(user=user, profile=PlanningProfile(user.id))

    payload = json.loads(await context.build_user_financial_context(
        object(), snapshot, "Show the Named merchant transaction last month"
    ))

    assert payload["requested_activity"] == selected
    selector.assert_awaited_once_with(
        ANY,
        user.id,
        "Show the Named merchant transaction last month",
        snapshot.as_of,
        [],
    )
