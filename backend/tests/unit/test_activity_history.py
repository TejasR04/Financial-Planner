from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.services.activity_history import ActivityHistory, completed_months
from app.services.budget_service import BudgetTransactionInput


def row(day, amount, kind="expense", **kwargs):
    return BudgetTransactionInput("Merchant", Decimal(amount), "cleared", None,
                                  type=kind, posted_at=date.fromisoformat(day), **kwargs)


def test_completed_window_excludes_partial_edges_and_caps_at_twelve_months():
    today = date(2026, 9, 17)
    assert completed_months(date(2026, 6, 15), today, today) == [date(2026, 7, 1), date(2026, 8, 1)]
    assert completed_months(date(2026, 9, 1), today, today) == []
    assert completed_months(None, today, today) == []
    months = completed_months(date(2020, 1, 1), today, today)
    assert len(months) == 12
    assert months[0] == date(2025, 9, 1)
    assert months[-1] == date(2026, 8, 1)
    assert completed_months(date(2026, 6, 1), date(2026, 8, 1), today) == [date(2026, 6, 1), date(2026, 7, 1)]
    assert completed_months(date(2026, 6, 1), date(2027, 1, 1), today)[-1] == date(2026, 8, 1)


def test_cashflow_averages_use_whole_months_including_zero_activity_and_refunds():
    history = ActivityHistory([date(2026, 7, 1), date(2026, 8, 1)], [
        row("2026-07-01", "6000", "income"), row("2026-07-02", "-2000"),
        row("2026-07-03", "200"), row("2026-07-04", "-5000", "transfer"),
        row("2026-07-05", "-1000", "credit_card_payment"),
        row("2026-07-06", "-1000", provider_category="LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"),
        row("2026-06-30", "-99999"), row("2026-09-01", "-99999"),
    ])
    assert history.monthly_cash_flow == (Decimal("3000"), Decimal("900"))


def test_spending_average_clamps_short_months_and_keeps_budget_semantics():
    transfer = BudgetTransactionInput("Reimbursement", Decimal("50"), "cleared", uuid4(),
                                     type="transfer", posted_at=date(2024, 2, 15))
    history = ActivityHistory([date(2024, 1, 1), date(2024, 2, 1)], [
        row("2024-01-02", "-100"), row("2024-01-31", "-100"),
        row("2024-02-02", "-200"), row("2024-02-29", "-100"), transfer,
        row("2024-02-01", "-999", ignored_from_budget=True),
    ])
    curve = history.average_spending_curve(date(2024, 3, 1))
    assert len(curve) == 31
    assert curve[0] == 0
    assert curve[1] == 150
    assert curve[28] == 175
    assert curve[30] == 225
    assert ActivityHistory([], []).average_spending_curve(date(2024, 2, 1)) == [None] * 29
