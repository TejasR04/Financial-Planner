from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.services.activity_history import ActivityHistory, ActivityRule, completed_months
from app.services.budget_service import BudgetTransactionInput


def row(day, amount, kind="expense", **kwargs):
    category_id = kwargs.pop("budget_category_id", None)
    merchant = kwargs.pop("merchant", "Merchant")
    return BudgetTransactionInput(merchant, Decimal(amount), "cleared", category_id,
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


def test_budget_cashflow_uses_classified_income_and_categorized_net_spending():
    category_id = uuid4()
    history = ActivityHistory([date(2026, 8, 1)], [
        row("2026-08-01", "6000", "income"),
        row("2026-08-02", "100", "income"),
        row("2026-08-03", "-2000", budget_category_id=category_id),
        row("2026-08-04", "200", budget_category_id=category_id),
        row("2026-08-05", "-500"),
        row("2026-08-06", "-300", "transfer", budget_category_id=category_id),
        row("2026-08-07", "50", "transfer", budget_category_id=category_id),
        row("2026-08-08", "-100", budget_category_id=category_id, ignored_from_budget=True),
        row("2026-08-09", "-100", "credit_card_payment", budget_category_id=category_id),
        row("2026-08-10", "-100", budget_category_id=category_id,
            provider_category="LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"),
    ])

    assert history.budget_monthly_cash_flow([(category_id, "Living")], []) == (
        Decimal("6100"), Decimal("2050")
    )


def test_budget_cashflow_resolves_defaults_without_mutating_transactions():
    dining_id = uuid4()
    travel_id = uuid4()
    provider_default = row(
        "2026-08-03", "-40", provider_category="FOOD_AND_DRINK_RESTAURANT"
    )
    merchant_default = BudgetTransactionInput(
        "Airline Transfer", Decimal("-60"), "cleared", None,
        type="transfer", posted_at=date(2026, 8, 4),
    )
    reviewed_unassigned = BudgetTransactionInput(
        "Restaurant", Decimal("-100"), "cleared", None,
        provider_category="FOOD_AND_DRINK_RESTAURANT", posted_at=date(2026, 8, 5),
        reviewed_at=datetime.now(timezone.utc),
    )
    history = ActivityHistory(
        [date(2026, 8, 1)],
        [provider_default, merchant_default, reviewed_unassigned],
    )

    result = history.budget_monthly_cash_flow(
        [(dining_id, "Dining"), (travel_id, "Travel")],
        [ActivityRule("airline transfer", travel_id, None)],
    )

    assert result == (Decimal("0"), Decimal("100"))
    assert provider_default.budget_category_id is None
    assert merchant_default.budget_category_id is None


def test_budget_cashflow_applies_type_rules_and_preserves_explicit_category_state():
    active_id = uuid4()
    inactive_id = uuid4()
    rows = [
        row("2026-08-01", "500", merchant="Employer Payroll"),
        row("2026-08-02", "250", "income", merchant="Payment - Bilt"),
        row("2026-08-03", "-75", budget_category_id=inactive_id,
            provider_category="FOOD_AND_DRINK_RESTAURANT"),
        row("2026-08-04", "700", "income", ignored_from_budget=True),
    ]
    history = ActivityHistory([date(2026, 8, 1)], rows)

    result = history.budget_monthly_cash_flow(
        [(active_id, "Dining")],
        [ActivityRule("employer payroll", None, "income")],
    )

    # Type rule classifies payroll as income, card-like income is excluded,
    # inactive explicit categories are not reassigned, and ignored salary is
    # still income because ignored_from_budget applies only to spending.
    assert result == (Decimal("1200"), Decimal("0"))


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
