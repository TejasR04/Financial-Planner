"""Shared completed-month window for spending, outlooks, and financial checks."""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.cash_flow import cash_flow_amounts
from app.services.budget_service import BudgetTransactionInput, cumulative_spending

ZERO = Decimal("0")


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
