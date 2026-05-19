"""
Unit tests for dynamic daily goal calculation
"""
import unittest
from src.services.daily_task_service import compute_daily_goal_from_instances


class TestDailyGoal(unittest.TestCase):
    def test_empty_day(self):
        self.assertEqual(compute_daily_goal_from_instances([]), 0)

    def test_single_tier_sums_all(self):
        instances = [
            {'points': 100},
            {'points': 100, 'abandoned': True},
            {'points': 100, 'completed': True},
        ]
        self.assertEqual(compute_daily_goal_from_instances(instances), 300)

    def test_multiple_tiers_only_top(self):
        instances = [
            {'points': 100},
            {'points': 100},
            {'points': 50},
            {'points': 50},
            {'points': 50},
        ]
        self.assertEqual(compute_daily_goal_from_instances(instances), 200)

    def test_five_hundred_pt_example(self):
        instances = [{'points': 100}] * 5 + [{'points': 50}] * 3
        self.assertEqual(compute_daily_goal_from_instances(instances), 500)

    def test_negative_top_tier_clamped_to_zero(self):
        instances = [
            {'points': -10},
            {'points': -10},
            {'points': -50},
        ]
        self.assertEqual(compute_daily_goal_from_instances(instances), 0)

    def test_mixed_positive_negative_uses_numeric_max(self):
        instances = [
            {'points': 100},
            {'points': -200},
        ]
        self.assertEqual(compute_daily_goal_from_instances(instances), 100)

    def test_missing_points_treated_as_zero(self):
        instances = [{'description': 'no points field'}]
        self.assertEqual(compute_daily_goal_from_instances(instances), 0)

    def test_backup_tasks_excluded(self):
        instances = [
            {'points': 100},
            {'points': 100},
            {'points': 100, 'is_backup': True},
            {'points': 100, 'is_backup': True},
        ]
        self.assertEqual(compute_daily_goal_from_instances(instances), 200)

    def test_only_backups_yields_zero(self):
        instances = [{'points': 100, 'is_backup': True}] * 3
        self.assertEqual(compute_daily_goal_from_instances(instances), 0)


if __name__ == '__main__':
    unittest.main()
