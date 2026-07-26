"""Pure budget classification and monthly-rollup logic."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

ZERO = Decimal("0")


def _normalize_merchant(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").split())


@dataclass(slots=True, frozen=True)
class BudgetCategoryInput:
    id: UUID
    name: str
    group_name: str
    monthly_limit: Decimal
    active: bool


@dataclass(slots=True, frozen=True)
class MerchantRuleInput:
    budget_category_id: UUID
    merchant_pattern: str


@dataclass(slots=True, frozen=True)
class BudgetTransactionInput:
    merchant: str
    amount: Decimal
    status: str
    budget_category_id: UUID | None


@dataclass(slots=True, frozen=True)
class BudgetCategoryRollup:
    budget_category_id: UUID
    name: str
    group_name: str
    budgeted: Decimal
    spent: Decimal
    pending: Decimal
    remaining: Decimal
    forecast: Decimal


class BudgetService:
    def classify_category_id(
        self,
        transaction: BudgetTransactionInput,
        rules: list[MerchantRuleInput],
        active_category_ids: set[UUID],
    ) -> UUID | None:
        if transaction.budget_category_id in active_category_ids:
            return transaction.budget_category_id
        merchant = _normalize_merchant(transaction.merchant)
        matching_rule = next((rule for rule in rules if rule.merchant_pattern in merchant), None)
        if matching_rule and matching_rule.budget_category_id in active_category_ids:
            return matching_rule.budget_category_id
        return None

    def summarize(
        self,
        categories: list[BudgetCategoryInput],
        rules: list[MerchantRuleInput],
        transactions: list[BudgetTransactionInput],
        month: date,
        today: date | None = None,
    ) -> tuple[list[BudgetCategoryRollup], Decimal, Decimal, int]:
        active_categories = [category for category in categories if category.active]
        category_ids = {category.id for category in active_categories}
        totals = {category.id: {"spent": ZERO, "pending": ZERO} for category in active_categories}
        uncategorized_spent = uncategorized_pending = ZERO
        uncategorized_count = 0

        for transaction in transactions:
            category_id = self.classify_category_id(transaction, rules, category_ids)

            # Expense amounts are normalized as negative. A positive expense
            # (a provider refund) therefore reduces the category total.
            amount = -transaction.amount
            target = totals.get(category_id) if category_id in category_ids else None
            if target is None:
                uncategorized_count += 1
                if transaction.status == "pending":
                    uncategorized_pending += amount
                else:
                    uncategorized_spent += amount
                continue
            if transaction.status == "pending":
                target["pending"] += amount
            else:
                target["spent"] += amount

        reference_date = today or date.today()
        days_in_month = calendar.monthrange(month.year, month.month)[1]
        elapsed_days = days_in_month if (reference_date.year, reference_date.month) != (month.year, month.month) else max(1, reference_date.day)
        rollups = [
            BudgetCategoryRollup(
                budget_category_id=category.id,
                name=category.name,
                group_name=category.group_name,
                budgeted=category.monthly_limit,
                spent=totals[category.id]["spent"],
                pending=totals[category.id]["pending"],
                remaining=category.monthly_limit - totals[category.id]["spent"],
                forecast=(totals[category.id]["spent"] / elapsed_days * days_in_month).quantize(Decimal("0.01")),
            )
            for category in active_categories
        ]
        return rollups, uncategorized_spent, uncategorized_pending, uncategorized_count
