"""
Unit tests for effective weekday and days_of_week validation (travel day).
"""
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

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


class TestUpdateDailyTask(unittest.TestCase):
    def setUp(self):
        self.app_manager = MagicMock()
        self.app_manager.logger = MagicMock()
        self.app_manager.db = MagicMock()
        self.service = DailyTaskService(self.app_manager)
        self.service.central_tz = __import__('pytz').timezone('US/Central')

    @patch('src.services.daily_task_service.handle_exception')
    def test_update_daily_task_not_found(self, mock_handle):
        def raise_exc(e, ctx=""):
            raise e
        mock_handle.side_effect = raise_exc

        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        doc_ref = MagicMock()
        col.document.return_value = doc_ref
        doc = MagicMock()
        doc.exists = False
        doc_ref.get.return_value = doc

        from src.utils.exceptions import NotFoundError
        with self.assertRaises(NotFoundError):
            self.service.update_daily_task("missing_id", {"points": 10}, "test_user")

    @patch('src.services.daily_task_service.handle_exception')
    def test_update_daily_task_unauthorized(self, mock_handle):
        def raise_exc(e, ctx=""):
            raise e
        mock_handle.side_effect = raise_exc

        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        doc_ref = MagicMock()
        col.document.return_value = doc_ref
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"username": "other_user"}
        doc_ref.get.return_value = doc

        from src.utils.exceptions import UnauthorizedError
        with self.assertRaises(UnauthorizedError):
            self.service.update_daily_task("task_id", {"points": 10}, "test_user")

    @patch('src.services.daily_task_service.handle_exception')
    def test_update_daily_task_invalid_points_zero(self, mock_handle):
        def raise_exc(e, ctx=""):
            raise e
        mock_handle.side_effect = raise_exc

        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        doc_ref = MagicMock()
        col.document.return_value = doc_ref
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"username": "test_user"}
        doc_ref.get.return_value = doc

        from src.utils.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.service.update_daily_task("task_id", {"points": 0}, "test_user")

    @patch('src.services.daily_task_service.handle_exception')
    def test_update_daily_task_invalid_points_out_of_bounds(self, mock_handle):
        def raise_exc(e, ctx=""):
            raise e
        mock_handle.side_effect = raise_exc

        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        doc_ref = MagicMock()
        col.document.return_value = doc_ref
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"username": "test_user"}
        doc_ref.get.return_value = doc

        from src.utils.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.service.update_daily_task("task_id", {"points": 101}, "test_user")

    @patch('src.services.daily_task_service.handle_exception')
    def test_update_daily_task_invalid_days_of_week_empty(self, mock_handle):
        def raise_exc(e, ctx=""):
            raise e
        mock_handle.side_effect = raise_exc

        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        doc_ref = MagicMock()
        col.document.return_value = doc_ref
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"username": "test_user"}
        doc_ref.get.return_value = doc

        from src.utils.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.service.update_daily_task("task_id", {"days_of_week": []}, "test_user")

    @patch('src.services.daily_task_service.handle_exception')
    def test_update_daily_task_invalid_days_of_week_out_of_range(self, mock_handle):
        def raise_exc(e, ctx=""):
            raise e
        mock_handle.side_effect = raise_exc

        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        doc_ref = MagicMock()
        col.document.return_value = doc_ref
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"username": "test_user"}
        doc_ref.get.return_value = doc

        from src.utils.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.service.update_daily_task("task_id", {"days_of_week": [8]}, "test_user")

    def test_update_daily_task_success(self):
        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        doc_ref = MagicMock()
        col.document.return_value = doc_ref
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"username": "test_user", "description": "old description"}
        doc_ref.get.return_value = doc

        # Mock the instance query
        instance_query = MagicMock()
        col.where.return_value = instance_query
        instance_query.stream.return_value = []

        result = self.service.update_daily_task(
            "task_id",
            {"description": "new description", "points": 10, "days_of_week": [1, 2]},
            "test_user"
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message"], "Daily task updated successfully")


if __name__ == '__main__':
    unittest.main()
