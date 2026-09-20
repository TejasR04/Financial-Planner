from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.repositories.budget_repository import BudgetRepository
from app.services.activity_history import ActivityHistory, ActivityRule, completed_months, shift_month
from app.services.budget_service import BudgetTransactionInput


async def load_activity_history(session: AsyncSession, user_id: UUID, reference: date | None = None) -> ActivityHistory:
    today = date.today()
    repo = BudgetRepository(session)
    history_start = await repo.history_start(user_id)
    months = completed_months(history_start, reference or today, today)
    if not months:
        return ActivityHistory([], [], history_start)
    rows = await repo.expense_transactions_for_month(user_id, months[0], shift_month(months[-1], 1) - timedelta(days=1))
    return ActivityHistory(months, [
        BudgetTransactionInput(row.merchant, row.amount, row.status, row.budget_category_id,
                               row.type, row.ignored_from_budget, row.category, row.posted_at,
                               row.reviewed_at)
        for row in rows
    ], history_start)


async def load_budget_activity_summary(
    session: AsyncSession, user_id: UUID, reference: date | None = None
) -> tuple[ActivityHistory, tuple[Decimal, Decimal]]:
    """Load history plus a read-only, virtually classified budget cash flow."""
    history = await load_activity_history(session, user_id, reference)
    repo = BudgetRepository(session)
    categories = [(row.id, row.name) for row in await repo.list_categories(user_id) if row.active]
    rules = [
        ActivityRule(
            merchant_pattern=rule.merchant_pattern,
            budget_category_id=(
                rule.budget_category_id
                if category is not None and category.active
                else None
            ),
            transaction_type=rule.transaction_type,
        )
        for rule, category in await repo.list_rules(user_id)
        if rule.transaction_type is not None
        or (rule.budget_category_id is not None and category is not None and category.active)
    ]
    return history, history.budget_monthly_cash_flow(categories, rules)
