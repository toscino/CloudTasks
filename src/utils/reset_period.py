"""Reset period helpers (4am America/Chicago day boundary)."""
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple

import pytz

from src.utils.config import get_timezone

RESET_HOUR = 4


def get_reset_day(now: Optional[datetime] = None, tz=None) -> date:
    """Get active reset-period date (before 4am, still yesterday's period)."""
    tz = tz or get_timezone()
    now = now or datetime.now(tz)
    if now.hour < RESET_HOUR:
        return now.date() - timedelta(days=1)
    return now.date()


def get_reset_period_bounds(
    reset_day: date, tz=None
) -> Tuple[datetime, datetime]:
    """Get 4am on reset_day through 4am on reset_day + 1 (exclusive end for queries)."""
    tz = tz or get_timezone()
    start = tz.localize(datetime.combine(reset_day, time(RESET_HOUR, 0)))
    end = start + timedelta(days=1)
    return start, end


def get_reset_time_on(reset_day: date, tz=None) -> datetime:
    """Get 4am timestamp on a reset day."""
    tz = tz or get_timezone()
    return tz.localize(datetime.combine(reset_day, time(RESET_HOUR, 0)))
