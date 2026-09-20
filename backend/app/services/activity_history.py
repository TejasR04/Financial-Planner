"""Shared completed-month window for spending, outlooks, and financial checks."""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.domain.cash_flow import cash_flow_amounts, is_card_payment
from app.domain.category_mapping import match_existing_category
from app.domain.merchant_rules import merchant_matches_rule
from app.services.budget_service import BudgetTransactionInput, cumulative_spending

ZERO = Decimal("0")


@dataclass(frozen=True)
class ActivityRule:
    merchant_pattern: str
    budget_category_id: UUID | None
    transaction_type: str | None


def shift_month(month: date, offset: int) -> date:
    index = month.year * 12 + month.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def completed_months(history_start: date | None, reference: date, today: date) -> list[date]:
    """Exclude the selected/current month and the first partially imported month.

    Transaction dates are a coverage proxy, not a guarantee of complete bank
    history. Zero-activity months inside that window still count in the mean.
    """
    if history_start is None:
        return []
    end = min(reference.replace(day=1), today.replace(day=1))
    first = shift_month(history_start, int(history_start.day != 1))
    start = max(first, shift_month(end, -12))
    months = []
    while start < end:
        months.append(start)
        start = shift_month(start, 1)
    return months


@dataclass(frozen=True)
class ActivityHistory:
    months: list[date]
    transactions: list[BudgetTransactionInput]
    history_start: date | None = None

    @property
    def label(self) -> str:
        if not self.months:
            return "No completed months of history"
        return (f"{len(self.months)} completed month{'s' if len(self.months) != 1 else ''} "
                f"({self.months[0]:%b %Y} to {self.months[-1]:%b %Y})")

    @property
    def monthly_cash_flow(self) -> tuple[Decimal, Decimal]:
        income = expenses = ZERO
        included = set(self.months)
        for row in self.transactions:
            if row.posted_at is None or row.posted_at.replace(day=1) not in included:
                continue
            earned, spent = cash_flow_amounts(row.type, row.amount, row.provider_category, row.merchant)
            income += earned
            expenses += spent
        divisor = max(1, len(self.months))
        return income / divisor, expenses / divisor

    def budget_monthly_cash_flow(
        self,
        active_categories: list[tuple[UUID, str]],
        rules: list[ActivityRule],
    ) -> tuple[Decimal, Decimal]:
        """Average classified income and categorized budget spending.

        Income includes only positive transactions explicitly classified as
        income. Spending includes categorized expenses/refunds and categorized
        transfers, while honoring budget exclusions and card-payment detection.
        """
        income = expenses = ZERO
        included = set(self.months)
        active_category_ids = {category_id for category_id, _ in active_categories}
        for row in self.transactions:
            if row.posted_at is None or row.posted_at.replace(day=1) not in included:
                continue
            effective_type = row.type
            category_id = (
                row.budget_category_id
                if row.budget_category_id in active_category_ids
                else None
            )
            can_apply_defaults = row.budget_category_id is None and row.reviewed_at is None
            if can_apply_defaults and not row.ignored_from_budget:
                for rule in rules:
                    if not merchant_matches_rule(row.merchant, rule.merchant_pattern):
                        continue
                    if rule.budget_category_id is not None:
                        category_id = (
                            rule.budget_category_id
                            if rule.budget_category_id in active_category_ids
                            else None
                        )
                    elif rule.transaction_type is not None:
                        effective_type = rule.transaction_type
                        category_id = None
                if category_id is None and effective_type == "expense":
                    category_id = match_existing_category(row.provider_category, active_categories)
            if (
                effective_type == "income"
                and row.amount > ZERO
                and not is_card_payment(effective_type, row.provider_category, row.merchant)
            ):
                income += row.amount
            if (
                category_id is not None
                and not row.ignored_from_budget
                and not is_card_payment(effective_type, row.provider_category, row.merchant)
                and effective_type in {"expense", "transfer"}
            ):
                expenses += -row.amount
        divisor = max(1, len(self.months))
        return income / divisor, expenses / divisor

    def average_spending_curve(self, reference: date) -> list[Decimal | None]:
        days = monthrange(reference.year, reference.month)[1]
        if not self.months:
            return [None] * days
        curves = [cumulative_spending(self.transactions, month, shift_month(month, 1), month)
                  for month in self.months]
        # Carry February's closing balance through days 29-31, so every day
        # uses the same denominator rather than dropping shorter months.
        return [(sum((curve[min(day, len(curve) - 1)] or ZERO for curve in curves), ZERO)
                 / len(curves)).quantize(Decimal("0.01")) for day in range(days)]
