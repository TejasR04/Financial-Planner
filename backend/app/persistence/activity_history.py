from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.repositories.budget_repository import BudgetRepository
from app.services.activity_history import ActivityHistory, completed_months, shift_month
from app.services.budget_service import BudgetTransactionInput


async def load_activity_history(session: AsyncSession, user_id: UUID, reference: date | None = None) -> ActivityHistory:
    today = date.today()
    repo = BudgetRepository(session)
    months = completed_months(await repo.history_start(user_id), reference or today, today)
    if not months:
        return ActivityHistory([], [])
    rows = await repo.expense_transactions_for_month(user_id, months[0], shift_month(months[-1], 1) - timedelta(days=1))
    return ActivityHistory(months, [
        BudgetTransactionInput(row.merchant, row.amount, row.status, row.budget_category_id,
                               row.type, row.ignored_from_budget, row.category, row.posted_at)
        for row in rows
    ])
