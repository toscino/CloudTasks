"""
Unit tests for dice roll scoring and configuration normalization.
"""
import unittest
from unittest.mock import MagicMock, patch
from src.services.dice_roll_service import (
    DiceRollService,
    DEFAULT_FACE_COUNT,
    DEFAULT_POINT_VALUE,
    DEFAULT_MAX_ROLLS,
)
from src.services.performance_reward_service import PerformanceRewardService


class TestMinimumDiceRollPoints(unittest.TestCase):
    def test_formula(self):
        from src.services.performance_reward_service import PerformanceRewardService
        self.assertEqual(PerformanceRewardService.minimum_dice_roll_points(0), 0)
        self.assertEqual(PerformanceRewardService.minimum_dice_roll_points(9), 0)
        self.assertEqual(PerformanceRewardService.minimum_dice_roll_points(10), 5)
        self.assertEqual(PerformanceRewardService.minimum_dice_roll_points(30), 15)
        self.assertEqual(PerformanceRewardService.minimum_dice_roll_points(35), 15)


class TestComputeRollPoints(unittest.TestCase):
    def test_three_dice_drop_lowest(self):
        self.assertEqual(DiceRollService.compute_roll_points([2, 5, 10]), 15)

    def test_single_die_zero(self):
        self.assertEqual(DiceRollService.compute_roll_points([10]), 0)

    def test_two_dice(self):
        self.assertEqual(DiceRollService.compute_roll_points([3, 7]), 7)

    def test_empty(self):
        self.assertEqual(DiceRollService.compute_roll_points([]), 0)


class TestNormalizeOneDie(unittest.TestCase):
    def setUp(self):
        self.svc = DiceRollService.__new__(DiceRollService)
        self.couple = ["alice", "bob"]

    def test_defaults_on_empty(self):
        d = self.svc._normalize_one_die({}, self.couple)
        self.assertEqual(d["point_value"], DEFAULT_POINT_VALUE)
        self.assertEqual(d["face_count"], DEFAULT_FACE_COUNT)
        self.assertEqual(set(d["for_usernames"]), set(self.couple))
        self.assertEqual(len(d["face_rules"]), DEFAULT_FACE_COUNT)

    def test_custom_face_count(self):
        d = self.svc._normalize_one_die({"face_count": 4, "face_rules": {"1": "a"}}, self.couple)
        self.assertEqual(d["face_count"], 4)
        self.assertEqual(d["face_rules"]["1"], "a")
        self.assertEqual(d["face_rules"]["4"], "")

    def test_for_usernames_single(self):
        d = self.svc._normalize_one_die({"for_usernames": ["alice"]}, self.couple)
        self.assertEqual(d["for_usernames"], ["alice"])

    def test_max_rolls_default(self):
        d = self.svc._normalize_one_die({}, self.couple)
        self.assertEqual(d["max_rolls"], DEFAULT_MAX_ROLLS)

    def test_max_rolls_capped_by_face_count(self):
        d = self.svc._normalize_one_die({"face_count": 3, "max_rolls": 8}, self.couple)
        self.assertEqual(d["face_count"], 3)
        self.assertEqual(d["max_rolls"], 3)


class TestUniqueFacesForDie(unittest.TestCase):
    def setUp(self):
        self.svc = DiceRollService.__new__(DiceRollService)

    def test_sample_without_replacement(self):
        faces = self.svc._unique_faces_for_die(6, 3)
        self.assertEqual(len(faces), 3)
        self.assertEqual(len(set(faces)), 3)
        self.assertTrue(all(1 <= f <= 6 for f in faces))

    def test_rejects_over_face_count(self):
        with self.assertRaises(ValueError):
            self.svc._unique_faces_for_die(4, 5)


class TestExpandSelectedDice(unittest.TestCase):
    def setUp(self):
        self.svc = DiceRollService.__new__(DiceRollService)

    def test_list_form(self):
        self.assertEqual(self.svc._expand_selected_dice([0, 1, 1]), [0, 1, 1])

    def test_dict_form(self):
        self.assertEqual(self.svc._expand_selected_dice({"0": 2, "1": 1}), [0, 0, 1])


class TestAllowedDieIndices(unittest.TestCase):
    def setUp(self):
        self.svc = DiceRollService.__new__(DiceRollService)

    def test_filters_by_username(self):
        configs = {
            "die_1": {"for_usernames": ["alice"]},
            "die_2": {"for_usernames": ["bob"]},
            "die_3": {"for_usernames": ["alice", "bob"]},
        }
        keys = ["die_1", "die_2", "die_3"]
        self.assertEqual(self.svc._allowed_die_indices("alice", configs, keys), [0, 2])
        self.assertEqual(self.svc._allowed_die_indices("bob", configs, keys), [1, 2])


class TestRemainingFacesForReroll(unittest.TestCase):
    def test_three_faces_used_reroll_third_leaves_rest(self):
        instances = [
            {"die_index": 0, "face_value": 1},
            {"die_index": 0, "face_value": 2},
            {"die_index": 0, "face_value": 3},
        ]
        remaining = DiceRollService.remaining_faces_for_reroll(instances, 2, 6)
        self.assertEqual(remaining, [3, 4, 5, 6])

    def test_all_six_faces_only_current_face_left(self):
        instances = [
            {"die_index": 0, "face_value": i} for i in range(1, 7)
        ]
        remaining = DiceRollService.remaining_faces_for_reroll(instances, 0, 6)
        self.assertEqual(remaining, [1])

    def test_other_die_faces_ignored(self):
        instances = [
            {"die_index": 0, "face_value": 1},
            {"die_index": 1, "face_value": 5},
        ]
        remaining = DiceRollService.remaining_faces_for_reroll(instances, 0, 6)
        self.assertEqual(remaining, [1, 2, 3, 4, 5, 6])


class TestAnnotateRerollable(unittest.TestCase):
    def setUp(self):
        self.svc = DiceRollService.__new__(DiceRollService)

    def test_rerollable_when_faces_remain(self):
        instances = [{"die_index": 0, "face_value": 1, "title": "A", "point_value": 2}]
        configs = {"die_1": {"face_count": 6}}
        out = self.svc._annotate_instances_rerollable(
            instances, configs, ["die_1"], reroll_used=False
        )
        self.assertTrue(out[0]["rerollable"])

    def test_not_rerollable_after_reroll_used(self):
        instances = [{"die_index": 0, "face_value": 1}]
        configs = {"die_1": {"face_count": 6}}
        out = self.svc._annotate_instances_rerollable(
            instances, configs, ["die_1"], reroll_used=True
        )
        self.assertFalse(out[0]["rerollable"])

    def test_not_rerollable_when_all_faces_on_die_are_used(self):
        instances = [
            {"die_index": 0, "face_value": 1},
            {"die_index": 0, "face_value": 2},
            {"die_index": 0, "face_value": 3},
        ]
        configs = {"die_1": {"face_count": 3}}
        out = self.svc._annotate_instances_rerollable(
            instances, configs, ["die_1"], reroll_used=False
        )
        self.assertFalse(any(i["rerollable"] for i in out))


class TestGetRollHistory(unittest.TestCase):
    def setUp(self):
        self.app_manager = MagicMock()
        self.app_manager.logger = MagicMock()
        self.app_manager.db = MagicMock()
        self.svc = DiceRollService(self.app_manager, None)

    def test_returns_at_most_two_newest(self):
        from datetime import datetime, timezone

        docs = []
        for i, rid in enumerate(["old", "mid", "new"]):
            doc = MagicMock()
            doc.id = rid
            doc.to_dict.return_value = {
                "username": "alice",
                "created_at": datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                "roll_instances": [],
                "points_scored": i,
                "points_subtracted": 0,
                "owed_balance_after": 0,
                "reroll_used": False,
            }
            docs.append(doc)

        query = MagicMock()
        query.stream.return_value = docs
        col = MagicMock()
        col.where.return_value = query
        self.app_manager.db.collection.return_value = col

        result = self.svc.get_roll_history("alice", limit=2)
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["sessions"]), 2)
        self.assertEqual(result["sessions"][0]["roll_id"], "new")
        self.assertEqual(result["sessions"][1]["roll_id"], "mid")


class TestRerollOneInstance(unittest.TestCase):
    def setUp(self):
        self.app_manager = MagicMock()
        self.app_manager.logger = MagicMock()
        self.app_manager.db = MagicMock()
        self.svc = DiceRollService(self.app_manager, None)

    @patch.object(DiceRollService, "get_dice_configuration")
    @patch.object(DiceRollService, "_load_roll_session")
    def test_reroll_blocked_when_already_used(self, mock_load, mock_config):
        mock_load.return_value = {
            "roll_id": "r1",
            "username": "alice",
            "reroll_used": True,
            "roll_instances": [{"die_index": 0, "face_value": 1}],
        }
        result = self.svc.reroll_one_instance("alice", "r1", 0)
        self.assertEqual(result["status"], "error")
        self.assertIn("already used", result["message"])

    @patch.object(DiceRollService, "get_dice_configuration")
    @patch.object(DiceRollService, "_load_roll_session")
    def test_reroll_wrong_user(self, mock_load, mock_config):
        mock_load.return_value = {
            "roll_id": "r1",
            "username": "bob",
            "reroll_used": False,
            "roll_instances": [{"die_index": 0, "face_value": 1}],
        }
        result = self.svc.reroll_one_instance("alice", "r1", 0)
        self.assertEqual(result["status"], "error")

    @patch.object(DiceRollService, "get_dice_configuration")
    @patch.object(DiceRollService, "_load_roll_session")
    def test_reroll_success_marks_used(self, mock_load, mock_config):
        mock_load.return_value = {
            "roll_id": "r1",
            "username": "alice",
            "couple_id": "alice_bob",
            "reroll_used": False,
            "points_scored": 5,
            "points_subtracted": 3,
            "owed_balance_after": 2,
            "roll_instances": [
                {"die_index": 0, "face_value": 1, "face_rule": "", "title": "A", "point_value": 2},
                {"die_index": 0, "face_value": 2, "face_rule": "", "title": "A", "point_value": 2},
            ],
        }
        mock_config.return_value = {
            "status": "success",
            "dice_configs": {
                "die_1": self.svc._normalize_one_die(
                    {"face_count": 6, "face_rules": {"4": "four"}}, ["alice", "bob"]
                ),
            },
        }
        doc_ref = MagicMock()
        col = MagicMock()
        col.document.return_value = doc_ref
        self.app_manager.db.collection.return_value = col

        with patch("src.services.dice_roll_service.random.choice", return_value=4):
            result = self.svc.reroll_one_instance("alice", "r1", 0)
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["reroll_used"])
        self.assertEqual(result["roll_instances"][0]["face_value"], 4)
        self.assertFalse(any(i["rerollable"] for i in result["roll_instances"]))
        doc_ref.set.assert_called_once()


class TestRollDiceIntegration(unittest.TestCase):
    def setUp(self):
        self.app_manager = MagicMock()
        self.app_manager.logger = MagicMock()
        self.app_manager.db = MagicMock()
        self.perf = MagicMock()
        self.perf.minimum_dice_roll_points = PerformanceRewardService.minimum_dice_roll_points
        self.perf._get_owed_balance.return_value = 0
        self.svc = DiceRollService(self.app_manager, self.perf)

    @patch.object(DiceRollService, "_save_roll_session")
    @patch.object(DiceRollService, "get_couple_id", return_value="alice_bob")
    @patch.object(DiceRollService, "get_dice_configuration")
    def test_roll_subtracts_owed(self, mock_config, _couple, _save):
        mock_config.return_value = {
            "status": "success",
            "dice_configs": {
                "die_1": self.svc._normalize_one_die(
                    {"point_value": 2, "for_usernames": ["alice"]}, ["alice", "bob"]
                ),
                "die_2": self.svc._normalize_one_die(
                    {"point_value": 5, "for_usernames": ["alice"]}, ["alice", "bob"]
                ),
            },
            "couple_usernames": ["alice", "bob"],
        }
        self.perf.debit_owed_for_dice_roll.return_value = {
            "status": "success",
            "points_subtracted": 5,
            "owed_balance_before": 10,
            "owed_balance_after": 5,
        }
        with patch("src.services.dice_roll_service.random.randint", return_value=1):
            result = self.svc.roll_dice("alice", selected_dice=[0, 1])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["points_scored"], 5)
        self.assertEqual(result["points_subtracted"], 5)
        self.assertEqual(len(result["roll_instances"]), 2)
        self.assertIn("rerollable", result["roll_instances"][0])
        self.perf.debit_owed_for_dice_roll.assert_called_once()
        _save.assert_called_once()

    @patch.object(DiceRollService, "_save_roll_session")
    @patch.object(DiceRollService, "get_couple_id", return_value="alice_bob")
    @patch.object(DiceRollService, "get_dice_configuration")
    def test_rejects_spouse_only_die(self, mock_config, _couple, _save):
        mock_config.return_value = {
            "status": "success",
            "dice_configs": {
                "die_1": self.svc._normalize_one_die(
                    {"point_value": 10, "for_usernames": ["bob"]}, ["alice", "bob"]
                ),
            },
            "couple_usernames": ["alice", "bob"],
        }
        self.perf.debit_owed_for_dice_roll.return_value = {
            "status": "success",
            "points_subtracted": 0,
            "owed_balance_before": 0,
            "owed_balance_after": 0,
        }
        result = self.svc.roll_dice("alice", selected_dice=[0])
        self.assertEqual(result["status"], "error")

    @patch.object(DiceRollService, "_save_roll_session")
    @patch.object(DiceRollService, "get_couple_id", return_value="alice_bob")
    @patch.object(DiceRollService, "get_dice_configuration")
    def test_same_die_twice_gets_distinct_faces(self, mock_config, _couple, _save):
        mock_config.return_value = {
            "status": "success",
            "dice_configs": {
                "die_1": self.svc._normalize_one_die(
                    {"point_value": 2, "face_count": 6, "max_rolls": 3, "for_usernames": ["alice"]},
                    ["alice", "bob"],
                ),
            },
            "couple_usernames": ["alice", "bob"],
        }
        self.perf.debit_owed_for_dice_roll.return_value = {
            "status": "success",
            "points_subtracted": 0,
            "owed_balance_before": 0,
            "owed_balance_after": 0,
        }
        result = self.svc.roll_dice("alice", selected_dice=[0, 0])
        self.assertEqual(result["status"], "success")
        faces = [i["face_value"] for i in result["roll_instances"]]
        self.assertEqual(len(faces), 2)
        self.assertEqual(len(set(faces)), 2)

    @patch.object(DiceRollService, "_save_roll_session")
    @patch.object(DiceRollService, "get_couple_id", return_value="alice_bob")
    @patch.object(DiceRollService, "get_dice_configuration")
    def test_rejects_roll_below_minimum_for_owed(self, mock_config, _couple, _save):
        mock_config.return_value = {
            "status": "success",
            "dice_configs": {
                "die_1": self.svc._normalize_one_die(
                    {"point_value": 2, "for_usernames": ["alice"]}, ["alice", "bob"]
                ),
                "die_2": self.svc._normalize_one_die(
                    {"point_value": 3, "for_usernames": ["alice"]}, ["alice", "bob"]
                ),
            },
            "couple_usernames": ["alice", "bob"],
        }
        self.perf._get_owed_balance.return_value = 30
        result = self.svc.roll_dice("alice", selected_dice=[0])
        self.assertEqual(result["status"], "error")
        self.assertIn("at least 15", result["message"])
        _save.assert_not_called()

    @patch.object(DiceRollService, "_save_roll_session")
    @patch.object(DiceRollService, "get_couple_id", return_value="alice_bob")
    @patch.object(DiceRollService, "get_dice_configuration")
    def test_max_rolls_enforced(self, mock_config, _couple, _save):
        mock_config.return_value = {
            "status": "success",
            "dice_configs": {
                "die_1": self.svc._normalize_one_die(
                    {"point_value": 2, "max_rolls": 1, "for_usernames": ["alice"]},
                    ["alice", "bob"],
                ),
            },
            "couple_usernames": ["alice", "bob"],
        }
        result = self.svc.roll_dice("alice", selected_dice=[0, 0])
        self.assertEqual(result["status"], "error")
        self.assertIn("at most 1", result["message"])


class TestDebitOwedForDiceRoll(unittest.TestCase):
    def setUp(self):
        self.app_manager = MagicMock()
        self.app_manager.logger = MagicMock()
        self.app_manager.db = MagicMock()
        from src.services.performance_reward_service import PerformanceRewardService
        self.svc = PerformanceRewardService(self.app_manager)

    def test_caps_at_balance(self):
        owed_doc = MagicMock()
        owed_doc.exists = True
        owed_doc.to_dict.return_value = {"balance": 3}
        owed_ref = MagicMock()
        owed_ref.get.return_value = owed_doc
        ledger_col = MagicMock()
        ledger_ref = MagicMock()
        ledger_doc = MagicMock()
        ledger_doc.exists = False
        ledger_ref.get.return_value = ledger_doc
        ledger_col.document.return_value = ledger_ref
        self.app_manager.db.collection.side_effect = lambda name: {
            "owed_points_balance": MagicMock(document=MagicMock(return_value=owed_ref)),
            "owed_points_ledger": ledger_col,
        }[name]

        result = self.svc.debit_owed_for_dice_roll("alice", 10, roll_id="r1")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["points_subtracted"], 3)
        self.assertEqual(result["owed_balance_after"], 0)
