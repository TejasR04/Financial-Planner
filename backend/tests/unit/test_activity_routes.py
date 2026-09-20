from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routes import activity
from app.domain.entities import User
from app.domain.enums import TransactionStatus, TransactionType
from app.services.activity_history import ActivityHistory
from app.services.budget_service import BudgetTransactionInput


@pytest.mark.asyncio
async def test_activity_summary_returns_null_averages_without_completed_months(monkeypatch):
    history = ActivityHistory([], [], history_start=date(2026, 9, 10))
    loader = AsyncMock(return_value=(history, (Decimal("0"), Decimal("0"))))
    monkeypatch.setattr(activity, "load_budget_activity_summary", loader)
    user = User(id=uuid4(), email="person@example.com", full_name="Person")
    db = object()

    result = await activity.get_activity_summary(user, db)

    assert result.history_start == date(2026, 9, 10)
    assert result.month_count == 0
    assert result.period_start is None
    assert result.period_end is None
    assert result.average_monthly_income is None
    assert result.average_monthly_expenses is None
    assert result.average_monthly_surplus is None
    loader.assert_awaited_once_with(db, user.id)


@pytest.mark.asyncio
async def test_activity_summary_preserves_authoritative_twelve_month_window(monkeypatch):
    months = [date(2025 + (8 + index) // 12, (8 + index) % 12 + 1, 1) for index in range(12)]
    category_id = uuid4()
    transactions = [
        BudgetTransactionInput(
            "Pay", Decimal("12000"), TransactionStatus.CLEARED, None,
            TransactionType.INCOME, False, "income", months[0],
        ),
        BudgetTransactionInput(
            "Rent", Decimal("-6000"), TransactionStatus.CLEARED, category_id,
            TransactionType.EXPENSE, False, "housing", months[-1],
        ),
    ]
    history = ActivityHistory(months, transactions, history_start=date(2020, 1, 15))
    monkeypatch.setattr(
        activity,
        "load_budget_activity_summary",
        AsyncMock(return_value=(history, (Decimal("1000"), Decimal("500")))),
    )
    user = User(id=uuid4(), email="person@example.com", full_name="Person")

    result = await activity.get_activity_summary(user, object())

    assert result.history_start == date(2020, 1, 15)
    assert result.month_count == 12
    assert result.period_start == months[0]
    assert result.period_end == months[-1]
    assert result.average_monthly_income == Decimal("1000")
    assert result.average_monthly_expenses == Decimal("500")
    assert result.average_monthly_surplus == Decimal("500")
