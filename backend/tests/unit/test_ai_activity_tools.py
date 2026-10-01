from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai.agent import AgentOrchestrator
from app.api.v1.routes import agent as agent_routes
from app.ai.tool_registry import registry
from app.ai.tools import activity_tools
from app.ai.tools.activity_tools import ActivityScope, BudgetSummaryInput, SpendingSummaryInput
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
async def test_undated_activity_uses_chat_system_day(monkeypatch):
    repo = SimpleNamespace(list_for_user=AsyncMock(return_value=([], 0)),
                           totals_for_user=AsyncMock(return_value={"income": Decimal(0),
                                                              "spending": Decimal(0), "net_cash_flow": Decimal(0)}))
    monkeypatch.setattr(activity_tools, "TransactionRepository", lambda session: repo)
    scope = ActivityScope(object(), uuid4(), date(2026, 9, 30))

    result = await activity_tools.get_spending_summary(SpendingSummaryInput(), scope)

    assert result["period"] == {"start": "2026-09-01", "end": "2026-09-30"}
    assert repo.totals_for_user.await_args.kwargs["until"] == date(2026, 9, 30)


def test_chat_date_follows_browser_timezone_across_midnight():
    instant = datetime(2026, 10, 1, 3, 57, tzinfo=timezone.utc)

    eastern, zone = agent_routes._chat_local_now("America/New_York", instant)
    iceland, _ = agent_routes._chat_local_now("Atlantic/Reykjavik", instant)

    assert eastern.date() == date(2026, 9, 30)
    assert zone == "America/New_York"
    assert iceland.date() == date(2026, 10, 1)


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
    progress = []
    result = await AgentOrchestrator(client=SimpleNamespace(models=models), model="test").handle_message_scoped(
        "What happened September 8?", [], "{}", ActivityScope(object(), uuid4()), on_progress=progress.append)
    assert result.reply == "One transaction found."
    assert result.tool_calls[0]["tool"] == "search_transactions"
    assert result.structured_results[0]["result"]["matching_count"] == 0
    assert any(item.name == "search_transactions" for item in models.requests[0]["config"].tools[0].function_declarations)
    assert "Looking up transactions" in progress


@pytest.mark.asyncio
async def test_chat_stream_emits_status_before_complete(monkeypatch):
    import json

    async def fake_run(body, user, db, on_progress):
        on_progress("Reading your saved finances")
        on_progress("Checking budget limits and spending")
        return agent_routes.ChatResponse(conversation_id=str(uuid4()), reply="Done", tool_calls=[], structured_results=[])

    monkeypatch.setattr(agent_routes, "_run_chat", fake_run)
    response = await agent_routes.chat_stream(agent_routes.ChatRequest(message="Budget?"),
                                             SimpleNamespace(id=uuid4()), object())
    events = [json.loads(chunk) async for chunk in response.body_iterator]
    assert [event["type"] for event in events] == ["status", "status", "complete"]
    assert events[1]["label"] == "Checking budget limits and spending"
    assert events[2]["data"]["reply"] == "Done"
