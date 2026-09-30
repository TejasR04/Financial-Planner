from datetime import date, datetime, timezone
from decimal import Decimal

from app.api.v1.routes.investments import _display_history
from app.core import financial_date


def test_financial_today_uses_configured_timezone(monkeypatch):
    class AfterMidnightUtc(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 27, 2, 0, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(financial_date, "datetime", AfterMidnightUtc)
    assert financial_date.financial_today() == date(2026, 9, 26)


def test_investment_history_does_not_show_a_future_server_date():
    today = date(2026, 9, 26)
    future = date(2026, 9, 27)
    assert [(point.date, point.value) for point in _display_history(
        [(today, Decimal("100")), (future, Decimal("90"))], today
    )] == [(today, Decimal("100"))]
    assert [(point.date, point.value) for point in _display_history(
        [(future, Decimal("90"))], today
    )] == [(today, Decimal("90"))]
