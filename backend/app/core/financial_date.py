from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def financial_today() -> date:
    """Calendar day used for financial records, independent of server UTC time."""
    return datetime.now(ZoneInfo(get_settings().financial_timezone)).date()
