"""
Unit tests for performance reward helpers (no Firestore).
"""
import unittest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
import pytz
from src.services.performance_reward_service import (
    PerformanceRewardService,
    missed_reset_dates,
)
from src.models.performance_reward import compute_performance_band, TOP_BAND_INDEX


class TestDaysRemaining(unittest.TestCase):
    def setUp(self):
        self.svc = PerformanceRewardService.__new__(PerformanceRewardService)
        self.svc.central_tz = pytz.timezone("America/Chicago")

    def _item_expiring(self, reset_date: date) -> dict:
        expires = self.svc._reset_time_on(reset_date + timedelta(days=2))
        return {"expires_at": expires, "created_at_reset_date": reset_date.isoformat()}

    def test_two_days_on_create_day(self):
        reset_day = date(2025, 5, 22)
        now = self.svc.central_tz.localize(datetime(2025, 5, 22, 10, 0))
        self.assertEqual(self.svc.days_remaining(self._item_expiring(reset_day), now), 2)

    def test_one_day_before_expiry(self):
        reset_day = date(2025, 5, 22)
        now = self.svc.central_tz.localize(datetime(2025, 5, 23, 15, 0))
        self.assertEqual(self.svc.days_remaining(self._item_expiring(reset_day), now), 1)

    def test_zero_after_expire_reset_day(self):
        reset_day = date(2025, 5, 22)
        now = self.svc.central_tz.localize(datetime(2025, 5, 25, 10, 0))
        self.assertEqual(self.svc.days_remaining(self._item_expiring(reset_day), now), 0)

    def test_last_morning_before_third_2am(self):
        reset_day = date(2025, 5, 22)
        now = self.svc.central_tz.localize(datetime(2025, 5, 24, 1, 30))
        self.assertEqual(self.svc.days_remaining(self._item_expiring(reset_day), now), 1)

    def test_expire_boundary_not_rolling_48h(self):
        """Late reset run time does not push expiry — fixed 2am on R+2."""
        reset_day = date(2025, 5, 22)
        exp = self.svc.expire_at_for_created_reset(reset_day)
        self.assertEqual(exp, self.svc.central_tz.localize(datetime(2025, 5, 24, 2, 0)))
        late_create_moment = self.svc.central_tz.localize(datetime(2025, 5, 22, 2, 47))
        self.assertLess(late_create_moment, exp)
        self.assertGreater(
            exp,
            self.svc.central_tz.localize(datetime(2025, 5, 24, 1, 59)),
        )


class TestEarnedRewardConfigs(unittest.TestCase):
    def test_top_band_independent_slots(self):
        from src.models.performance_reward import earned_reward_configs
        tier = {
            "reward_slots": [
                {"item_text": "A", "owed_conversion_points": 3, "assign_to": "self"},
                {"item_text": "B", "owed_conversion_points": 7, "assign_to": "spouse"},
            ],
        }
        configs = earned_reward_configs(tier, TOP_BAND_INDEX)
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0]["owed_conversion_points"], 3)
        self.assertEqual(configs[1]["assign_to"], "spouse")
        self.assertEqual(configs[1]["owed_conversion_points"], 7)

    def test_top_band_skips_empty_second(self):
        from src.models.performance_reward import earned_reward_configs
        tier = {
            "reward_slots": [
                {"item_text": "Only", "owed_conversion_points": 1, "assign_to": "self"},
                {"item_text": "", "owed_conversion_points": 9, "assign_to": "spouse"},
            ],
        }
        self.assertEqual(len(earned_reward_configs(tier, TOP_BAND_INDEX)), 1)

    def test_single_slot_band(self):
        from src.models.performance_reward import earned_reward_configs
        tier = {
            "reward_slots": [
                {"item_text": "Mid reward", "owed_conversion_points": 2, "assign_to": "spouse"},
            ],
        }
        configs = earned_reward_configs(tier, 2)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["assign_to"], "spouse")


class TestBandIntegration(unittest.TestCase):
    def test_highest_band_only_usage(self):
        self.assertEqual(compute_performance_band(999, 500), 3)
        self.assertEqual(compute_performance_band(1000, 500), 4)
        self.assertEqual(compute_performance_band(800, 500), 3)
        self.assertEqual(compute_performance_band(650, 500), 2)


class TestConvertToOwedPoints(unittest.TestCase):
    def setUp(self):
        self.svc = PerformanceRewardService.__new__(PerformanceRewardService)
        self.svc.logger = MagicMock()
        self.svc.db = MagicMock()

    def test_credits_assignee_and_writes_ledger(self):
        owed_doc = MagicMock()
        owed_doc.exists = True
        owed_doc.to_dict.return_value = {"balance": 5}
        owed_ref = MagicMock()
        owed_ref.get.return_value = owed_doc
        ledger_col = MagicMock()
        self.svc.db.collection.side_effect = lambda name: {
            "owed_points_balance": MagicMock(document=MagicMock(return_value=owed_ref)),
            "owed_points_ledger": ledger_col,
        }[name]

        item = {
            "assignee_username": "ian",
            "owed_conversion_points": 20,
            "band_index": 2,
            "earner_username": "karleigh",
            "earned_for_date": "2025-05-21",
        }
        self.svc.convert_to_owed_points(item, "karleigh_2025-05-21")

        owed_ref.set.assert_called_once()
        args, kwargs = owed_ref.set.call_args
        self.assertEqual(args[0]["balance"], 25)
        ledger_col.add.assert_called_once()
        ledger_entry = ledger_col.add.call_args[0][0]
        self.assertEqual(ledger_entry["amount"], 20)
        self.assertEqual(ledger_entry["source_item_id"], "karleigh_2025-05-21")

    def test_skips_zero_or_missing_assignee(self):
        self.svc.convert_to_owed_points({"assignee_username": "ian", "owed_conversion_points": 0}, "x")
        self.svc.db.collection.assert_not_called()


class TestExpireDueItems(unittest.TestCase):
    def setUp(self):
        self.svc = PerformanceRewardService.__new__(PerformanceRewardService)
        self.svc.logger = MagicMock()
        self.svc.central_tz = pytz.timezone("America/Chicago")
        self.svc.db = MagicMock()

    def test_expires_on_third_reset_day_regardless_of_clock(self):
        doc = MagicMock()
        doc.id = "ian_2025-05-18"
        doc.to_dict.return_value = {
            "status": "pending",
            "created_at_reset_date": "2025-05-20",
            "assignee_username": "ian",
            "owed_conversion_points": 10,
        }
        doc.reference = MagicMock()
        query = MagicMock()
        query.stream.return_value = [doc]
        self.svc.db.collection.return_value.where.return_value = query

        with patch.object(self.svc, "convert_to_owed_points") as convert:
            count = self.svc.expire_due_items(date(2025, 5, 22))
        self.assertEqual(count, 1)
        convert.assert_called_once_with(doc.to_dict.return_value, doc.id)

    def test_does_not_expire_before_third_reset_day(self):
        doc = MagicMock()
        doc.to_dict.return_value = {
            "status": "pending",
            "created_at_reset_date": "2025-05-20",
        }
        query = MagicMock()
        query.stream.return_value = [doc]
        self.svc.db.collection.return_value.where.return_value = query

        with patch.object(self.svc, "convert_to_owed_points") as convert:
            count = self.svc.expire_due_items(date(2025, 5, 21))
        self.assertEqual(count, 0)
        convert.assert_not_called()


class TestMissedResetDates(unittest.TestCase):
    def test_no_gap_when_last_is_yesterday(self):
        last = date(2025, 5, 19)
        today = date(2025, 5, 20)
        self.assertEqual(missed_reset_dates(last, today), [])

    def test_one_missed_day(self):
        last = date(2025, 5, 19)
        today = date(2025, 5, 21)
        self.assertEqual(missed_reset_dates(last, today), [date(2025, 5, 20)])

    def test_two_missed_days(self):
        last = date(2025, 5, 19)
        today = date(2025, 5, 22)
        self.assertEqual(
            missed_reset_dates(last, today),
            [date(2025, 5, 20), date(2025, 5, 21)],
        )


class TestProcessMissedResetRewards(unittest.TestCase):
    def setUp(self):
        self.svc = PerformanceRewardService.__new__(PerformanceRewardService)
        self.svc.logger = MagicMock()
        self.svc.central_tz = pytz.timezone("America/Chicago")
        self.svc.db = MagicMock()

    def test_skips_when_no_last_reset(self):
        with patch.object(self.svc, "get_last_reset_date", return_value=None):
            with patch.object(self.svc, "create_item_for_earned_day") as create:
                self.svc.process_missed_reset_rewards("ian", date(2025, 5, 21))
        create.assert_not_called()

    def test_gap_one_full_credit_with_missed_reset_day(self):
        last = date(2025, 5, 19)
        today = date(2025, 5, 21)
        missed = missed_reset_dates(last, today)
        with patch.object(self.svc, "get_last_reset_date", return_value=last):
            with patch.object(self.svc, "create_item_for_earned_day") as create:
                with patch.object(self.svc, "credit_owed_for_earned_day") as owed:
                    with patch.object(self.svc, "easiest_for_earned_day") as easy:
                        self.svc.process_missed_reset_rewards("ian", today)
        create.assert_called_once_with(
            "ian", date(2025, 5, 19), reset_day=missed[0]
        )
        owed.assert_not_called()
        easy.assert_not_called()

    def test_gap_one_catch_up_shows_one_day_remaining(self):
        reset_day = date(2025, 5, 20)
        now = self.svc.central_tz.localize(datetime(2025, 5, 21, 12, 0))
        item = {
            "created_at_reset_date": reset_day.isoformat(),
            "expires_at": self.svc.expire_at_for_created_reset(reset_day),
        }
        self.assertEqual(self.svc.days_remaining(item, now), 1)

    def test_gap_two_owed_for_primary_and_easiest_for_rest(self):
        last = date(2025, 5, 19)
        today = date(2025, 5, 22)
        with patch.object(self.svc, "get_last_reset_date", return_value=last):
            with patch.object(self.svc, "create_item_for_earned_day") as create:
                with patch.object(self.svc, "credit_owed_for_earned_day") as owed:
                    with patch.object(self.svc, "easiest_for_earned_day") as easy:
                        self.svc.process_missed_reset_rewards("ian", today)
        create.assert_not_called()
        owed.assert_called_once_with(
            "ian",
            date(2025, 5, 19),
            reason="missed_reset_2025-05-19",
        )
        easy.assert_called_once_with("ian", date(2025, 5, 20))


class TestCreditOwedForEarnedDay(unittest.TestCase):
    def setUp(self):
        self.svc = PerformanceRewardService.__new__(PerformanceRewardService)
        self.svc.logger = MagicMock()
        self.svc.db = MagicMock()
        self.svc.app_manager = MagicMock()

    def test_skips_when_bonus_item_exists(self):
        with patch.object(self.svc, "_has_bonus_for_earn_day", return_value=True):
            with patch.object(self.svc, "_credit_owed_balance") as credit:
                result = self.svc.credit_owed_for_earned_day(
                    "ian", date(2025, 5, 19), "missed_reset_2025-05-19"
                )
        self.assertFalse(result)
        credit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
