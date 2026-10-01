from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai.agent import AgentOrchestrator
from app.ai.tool_registry import registry
from app.ai.tools import activity_tools
from app.ai.tools.activity_tools import ActivityScope, BudgetSummaryInput
from app.domain.enums import TransactionStatus, TransactionType


@pytest.mark.asyncio
async def test_search_transactions_uses_authenticated_user_and_exact_day(monkeypatch):
    user_id = uuid4()
    row = SimpleNamespace(posted_at=date(2026, 9, 8), merchant="Cafe", amount=Decimal("-12.50"),
                          type=TransactionType.EXPENSE, status=TransactionStatus.CLEARED,
                          category="FOOD", budget_category_name="Dining", account_name="Checking")
    repo = SimpleNamespace(list_for_user=AsyncMock(return_value=([row], 1)),
                           totals_for_user=AsyncMock(return_value={"income": Decimal(0), "spending": Decimal("12.50"),
                                                              "net_cash_flow": Decimal("-12.50")}))
    monkeypatch.setattr(activity_tools, "TransactionRepository", lambda session: repo)
    scope = ActivityScope(object(), user_id)
    result = await registry.dispatch_async("search_transactions", {
        "start_date": "2026-09-08", "end_date": "2026-09-08",
    }, scope)
    assert result["period"]["start"] == result["period"]["end"] == "2026-09-08"
    assert result["transactions"][0]["merchant"] == "Cafe"
    assert result["has_more"] is False
    assert repo.list_for_user.await_args.args[0] == user_id
    assert repo.list_for_user.await_args.kwargs["since"] == date(2026, 9, 8)
    all_activity = await registry.dispatch_async("search_transactions", {}, scope)
    assert all_activity["period"]["label"] == "all saved activity"
    assert repo.list_for_user.await_args.kwargs["since"] is None
    with pytest.raises(ValueError, match="authenticated"):
        registry.dispatch("search_transactions", {})


@pytest.mark.asyncio
async def test_budget_summary_reuses_budget_rollup_and_filters_category(monkeypatch):
    category_id = uuid4()
    category = SimpleNamespace(id=category_id, name="Dining", group_name="Lifestyle",
                               monthly_limit=Decimal("200"), active=True)
    row = SimpleNamespace(merchant="Cafe", amount=Decimal("-12.50"), status="cleared",
                          budget_category_id=category_id, type="expense", ignored_from_budget=False,
                          category="FOOD", posted_at=date(2026, 9, 8))
    repo = SimpleNamespace(list_categories=AsyncMock(return_value=[category]),
                           list_rules=AsyncMock(return_value=[]),
                           expense_transactions_for_month=AsyncMock(return_value=[row]))
    monkeypatch.setattr(activity_tools, "BudgetRepository", lambda session: repo)
    result = await activity_tools.get_budget_summary(BudgetSummaryInput(month=date(2026, 9, 1), category="Din"),
                                                     ActivityScope(object(), uuid4()))
    assert result["categories"][0]["spent"] == "12.50"
    assert result["categories"][0]["budgeted"] == "200"
    assert result["totals"]["budget_spending"] == "12.50"
    assert result["uncategorized"] is None


@pytest.mark.asyncio
async def test_scoped_agent_can_fetch_then_answer(monkeypatch):
    class Models:
        def __init__(self):
            self.requests = []

        def generate_content(self, **kwargs):
            self.requests.append(kwargs)
            if len(self.requests) == 1:
                call = SimpleNamespace(name="search_transactions", args={"start_date": "2026-09-08"}, id="one")
                return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(
                    parts=[SimpleNamespace(function_call=call)]))], text="")
            return SimpleNamespace(candidates=[], text="One transaction found.")

    repo = SimpleNamespace(list_for_user=AsyncMock(return_value=([], 0)),
                           totals_for_user=AsyncMock(return_value={"income": Decimal(0),
                                                              "spending": Decimal(0), "net_cash_flow": Decimal(0)}))
    monkeypatch.setattr(activity_tools, "TransactionRepository", lambda session: repo)
    models = Models()
    result = await AgentOrchestrator(client=SimpleNamespace(models=models), model="test").handle_message_scoped(
        "What happened September 8?", [], "{}", ActivityScope(object(), uuid4()))
    assert result.reply == "One transaction found."
    assert result.tool_calls[0]["tool"] == "search_transactions"
    assert result.structured_results[0]["result"]["matching_count"] == 0
    assert any(item.name == "search_transactions" for item in models.requests[0]["config"].tools[0].function_declarations)
