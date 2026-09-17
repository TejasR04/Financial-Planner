from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.domain.entities import Account, FinancialSnapshot, PlanningProfile, User
from app.domain.enums import AccountType
from app.services.activity_history import ActivityHistory
from app.services.budget_service import BudgetTransactionInput
from app.services.insight_service import InsightService


def snapshot():
    user = User(uuid4(), "test@example.com", "Test")
    return FinancialSnapshot(user, PlanningProfile(user.id, target_savings_rate=Decimal("0.2")), accounts=[
        Account(uuid4(), user.id, "Checking", AccountType.DEPOSITORY, Decimal(5000)),
    ])


def test_insights_report_actual_values_and_period_without_health_score():
    history = ActivityHistory([date(2026, 8, 1)], [
        BudgetTransactionInput("Salary", Decimal(4000), "cleared", None, type="income", posted_at=date(2026, 8, 1)),
        BudgetTransactionInput("Rent", Decimal(-2000), "cleared", None, posted_at=date(2026, 8, 1)),
    ])
    drafts = InsightService().generate(snapshot(), history)
    assert "$4,000.00" in drafts[0].text and "$2,000.00" in drafts[0].text
    assert "Aug 2026" in drafts[0].meta
    assert any("2.5 months" in d.text for d in drafts)
    assert any("50.0%" in d.text and "20.0%" in d.text for d in drafts)
    assert not any("Equities" in d.text for d in drafts)


def test_insights_do_not_invent_savings_or_liquidity_with_no_history():
    drafts = InsightService().generate(snapshot(), ActivityHistory([], []))
    assert len(drafts) == 1
    assert "need a completed month" in drafts[0].text
    assert "No urgent issues" not in drafts[0].text
