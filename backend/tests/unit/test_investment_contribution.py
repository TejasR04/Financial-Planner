from datetime import date

from app.services.investment_contribution_service import (
    following_scheduled_date,
    next_scheduled_date,
)


def test_month_end_schedule_does_not_drift_after_february() -> None:
    february = following_scheduled_date(30, date(2027, 1, 30))
    assert february == date(2027, 2, 28)
    assert following_scheduled_date(30, february) == date(2027, 3, 30)


def test_next_schedule_uses_today_or_the_next_month() -> None:
    assert next_scheduled_date(15, date(2026, 9, 15)) == date(2026, 9, 15)
    assert next_scheduled_date(15, date(2026, 9, 16)) == date(2026, 10, 15)
