"""Pure budget classification and monthly-rollup logic."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.domain.merchant_rules import merchant_matches_rule
from app.domain.cash_flow import is_card_payment, cash_flow_amounts

ZERO = Decimal("0")


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
    type: str = "expense"
    ignored_from_budget: bool = False
    provider_category: str = ""
    posted_at: date | None = None
    reviewed_at: datetime | None = None


def budget_amount(transaction: BudgetTransactionInput) -> Decimal:
    if transaction.ignored_from_budget or is_card_payment(transaction.type, transaction.provider_category, transaction.merchant):
        return ZERO
    if transaction.type == "expense":
        return -transaction.amount
    # Explicitly categorized outgoing transfers are spending; incoming ones
    # reimburse it. Unassigned transfers and salary never become spending.
    if transaction.type == "transfer" and transaction.budget_category_id:
        return -transaction.amount
    return ZERO


def reconcile_budget(transactions: list[BudgetTransactionInput]) -> dict[str, Decimal]:
    expenses = excluded = reimbursements = transfer_spending = pending = ZERO
    for transaction in transactions:
        _, expense = cash_flow_amounts(transaction.type, transaction.amount, transaction.provider_category, transaction.merchant)
        expenses += expense
        if transaction.ignored_from_budget:
            excluded += expense
        amount = budget_amount(transaction)
        if transaction.type == "transfer":
            if amount > ZERO:
                transfer_spending += amount
            else:
                reimbursements -= amount
        if transaction.status == "pending":
            pending += amount
    return {"cash_flow_expenses": expenses, "excluded_expenses": excluded,
            "reimbursements": reimbursements, "categorized_transfer_spending": transfer_spending,
            "budget_spending": expenses - excluded + transfer_spending - reimbursements,
            "pending": pending}


def cumulative_spending(transactions: list[BudgetTransactionInput], month: date, today: date,
                        history_start: date | None) -> list[Decimal | None]:
    days = calendar.monthrange(month.year, month.month)[1]
    has_history = history_start is not None and history_start <= month.replace(day=days)
    daily = {day: ZERO for day in range(1, days + 1)}
    for transaction in transactions:
        if transaction.posted_at and transaction.posted_at.year == month.year and transaction.posted_at.month == month.month:
            daily[transaction.posted_at.day] += budget_amount(transaction)
    total = ZERO
    result: list[Decimal | None] = []
    for day in range(1, days + 1):
        total += daily[day]
        result.append(total if has_history and month.replace(day=day) <= today else None)
    return result


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
        matching_rule = next((rule for rule in rules if merchant_matches_rule(transaction.merchant, rule.merchant_pattern)), None)
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
            amount = budget_amount(transaction)
            if amount == ZERO:
                continue
            category_id = self.classify_category_id(transaction, rules, category_ids)

            # Expense amounts are normalized as negative. A positive expense
            # (a provider refund) therefore reduces the category total.
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
                remaining=category.monthly_limit - totals[category.id]["spent"] - totals[category.id]["pending"],
                forecast=((totals[category.id]["spent"] + totals[category.id]["pending"]) / elapsed_days * days_in_month).quantize(Decimal("0.01")),
            )
            for category in active_categories
        ]
        return rollups, uncategorized_spent, uncategorized_pending, uncategorized_count
