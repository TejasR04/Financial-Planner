from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai import relevant_activity
from app.domain.entities import Transaction
from app.domain.enums import TransactionStatus, TransactionType


def transaction(
    merchant: str,
    amount: str,
    posted_at: date,
    *,
    category_id=None,
    category_name=None,
) -> Transaction:
    return Transaction(
        id=uuid4(), account_id=uuid4(), posted_at=posted_at, merchant=merchant,
        category="FOOD_AND_DRINK", amount=Decimal(amount), type=TransactionType.EXPENSE,
        status=TransactionStatus.CLEARED, budget_category_id=category_id,
        budget_category_name=category_name, account_name="Checking",
    )


@pytest.fixture
def activity_repositories(monkeypatch: pytest.MonkeyPatch):
    dining_id = uuid4()
    groceries_id = uuid4()
    categories = [
        SimpleNamespace(id=dining_id, name="Drinks & Dining", group_name="Lifestyle", monthly_limit=Decimal("500"), active=True),
        SimpleNamespace(id=groceries_id, name="Groceries", group_name="Living", monthly_limit=Decimal("600"), active=True),
    ]
    rows = [
        transaction("Starbucks Store 123", "-12.50", date(2026, 9, 8), category_id=dining_id, category_name="Drinks & Dining"),
        transaction("Neighborhood Cafe", "-35.00", date(2026, 9, 4), category_id=dining_id, category_name="Drinks & Dining"),
        transaction("Fresh Market", "-80.00", date(2026, 8, 12), category_id=groceries_id, category_name="Groceries"),
    ]
    budget_repo = SimpleNamespace(list_categories=AsyncMock(return_value=categories))
    transaction_repo = SimpleNamespace(list_for_user=AsyncMock(return_value=(rows, len(rows))))
    monkeypatch.setattr(relevant_activity, "BudgetRepository", lambda session: budget_repo)
    monkeypatch.setattr(relevant_activity, "TransactionRepository", lambda session: transaction_repo)
    return dining_id, groceries_id


@pytest.mark.asyncio
async def test_unrelated_question_does_not_send_ledger_data(activity_repositories) -> None:
    result = await relevant_activity.build_relevant_activity_context(
        object(), uuid4(), "Can I retire at 60?", date(2026, 9, 20)
    )
    assert result is None


@pytest.mark.asyncio
async def test_named_budget_category_sends_current_period_total_without_transactions(activity_repositories) -> None:
    result = await relevant_activity.build_relevant_activity_context(
        object(), uuid4(), "How much have I spent on Dining?", date(2026, 9, 20)
    )
    assert result["period"]["label"] == "this month to date"
    assert result["budget_categories"] == [{
        "name": "Drinks & Dining", "group": "Lifestyle", "monthly_budget": "500.00",
        "net_spending_in_period": "47.50", "pending_in_period": "0.00", "transaction_count": 2,
    }]
    assert "transactions" not in result


@pytest.mark.asyncio
async def test_named_merchant_sends_only_matching_transactions(activity_repositories) -> None:
    result = await relevant_activity.build_relevant_activity_context(
        object(), uuid4(), "Show my Starbucks transactions", date(2026, 9, 20)
    )
    assert result["period"]["label"] == "trailing 12 months"
    assert result["matching_transaction_count"] == 1
    assert result["transactions"][0]["merchant"] == "Starbucks Store 123"
    assert result["transactions"][0]["amount"] == "-12.50"
    assert "id" not in result["transactions"][0]


@pytest.mark.asyncio
async def test_generic_question_words_do_not_match_other_merchants(activity_repositories) -> None:
    result = await relevant_activity.build_relevant_activity_context(
        object(), uuid4(), "Show my transactions from Fresh Market", date(2026, 9, 20)
    )
    assert result["matching_transaction_count"] == 1
    assert result["transactions"][0]["merchant"] == "Fresh Market"


@pytest.mark.asyncio
async def test_specific_amount_and_period_narrow_transaction_details(activity_repositories) -> None:
    result = await relevant_activity.build_relevant_activity_context(
        object(), uuid4(), "Which transaction was $80 last month?", date(2026, 9, 20)
    )
    assert result["period"]["label"] == "last month"
    assert result["matching_transaction_count"] == 1
    assert result["transactions"][0]["merchant"] == "Fresh Market"


@pytest.mark.asyncio
async def test_duration_number_is_not_mistaken_for_an_amount(activity_repositories) -> None:
    result = await relevant_activity.build_relevant_activity_context(
        object(), uuid4(), "Show my transactions for the last 3 months", date(2026, 9, 20)
    )
    assert result["period"]["label"] == "last 3 months"
    assert result["matching_transaction_count"] == 3


@pytest.mark.asyncio
async def test_period_spending_question_sends_category_totals_without_raw_transactions(activity_repositories) -> None:
    result = await relevant_activity.build_relevant_activity_context(
        object(), uuid4(), "How much did I spend last month?", date(2026, 9, 20)
    )
    assert result["period"]["label"] == "last month"
    assert {row["name"] for row in result["budget_categories"]} == {"Drinks & Dining", "Groceries"}
    assert "transactions" not in result


@pytest.mark.asyncio
async def test_follow_up_comparison_includes_monthly_category_history(activity_repositories) -> None:
    result = await relevant_activity.build_relevant_activity_context(
        object(),
        uuid4(),
        "Compare to other previous months\nPrior user request: spending on Dining this month",
        date(2026, 9, 20),
    )

    assert result["period"]["label"] == "trailing 12 months"
    history = result["budget_category_monthly_history"][0]
    assert history["name"] == "Drinks & Dining"
    assert history["months"][-2] == {
        "month": "2026-08", "net_spending": "0.00", "transaction_count": 0,
        "month_to_date": False,
    }
    assert history["months"][-1] == {
        "month": "2026-09", "net_spending": "47.50", "transaction_count": 2,
        "month_to_date": True,
    }
    assert "transactions" not in result
