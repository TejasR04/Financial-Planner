from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ActivitySummaryResponse(BaseModel):
    history_start: date | None
    months: list[date]
    month_count: int
    period_start: date | None
    period_end: date | None
    label: str
    average_monthly_income: Decimal | None
    average_monthly_expenses: Decimal | None
    average_monthly_surplus: Decimal | None
