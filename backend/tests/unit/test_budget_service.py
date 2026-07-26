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
    assert uncategorized_spent == Decimal("10")
    assert uncategorized_pending == Decimal("0")
    assert uncategorized_count == 1
