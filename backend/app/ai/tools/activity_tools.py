"""Authenticated, read-only ledger tools available to Meri during a chat."""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tool_registry import registry
from app.core.financial_date import financial_today
from app.domain.category_mapping import match_existing_category
from app.persistence.repositories.budget_repository import BudgetRepository
from app.persistence.repositories.transaction_repository import TransactionRepository
from app.services.budget_service import BudgetCategoryInput, BudgetService, BudgetTransactionInput, MerchantRuleInput


@dataclass(frozen=True)
class ActivityScope:
    session: AsyncSession
    user_id: UUID


class TransactionSearchInput(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    merchant: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    transaction_type: str | None = Field(default=None, pattern="^(expense|income|transfer|contribution|credit_card_payment)$")
    limit: int = Field(default=30, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def valid_period(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    today = financial_today()
    if start is None and end is None:
        return today.replace(day=1), today
    if start is None:
        return end.replace(day=1), end
    return start, end or start


@registry.register(
    "search_transactions",
    "Search the signed-in user's saved transactions by inclusive dates, merchant, category or type. "
    "Use exact dates for a day, month boundaries for a month, and offset for more pages.",
    TransactionSearchInput,
    scoped=True,
)
async def search_transactions(args: TransactionSearchInput, scope: ActivityScope) -> dict:
    start, end = (None, None) if args.start_date is None and args.end_date is None else _period(args.start_date, args.end_date)
    filters = dict(since=start, until=end, merchant=args.merchant, category=args.category,
                   transaction_type=args.transaction_type)
    repo = TransactionRepository(scope.session)
    rows, count = await repo.list_for_user(scope.user_id, limit=args.limit, offset=args.offset, **filters)
    totals = await repo.totals_for_user(scope.user_id, **filters)
    return {
        "period": {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
                   "label": "all saved activity" if start is None else "selected dates"},
        "filters": {"merchant": args.merchant, "category": args.category, "transaction_type": args.transaction_type},
        "matching_count": count, "offset": args.offset, "returned_count": len(rows),
        "has_more": args.offset + len(rows) < count,
        "cash_flow_totals": {key: str(value) for key, value in totals.items()},
        "transactions": [{"date": row.posted_at.isoformat(), "merchant": row.merchant,
                          "amount": str(row.amount), "type": row.type.value,
                          "status": row.status.value, "category": row.category,
                          "budget_category": row.budget_category_name, "account": row.account_name}
                         for row in rows],
    }


class SpendingSummaryInput(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    category: str | None = Field(default=None, max_length=100)
    merchant: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def valid_period(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


@registry.register(
    "get_spending_summary",
    "Get complete, server-calculated income and expense totals for an inclusive date range, optionally filtered "
    "by merchant or category. Excludes transfers and card repayments from cash-flow totals.",
    SpendingSummaryInput,
    scoped=True,
)
async def get_spending_summary(args: SpendingSummaryInput, scope: ActivityScope) -> dict:
    start, end = _period(args.start_date, args.end_date)
    filters = dict(since=start, until=end, merchant=args.merchant, category=args.category)
    repo = TransactionRepository(scope.session)
    _, count = await repo.list_for_user(scope.user_id, limit=1, **filters)
    totals = await repo.totals_for_user(scope.user_id, **filters)
    return {"period": {"start": start.isoformat(), "end": end.isoformat()},
            "filters": {"category": args.category, "merchant": args.merchant},
            "matching_transaction_count": count,
            "cash_flow_totals": {key: str(value) for key, value in totals.items()}}


class BudgetSummaryInput(BaseModel):
    month: date | None = None
    category: str | None = Field(default=None, max_length=100)


@registry.register(
    "get_budget_summary",
    "Get the signed-in user's monthly budget limits, cleared and pending spending, remaining amounts, "
    "forecast, and uncategorized spending. Provide any day of the desired month.",
    BudgetSummaryInput,
    scoped=True,
)
async def get_budget_summary(args: BudgetSummaryInput, scope: ActivityScope) -> dict:
    month = (args.month or financial_today()).replace(day=1)
    end = month.replace(day=monthrange(month.year, month.month)[1])
    repo = BudgetRepository(scope.session)
    categories = await repo.list_categories(scope.user_id)
    rules = await repo.list_rules(scope.user_id)
    rows = await repo.expense_transactions_for_month(scope.user_id, month, end)
    service = BudgetService()
    category_inputs = [BudgetCategoryInput(row.id, row.name, row.group_name, row.monthly_limit, row.active)
                       for row in categories]
    rule_inputs = [MerchantRuleInput(rule.budget_category_id, rule.merchant_pattern)
                   for rule, _ in rules if rule.budget_category_id]
    active_ids = {row.id for row in categories if row.active}
    active_names = [(row.id, row.name) for row in categories if row.active]
    transaction_inputs = []
    for row in rows:
        item = BudgetTransactionInput(row.merchant, row.amount, row.status, row.budget_category_id,
                                      row.type, row.ignored_from_budget, row.category, row.posted_at)
        effective_category = service.classify_category_id(item, rule_inputs, active_ids)
        if (effective_category is None and row.type == "expense" and
                getattr(row, "reviewed_at", None) is None and not row.ignored_from_budget):
            effective_category = match_existing_category(row.category, active_names)
        transaction_inputs.append(BudgetTransactionInput(row.merchant, row.amount, row.status,
                              effective_category, row.type, row.ignored_from_budget, row.category, row.posted_at))
    rollups, uncategorized_spent, uncategorized_pending, uncategorized_count = service.summarize(
        category_inputs, rule_inputs, transaction_inputs, month, financial_today())
    if args.category:
        rollups = [row for row in rollups if args.category.casefold() in row.name.casefold()]
    return {"month": month.isoformat()[:7], "category_filter": args.category,
            "totals": {"budgeted": str(sum((row.budgeted for row in rollups), 0)),
                       "category_spent": str(sum((row.spent for row in rollups), 0)),
                       "category_pending": str(sum((row.pending for row in rollups), 0)),
                       "budget_spending": str(
                           sum((row.spent + row.pending for row in rollups), 0)
                           + (uncategorized_spent + uncategorized_pending if not args.category else 0)),
                       "includes_uncategorized": args.category is None},
            "categories": [{"name": row.name, "group": row.group_name,
                            "budgeted": str(row.budgeted), "spent": str(row.spent),
                            "pending": str(row.pending), "remaining": str(row.remaining),
                            "forecast": str(row.forecast)} for row in rollups],
            "uncategorized": {"spent": str(uncategorized_spent), "pending": str(uncategorized_pending),
                              "transaction_count": uncategorized_count} if not args.category else None}
