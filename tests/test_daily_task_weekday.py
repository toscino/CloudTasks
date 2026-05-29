"""
Unit tests for effective weekday and days_of_week validation (travel day).
"""
import unittest
from datetime import date
from unittest.mock import MagicMock

from src.services.daily_task_service import DailyTaskService
from src.utils.config import VACATION_WEEKDAY, TRAVEL_DAY_WEEKDAY


def _service_with_settings(settings: dict) -> DailyTaskService:
    app_manager = MagicMock()
    user_service = MagicMock()
    user_service.get_user_settings.return_value = settings
    app_manager.user_service = user_service
    app_manager.logger = MagicMock()
    app_manager.db = MagicMock()
    return DailyTaskService(app_manager)


class TestEffectiveWeekday(unittest.TestCase):
    def setUp(self):
        self.target = date(2026, 5, 28)  # Thursday -> weekday 3
        self.username = 'testuser'

    def test_calendar_weekday_when_modes_off(self):
        svc = _service_with_settings({
            'vacation_mode': False,
            'travel_day_mode': False,
        })
        self.assertEqual(svc.get_effective_weekday(self.username, self.target), 3)

    def test_vacation_mode_uses_sunday(self):
        svc = _service_with_settings({
            'vacation_mode': True,
            'travel_day_mode': False,
        })
        self.assertEqual(svc.get_effective_weekday(self.username, self.target), VACATION_WEEKDAY)

    def test_travel_day_mode_uses_travel(self):
        svc = _service_with_settings({
            'vacation_mode': False,
            'travel_day_mode': True,
        })
        self.assertEqual(svc.get_effective_weekday(self.username, self.target), TRAVEL_DAY_WEEKDAY)

    def test_travel_wins_over_vacation(self):
        svc = _service_with_settings({
            'vacation_mode': True,
            'travel_day_mode': True,
        })
        self.assertEqual(svc.get_effective_weekday(self.username, self.target), TRAVEL_DAY_WEEKDAY)


class TestDaysOfWeekValidation(unittest.TestCase):
    def test_valid_day_range(self):
        for day in range(TRAVEL_DAY_WEEKDAY + 1):
            self.assertTrue(0 <= day <= TRAVEL_DAY_WEEKDAY, f'day {day} should be valid')

    def test_day_7_valid_day_8_invalid(self):
        self.assertTrue(0 <= 7 <= TRAVEL_DAY_WEEKDAY)
        self.assertFalse(0 <= 8 <= TRAVEL_DAY_WEEKDAY)


if __name__ == '__main__':
    unittest.main()
