"""Unit tests for the weekly interest feature on the owed points balance."""
import unittest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta
import pytz
from src.services.performance_reward_service import PerformanceRewardService

class TestOwedInterest(unittest.TestCase):
    def setUp(self):
        self.svc = PerformanceRewardService.__new__(PerformanceRewardService)
        self.svc.logger = MagicMock()
        self.svc.db = MagicMock()
        self.svc.COL_OWED = "owed_points_balance"
        self.svc.COL_LEDGER = "owed_points_ledger"
        self.svc.central_tz = pytz.timezone("America/Chicago")

    def mock_db(self, balance=0, ledger_exists=False):
        # Mock Owed Balance Document
        owed_doc = MagicMock()
        owed_doc.exists = (balance is not None)
        if balance is not None:
            owed_doc.to_dict.return_value = {"balance": balance}
        owed_ref = MagicMock()
        owed_ref.get.return_value = owed_doc

        # Mock Ledger Document
        ledger_doc = MagicMock()
        ledger_doc.exists = ledger_exists
        ledger_doc_ref = MagicMock()
        ledger_doc_ref.get.return_value = ledger_doc
        ledger_ref = MagicMock()
        ledger_ref.document.return_value = ledger_doc_ref

        # Mock DB Collection Routing
        def col_side_effect(name):
            if name == self.svc.COL_OWED:
                return MagicMock(document=MagicMock(return_value=owed_ref))
            elif name == self.svc.COL_LEDGER:
                return ledger_ref
            raise ValueError(f"Unknown collection {name}")

        self.svc.db.collection.side_effect = col_side_effect
        return owed_ref, ledger_ref, ledger_doc_ref

    def test_apply_interest_not_monday(self):
        # Tuesday
        reset_day = date(2026, 6, 9)  # 2026-06-09 is a Tuesday
        self.mock_db(balance=10)

        self.svc.apply_interest_for_date("ian", reset_day)

        # DB should not be called since it is not Monday
        self.svc.db.collection.assert_not_called()

    def test_apply_interest_already_applied(self):
        # Monday
        reset_day = date(2026, 6, 8)  # 2026-06-08 is a Monday
        owed_ref, _, ledger_doc_ref = self.mock_db(balance=10, ledger_exists=True)

        self.svc.apply_interest_for_date("ian", reset_day)

        # Should verify ledger exists but not write updates or set values
        self.svc.db.collection.assert_called_with(self.svc.COL_LEDGER)
        owed_ref.set.assert_not_called()
        ledger_doc_ref.set.assert_not_called()

    def test_apply_interest_no_balance_document(self):
        # Monday, user has no balance document in Firestore (so balance defaults to 0)
        reset_day = date(2026, 6, 8)
        owed_ref, ledger_ref, ledger_doc_ref = self.mock_db(balance=None, ledger_exists=False)

        self.svc.apply_interest_for_date("ian", reset_day)

        # Interest is 0, so owed document is not written
        owed_ref.set.assert_not_called()

        # Ledger recorded with amount 0
        ledger_ref.document.assert_called_with(f"interest_ian_2026-06-08")
        ledger_doc_ref.set.assert_called_once()
        ledger_data = ledger_doc_ref.set.call_args[0][0]
        self.assertEqual(ledger_data["amount"], 0)
        self.assertEqual(ledger_data["balance_before"], 0)
        self.assertEqual(ledger_data["balance_after"], 0)

    def test_apply_interest_under_five_is_zero(self):
        # Monday
        reset_day = date(2026, 6, 8)
        owed_ref, ledger_ref, ledger_doc_ref = self.mock_db(balance=4, ledger_exists=False)

        self.svc.apply_interest_for_date("ian", reset_day)

        # Owed balance is under 5, so no update to COL_OWED (no set call)
        owed_ref.set.assert_not_called()

        # But should still record 0 interest to the ledger
        ledger_ref.document.assert_called_with(f"interest_ian_2026-06-08")
        ledger_doc_ref.set.assert_called_once()
        ledger_data = ledger_doc_ref.set.call_args[0][0]
        self.assertEqual(ledger_data["amount"], 0)
        self.assertEqual(ledger_data["balance_before"], 4)
        self.assertEqual(ledger_data["balance_after"], 4)

    def test_apply_interest_exactly_five_is_one(self):
        # Monday
        reset_day = date(2026, 6, 8)
        owed_ref, ledger_ref, ledger_doc_ref = self.mock_db(balance=5, ledger_exists=False)

        self.svc.apply_interest_for_date("ian", reset_day)

        # Owed balance updated: 5 + 1 = 6
        owed_ref.set.assert_called_once()
        self.assertEqual(owed_ref.set.call_args[0][0]["balance"], 6)

        # Ledger recorded
        ledger_ref.document.assert_called_with(f"interest_ian_2026-06-08")
        ledger_doc_ref.set.assert_called_once()
        ledger_data = ledger_doc_ref.set.call_args[0][0]
        self.assertEqual(ledger_data["amount"], 1)
        self.assertEqual(ledger_data["balance_before"], 5)
        self.assertEqual(ledger_data["balance_after"], 6)

    def test_apply_interest_rounding_up(self):
        # Test math.ceil logic for various values on Monday
        reset_day = date(2026, 6, 8)

        # balance = 6 -> 1 interest (total 7)
        owed_ref, _, _ = self.mock_db(balance=6, ledger_exists=False)
        self.svc.apply_interest_for_date("ian", reset_day)
        self.assertEqual(owed_ref.set.call_args[0][0]["balance"], 7)

        # balance = 10 -> 1 interest (total 11)
        owed_ref, _, _ = self.mock_db(balance=10, ledger_exists=False)
        self.svc.apply_interest_for_date("ian", reset_day)
        self.assertEqual(owed_ref.set.call_args[0][0]["balance"], 11)

        # balance = 11 -> 2 interest (total 13)
        owed_ref, _, _ = self.mock_db(balance=11, ledger_exists=False)
        self.svc.apply_interest_for_date("ian", reset_day)
        self.assertEqual(owed_ref.set.call_args[0][0]["balance"], 13)

    def test_process_missed_resets_applies_interest(self):
        # We missed Sunday and Monday, and today is Tuesday
        last_reset = date(2026, 6, 6)  # Saturday
        today = date(2026, 6, 9)       # Tuesday
        
        # Missed dates: Sunday 2026-06-07 (not Monday), Monday 2026-06-08 (is Monday)
        with patch.object(self.svc, "get_last_reset_date", return_value=last_reset):
            with patch.object(self.svc, "apply_interest_for_date") as mock_apply:
                with patch.object(self.svc, "easiest_for_earned_day"):
                    with patch.object(self.svc, "credit_owed_for_earned_day"):
                        self.svc.process_missed_reset_rewards("ian", today)

        # Verify apply_interest_for_date was called for both missed days
        self.assertEqual(mock_apply.call_count, 2)
        mock_apply.assert_any_call("ian", date(2026, 6, 7))
        mock_apply.assert_any_call("ian", date(2026, 6, 8))

if __name__ == "__main__":
    unittest.main()
