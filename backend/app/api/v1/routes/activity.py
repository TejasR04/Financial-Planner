from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.activity_history import load_budget_activity_summary
from app.schemas.activity import ActivitySummaryResponse

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/summary", response_model=ActivitySummaryResponse)
async def get_activity_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivitySummaryResponse:
    """Return the authoritative completed-month window and cash-flow averages."""
    history, (income, expenses) = await load_budget_activity_summary(db, current_user.id)
    if not history.months:
        return ActivitySummaryResponse(
            history_start=history.history_start,
            months=[],
            month_count=0,
            period_start=None,
            period_end=None,
            label=history.label,
            average_monthly_income=None,
            average_monthly_expenses=None,
            average_monthly_surplus=None,
        )

    return ActivitySummaryResponse(
        history_start=history.history_start,
        months=history.months,
        month_count=len(history.months),
        period_start=history.months[0],
        period_end=history.months[-1],
        label=history.label,
        average_monthly_income=income,
        average_monthly_expenses=expenses,
        average_monthly_surplus=income - expenses,
    )
