"""Tests for task points streak/today paths (stored thresholds on locked days)."""
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from src.services.task_points_service import TaskPointsService


class TestTaskPointsStreak(unittest.TestCase):
    def setUp(self):
        self.app_manager = MagicMock()
        self.app_manager.logger = MagicMock()
        self.app_manager.db = MagicMock()
        self.service = TaskPointsService(self.app_manager, daily_task_service=None)
        self.service.central_tz = __import__('pytz').timezone('US/Central')

    def test_get_streak_uses_live_goal_for_today(self):
        with patch.object(self.service, '_today', return_value=date(2026, 5, 20)):
            with patch.object(self.service, '_compute_streak_from_daily', return_value=3):
                with patch.object(
                    self.service,
                    'get_daily_points_and_threshold',
                    return_value=(15, 100),
                ):
                    result = self.service.get_streak('test_user')

        self.assertEqual(result['current_streak'], 3)
        self.assertEqual(result['streak_threshold'], 100)

    def test_get_today_summary_below_minimum(self):
        today = date.today()
        with patch.object(self.service, '_today', return_value=today):
            with patch.object(
                self.service, '_get_spouse_username', return_value='spouse_user'
            ):
                with patch.object(
                    self.service,
                    'get_daily_points_and_threshold',
                    side_effect=[(5, 10), (12, 10)],
                ):
                    result = self.service.get_today_summary('test_user')

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['today_points']['test_user'], 5)
        self.assertEqual(result['today_points']['spouse_user'], 12)
        self.assertIn('test_user', result['below_minimum'])
        self.assertNotIn('spouse_user', result['below_minimum'])

    def test_locked_day_without_threshold_returns_none(self):
        today = date(2026, 5, 20)
        yesterday = today - timedelta(days=1)
        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        col.document.return_value.get.return_value = MagicMock(exists=False)

        with patch.object(self.service, '_today', return_value=today):
            pts, thresh = self.service.get_daily_points_and_threshold('user', yesterday)

        self.assertEqual(pts, 0)
        self.assertIsNone(thresh)

    def test_active_day_always_computes_goal(self):
        today = date(2026, 5, 20)
        col = MagicMock()
        self.app_manager.db.collection.return_value = col
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {'points_earned': 5, 'streak_threshold': 999}
        col.document.return_value.get.return_value = doc

        with patch.object(self.service, '_today', return_value=today):
            with patch.object(self.service, 'get_daily_goal', return_value=50) as mock_goal:
                pts, thresh = self.service.get_daily_points_and_threshold('user', today)

        mock_goal.assert_called_once_with('user', today)
        self.assertEqual(pts, 5)
        self.assertEqual(thresh, 50)

    def test_compute_streak_breaks_on_missing_threshold(self):
        today = date(2026, 5, 20)
        yesterday = today - timedelta(days=1)
        col = MagicMock()
        self.app_manager.db.collection.return_value = col

        doc = MagicMock()
        doc.exists = True
        doc.id = f'user_{yesterday.isoformat()}'
        doc.to_dict.return_value = {'points_earned': 10, 'streak_threshold': None}

        self.app_manager.db.get_all.return_value = [doc]

        with patch.object(self.service, '_today', return_value=today):
            count = self.service._compute_streak_from_daily('user')

        self.assertEqual(count, 0)

    def test_compute_streak_counts_locked_days(self):
        today = date(2026, 5, 20)
        yesterday = today - timedelta(days=1)
        two_days = today - timedelta(days=2)
        col = MagicMock()
        self.app_manager.db.collection.return_value = col

        def make_doc(day, points, thresh):
            doc = MagicMock()
            doc.exists = True
            doc.id = f'user_{day.isoformat()}'
            doc.to_dict.return_value = {
                'points_earned': points,
                'streak_threshold': thresh,
            }
            return doc

        self.app_manager.db.get_all.return_value = [
            make_doc(yesterday, 10, 10),
            make_doc(two_days, 0, 10),
        ]

        with patch.object(self.service, '_today', return_value=today):
            count = self.service._compute_streak_from_daily('user')

        self.assertEqual(count, 1)

    def test_lock_daily_threshold_skips_today_and_future(self):
        today = date(2026, 5, 20)
        col = MagicMock()
        self.app_manager.db.collection.return_value = col

        with patch.object(self.service, '_today', return_value=today):
            self.service.lock_daily_threshold_for_date('user', today)
            self.service.lock_daily_threshold_for_date('user', today + timedelta(days=1))

        col.document.return_value.set.assert_not_called()


if __name__ == '__main__':
    unittest.main()
