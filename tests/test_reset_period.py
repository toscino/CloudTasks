"""Unit tests for reset period helpers."""
import unittest
from datetime import date, datetime, timedelta

import pytz

from src.utils.reset_period import (
    RESET_HOUR,
    get_reset_day,
    get_reset_period_bounds,
    get_reset_time_on,
)


class TestResetPeriod(unittest.TestCase):
    def setUp(self):
        self.tz = pytz.timezone("America/Chicago")

    def test_reset_hour_is_four(self):
        self.assertEqual(RESET_HOUR, 4)

    def test_before_4am_returns_yesterday(self):
        now = self.tz.localize(datetime(2026, 6, 10, 3, 30))
        self.assertEqual(get_reset_day(now, tz=self.tz), date(2026, 6, 9))

    def test_at_4am_returns_today(self):
        now = self.tz.localize(datetime(2026, 6, 10, 4, 0))
        self.assertEqual(get_reset_day(now, tz=self.tz), date(2026, 6, 10))

    def test_after_4am_returns_today(self):
        now = self.tz.localize(datetime(2026, 6, 10, 15, 0))
        self.assertEqual(get_reset_day(now, tz=self.tz), date(2026, 6, 10))

    def test_period_bounds_span_4am_to_4am(self):
        reset_day = date(2026, 6, 9)
        start, end = get_reset_period_bounds(reset_day, tz=self.tz)
        self.assertEqual(start, self.tz.localize(datetime(2026, 6, 9, 4, 0)))
        self.assertEqual(end, self.tz.localize(datetime(2026, 6, 10, 4, 0)))

    def test_reset_time_on_matches_period_start(self):
        reset_day = date(2026, 6, 9)
        start, _ = get_reset_period_bounds(reset_day, tz=self.tz)
        self.assertEqual(get_reset_time_on(reset_day, tz=self.tz), start)


class TestDailyResetGate(unittest.TestCase):
    """check_and_reset_daily_tasks should not reset before period boundary."""

    def setUp(self):
        self.tz = pytz.timezone("America/Chicago")

    def test_330am_still_yesterday_period(self):
        now = self.tz.localize(datetime(2026, 6, 10, 3, 30))
        reset_day = get_reset_day(now, tz=self.tz)
        self.assertEqual(reset_day, date(2026, 6, 9))
        self.assertEqual(reset_day.isoformat(), "2026-06-09")


if __name__ == "__main__":
    unittest.main()
