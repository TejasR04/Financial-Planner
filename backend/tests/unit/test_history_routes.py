from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import simulations, insights
from app.domain.entities import User, FinancialSnapshot, PlanningProfile
from app.schemas.simulation import CashFlowSimulationRequest
from app.services.activity_history import ActivityHistory
from app.services.budget_service import BudgetTransactionInput


@pytest.mark.asyncio
async def test_outlook_uses_shared_history_and_not_partial_month_or_saved_salary(monkeypatch):
    user = User(uuid4(), "test@example.com", "Test")
    history = ActivityHistory([date(2026, 7, 1), date(2026, 8, 1)], [
        BudgetTransactionInput("Salary", Decimal(8000), "cleared", None, type="income", posted_at=date(2026, 7, 1)),
        BudgetTransactionInput("Rent", Decimal(-2000), "cleared", None, posted_at=date(2026, 7, 2)),
        BudgetTransactionInput("Rent", Decimal(-4000), "cleared", None, posted_at=date(2026, 8, 2)),
        BudgetTransactionInput("Partial month", Decimal(-9000), "cleared", None, posted_at=date(2026, 9, 2)),
    ])
    loader = AsyncMock(return_value=history)
    monkeypatch.setattr(simulations, "load_activity_history", loader)
    monkeypatch.setattr(simulations, "IncomeSourceRepository", lambda db: SimpleNamespace(list_for_user=AsyncMock(return_value=[])))
    monkeypatch.setattr(simulations, "UserRepository", lambda db: SimpleNamespace(get_planning_profile=AsyncMock(return_value=PlanningProfile(user.id))))
    result = await simulations.simulate_cash_flow(CashFlowSimulationRequest(months=6), user, None)
    assert len(result.series) == 6
    assert result.series[0].income == 4000
    assert result.series[0].expenses == 3000
    assert result.average_monthly_surplus == 1000
    assert "2 completed months (Jul 2026 to Aug 2026)" in result.expense_source
    loader.return_value = ActivityHistory([], [])
    with pytest.raises(HTTPException) as error:
        await simulations.simulate_cash_flow(CashFlowSimulationRequest(), user, None)
    assert error.value.status_code == 422
    assert "completed month" in error.value.detail


@pytest.mark.asyncio
async def test_insight_reads_reflect_current_activity_without_stored_health_score(monkeypatch):
    user = User(uuid4(), "test@example.com", "Test")
    snapshot = FinancialSnapshot(user, PlanningProfile(user.id))
    history = ActivityHistory([date(2026, 8, 1)], [
        BudgetTransactionInput("Rent", Decimal(-2000), "cleared", None, posted_at=date(2026, 8, 2)),
    ])
    monkeypatch.setattr(insights, "build_financial_snapshot", AsyncMock(return_value=snapshot))
    loader = AsyncMock(return_value=history)
    monkeypatch.setattr(insights, "load_activity_history", loader)
    before = await insights.list_insights(user, None)
    assert "$2,000.00" in before[0].text
    loader.return_value = ActivityHistory([], [])
    after = await insights.list_insights(user, None)
    assert "need a completed month" in after[0].text
    assert "$2,000.00" not in after[0].text
