from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.services.budget_service import (
    BudgetCategoryInput,
    BudgetService,
    BudgetTransactionInput,
    MerchantRuleInput,
)


def test_manual_assignment_wins_over_merchant_rule_and_pending_is_separate():
    groceries_id = uuid4()
    subscriptions_id = uuid4()
    categories = [
        BudgetCategoryInput(groceries_id, "Groceries", "Needs", Decimal("600"), True),
        BudgetCategoryInput(subscriptions_id, "Subscriptions", "Wants", Decimal("50"), True),
    ]
    rules = [MerchantRuleInput(subscriptions_id, "netflix")]
    transactions = [
        BudgetTransactionInput("Netflix", Decimal("-15"), "cleared", None),
        BudgetTransactionInput("Netflix", Decimal("-20"), "cleared", groceries_id),
        BudgetTransactionInput("Netflix", Decimal("-15"), "pending", None),
        BudgetTransactionInput("Unknown merchant", Decimal("-10"), "cleared", None),
    ]

    rollups, uncategorized_spent, uncategorized_pending, uncategorized_count = BudgetService().summarize(
        categories, rules, transactions, date(2026, 7, 1), today=date(2026, 7, 20)
    )
    by_category = {row.budget_category_id: row for row in rollups}

    assert by_category[groceries_id].spent == Decimal("20")
    assert by_category[subscriptions_id].spent == Decimal("15")
    assert by_category[subscriptions_id].pending == Decimal("15")
    assert by_category[subscriptions_id].remaining == Decimal("20")
    assert by_category[subscriptions_id].forecast == Decimal("46.50")
    assert uncategorized_spent == Decimal("10")
    assert uncategorized_pending == Decimal("0")
    assert uncategorized_count == 1


def test_refunds_reimbursements_and_exclusions_reconcile():
    from app.services.budget_service import reconcile_budget
    category_id = uuid4()
    rows = [
        BudgetTransactionInput("Store", Decimal("-100"), "cleared", category_id),
        BudgetTransactionInput("Refund", Decimal("20"), "cleared", category_id),
        BudgetTransactionInput("Shared meal", Decimal("15"), "pending", category_id, "transfer"),
        BudgetTransactionInput("Own transfer", Decimal("1000"), "cleared", None, "transfer"),
        BudgetTransactionInput("Salary", Decimal("2000"), "cleared", category_id, "income"),
        BudgetTransactionInput("Excluded", Decimal("-10"), "cleared", category_id, ignored_from_budget=True),
        BudgetTransactionInput("PAYMENT - BILT", Decimal("-100"), "cleared", category_id),
        BudgetTransactionInput("Uncategorized", Decimal("-5"), "cleared", None),
    ]
    result = reconcile_budget(rows)
    assert result == {"cash_flow_expenses": Decimal("95"), "excluded_expenses": Decimal("10"),
                      "reimbursements": Decimal("15"), "budget_spending": Decimal("70"), "pending": Decimal("-15")}
    rollups, unassigned, _, _ = BudgetService().summarize(
        [BudgetCategoryInput(category_id, "Shopping", "Wants", Decimal("100"), True)], [], rows, date(2026, 7, 1))
    assert rollups[0].spent + rollups[0].pending + unassigned == result["budget_spending"]


def test_cumulative_spending_stops_at_today_and_preserves_refunds():
    from app.services.budget_service import cumulative_spending
    rows = [BudgetTransactionInput("Purchase", Decimal("-100"), "cleared", None, posted_at=date(2026, 9, 1)),
            BudgetTransactionInput("Refund", Decimal("20"), "cleared", None, posted_at=date(2026, 9, 3))]
    series = cumulative_spending(rows, date(2026, 9, 1), date(2026, 9, 3), date(2026, 1, 1))
    assert series[:4] == [Decimal("100"), Decimal("100"), Decimal("80"), None]
    assert len(series) == 30


def test_cumulative_spending_distinguishes_missing_history_and_zero_activity():
    from app.services.budget_service import cumulative_spending
    assert cumulative_spending([], date(2024, 2, 1), date(2024, 3, 1), None) == [None] * 29
    assert cumulative_spending([], date(2024, 2, 1), date(2024, 3, 1), date(2024, 1, 1)) == [Decimal(0)] * 29
