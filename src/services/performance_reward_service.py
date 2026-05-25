"""
Performance reward service — daily band bonuses, owed points, tier settings.
"""
import random
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta, time
from typing import Optional, List, Dict, Any
from src.models.performance_reward import (
    compute_performance_band,
    band_cutoffs_for_goal,
    default_tier_settings,
    earned_reward_configs,
    normalize_reward_slot,
    prepare_tier_for_client,
    slot_count_for_band,
    MIN_GOAL_FOR_BANDS,
    TOP_BAND_INDEX,
)
from src.utils.config import get_timezone
from src.utils.error_handlers import handle_exception


def missed_reset_dates(last_reset: date, today: date) -> List[date]:
    """Calendar reset days M where last_reset < M < today."""
    missed: List[date] = []
    d = last_reset + timedelta(days=1)
    while d < today:
        missed.append(d)
        d += timedelta(days=1)
    return missed


class PerformanceRewardService:
    """Daily performance bonuses and owed points."""

    COL_TIERS = "performance_tier_settings"
    COL_ITEMS = "performance_bonus_items"
    COL_OWED = "owed_points_balance"
    COL_LEDGER = "owed_points_ledger"

    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()

    def _now(self) -> datetime:
        return datetime.now(self.central_tz)

    def _today(self) -> date:
        return self._now().date()

    def _reset_time_on(self, d: date) -> datetime:
        dt = datetime.combine(d, time(2, 0))
        return self.central_tz.localize(dt)

    def expire_on_reset_date(self, created_reset_date: date) -> date:
        """Calendar day when the 3rd 2am reset removes the item (R+2)."""
        return created_reset_date + timedelta(days=2)

    def expire_at_for_created_reset(self, created_reset_date: date) -> datetime:
        """Stored 2am timestamp on expire day (audit only; expiry runs on reset)."""
        return self._reset_time_on(self.expire_on_reset_date(created_reset_date))

    def _created_reset_date(self, item_data: Dict[str, Any]) -> Optional[date]:
        created_str = item_data.get("created_at_reset_date")
        if not created_str:
            return None
        return date.fromisoformat(created_str)

    def should_expire_on_reset(self, today_central: date, item_data: Dict[str, Any]) -> bool:
        """True when today's daily reset should convert this pending item."""
        created = self._created_reset_date(item_data)
        if created is None:
            return False
        return today_central >= self.expire_on_reset_date(created)

    def _expire_pending_doc(self, doc, data: Dict[str, Any]) -> None:
        """Convert to owed points and mark expired (idempotent for non-pending)."""
        if data.get("status") != "pending":
            return
        self.convert_to_owed_points(data, doc.id)
        doc.reference.update({
            "status": "expired",
            "expired_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

    def get_couple_id(self, username: str) -> Optional[str]:
        task_points = getattr(self.app_manager, "task_points_service", None)
        if task_points:
            return task_points.get_couple_id(username)
        return username

    def _get_spouse_username(self, username: str) -> Optional[str]:
        user_service = getattr(self.app_manager, "user_service", None)
        if user_service:
            settings = user_service.get_user_settings(username)
            return settings.get("spouse_username")
        user_doc = self.db.collection("users").document(username).get()
        if user_doc.exists:
            return user_doc.to_dict().get("spouse_username")
        return None

    def resolve_assignee(self, earner_username: str, assign_to: str) -> str:
        if assign_to == "spouse":
            spouse = self._get_spouse_username(earner_username)
            if spouse:
                return spouse
        return earner_username

    def get_tier_settings(self, username: str) -> Dict[str, Any]:
        """Get this user's tier settings (creates defaults if missing)."""
        try:
            ref = self.db.collection(self.COL_TIERS).document(username)
            doc = ref.get()
            if doc.exists:
                data = doc.to_dict()
                tiers = data.get("tiers", default_tier_settings())
            else:
                tiers = default_tier_settings()
                ref.set({
                    "username": username,
                    "tiers": tiers,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                })

            tiers = [prepare_tier_for_client(t) for t in tiers]
            return {"status": "success", "username": username, "tiers": tiers}
        except Exception as e:
            return handle_exception(e, "Failed to get tier settings")

    def save_tier_settings(self, username: str, tiers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save tier settings for the logged-in user only."""
        try:
            if len(tiers) != 5:
                return {"status": "error", "message": "Expected exactly 5 tiers"}

            normalized = []
            for i, t in enumerate(sorted(tiers, key=lambda x: x.get("band_index", 0))):
                kind = t.get("kind", "reward" if i > 0 else "consequence")
                count = slot_count_for_band(i)
                slots = [normalize_reward_slot(s) for s in t.get("reward_slots", [])[:count]]
                while len(slots) < count:
                    slots.append(normalize_reward_slot({}))
                normalized.append({
                    "band_index": i,
                    "label": str(t.get("label", f"Tier {i}"))[:80],
                    "kind": kind,
                    "reward_slots": slots[:count],
                })

            self.db.collection(self.COL_TIERS).document(username).set({
                "username": username,
                "tiers": normalized,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)

            client_tiers = [prepare_tier_for_client(t) for t in normalized]
            return {"status": "success", "message": "Tier settings saved", "username": username, "tiers": client_tiers}
        except Exception as e:
            return handle_exception(e, "Failed to save tier settings")

    def get_band_preview(self, username: str) -> Dict[str, Any]:
        """Today's goal and band cutoffs for user and spouse."""
        try:
            task_points = getattr(self.app_manager, "task_points_service", None)
            today = self._today()
            users = [username]
            spouse = self._get_spouse_username(username)
            if spouse:
                users.append(spouse)

            previews = {}
            for u in users:
                goal = 0
                if task_points:
                    goal = task_points.get_daily_goal(u, today)
                cutoffs = band_cutoffs_for_goal(goal)
                previews[u] = {"goal": goal, "cutoffs": cutoffs, "skipped": goal < MIN_GOAL_FOR_BANDS}

            return {"status": "success", "previews": previews}
        except Exception as e:
            return handle_exception(e, "Failed to get band preview")

    def _item_doc_id(self, earner_username: str, earned_for_date: date, slot: int = 0) -> str:
        base = f"{earner_username}_{earned_for_date.isoformat()}"
        return base if slot == 0 else f"{base}_2"

    def _write_bonus_item(
        self,
        item_id: str,
        *,
        earner_username: str,
        assignee: str,
        couple_id: Optional[str],
        band: int,
        kind: str,
        description: str,
        owed_conversion_points: int,
        earned_for_date: date,
        reset_day: date,
        expires_at: datetime,
        points: int,
        goal: int,
        slot: int,
    ) -> None:
        self.db.collection(self.COL_ITEMS).document(item_id).set({
            "earner_username": earner_username,
            "assignee_username": assignee,
            "couple_id": couple_id,
            "band_index": band,
            "kind": kind,
            "description": description,
            "owed_conversion_points": owed_conversion_points,
            "earned_for_date": earned_for_date.isoformat(),
            "created_at_reset_date": reset_day.isoformat(),
            "expires_at": expires_at,
            "status": "pending",
            "points_snapshot": points,
            "goal_snapshot": goal,
            "reward_slot": slot,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

    def convert_to_owed_points(self, item_data: Dict[str, Any], item_id: str) -> None:
        assignee = item_data.get("assignee_username")
        amount = int(item_data.get("owed_conversion_points", 0))
        if not assignee or amount <= 0:
            return

        owed_ref = self.db.collection(self.COL_OWED).document(assignee)
        owed_doc = owed_ref.get()
        balance = 0
        if owed_doc.exists:
            balance = int(owed_doc.to_dict().get("balance", 0))
        owed_ref.set({
            "username": assignee,
            "balance": balance + amount,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        self.db.collection(self.COL_LEDGER).add({
            "username": assignee,
            "amount": amount,
            "source_item_id": item_id,
            "band_index": item_data.get("band_index"),
            "earner_username": item_data.get("earner_username"),
            "earned_for_date": item_data.get("earned_for_date"),
            "created_at": firestore.SERVER_TIMESTAMP,
        })

    def expire_due_items(self, today_central: date) -> int:
        """
        Expire pending items during the daily reset only (not on task list reads).
        Uses reset calendar day: created on R, expire when reset runs on R+2 or later.
        See docs/DAILY_RESET_BEHAVIOR.md.
        """
        expired_count = 0
        try:
            query = self.db.collection(self.COL_ITEMS).where(
                filter=FieldFilter("status", "==", "pending")
            )
            for doc in query.stream():
                data = doc.to_dict()
                if not self.should_expire_on_reset(today_central, data):
                    continue
                self._expire_pending_doc(doc, data)
                expired_count += 1
            if expired_count:
                self.logger.info(f"Expired {expired_count} performance bonus items")
        except Exception as e:
            self.logger.error(f"Failed to expire performance bonus items: {e}")
        return expired_count

    def get_last_reset_date(self, username: str) -> Optional[date]:
        """Latest daily_task_resets.last_reset_date for user, or None."""
        try:
            query = self.db.collection("daily_task_resets").where(
                filter=FieldFilter("username", "==", username)
            )
            best: Optional[date] = None
            for doc in query.stream():
                raw = doc.to_dict().get("last_reset_date")
                if not raw:
                    continue
                d = date.fromisoformat(raw)
                if best is None or d > best:
                    best = d
            return best
        except Exception as e:
            self.logger.error(f"Failed to read last_reset_date for {username}: {e}")
            return None

    def _lock_earn_day_if_needed(self, earner_username: str, earn_day: date) -> None:
        task_points = getattr(self.app_manager, "task_points_service", None)
        if task_points:
            task_points.lock_daily_threshold_for_date(earner_username, earn_day)

    def _points_and_goal_for_earn_day(
        self, earner_username: str, earn_day: date
    ) -> tuple[int, int]:
        daily_key = f"{earner_username}_{earn_day.isoformat()}"
        daily_doc = self.db.collection("task_points_daily").document(daily_key).get()
        points = 0
        goal = None
        if daily_doc.exists:
            d = daily_doc.to_dict()
            points = int(d.get("points_earned", 0))
            goal = d.get("streak_threshold")

        if goal is None:
            task_points = getattr(self.app_manager, "task_points_service", None)
            if task_points:
                goal = task_points.get_daily_goal(earner_username, earn_day)
            else:
                goal = 0
        return points, int(goal or 0)

    def _tier_for_band(self, earner_username: str, band: int) -> Optional[Dict[str, Any]]:
        settings = self.get_tier_settings(earner_username)
        if settings.get("status") != "success":
            return None
        tiers = settings.get("tiers", default_tier_settings())
        return tiers[band] if band < len(tiers) else tiers[-1]

    def _has_bonus_for_earn_day(self, earner_username: str, earn_day: date) -> bool:
        for slot in (0, 1):
            doc_id = self._item_doc_id(earner_username, earn_day, slot)
            if self.db.collection(self.COL_ITEMS).document(doc_id).get().exists:
                return True
        return False

    def _ledger_exists(self, ledger_id: str) -> bool:
        return self.db.collection(self.COL_LEDGER).document(ledger_id).get().exists

    def _credit_owed_balance(
        self,
        assignee: str,
        amount: int,
        *,
        ledger_id: str,
        earner_username: str,
        earned_for_date: date,
        band_index: int,
        source: str,
    ) -> bool:
        if not assignee or amount <= 0:
            return False
        if self._ledger_exists(ledger_id):
            return False

        owed_ref = self.db.collection(self.COL_OWED).document(assignee)
        owed_doc = owed_ref.get()
        balance = int(owed_doc.to_dict().get("balance", 0)) if owed_doc.exists else 0
        owed_ref.set({
            "username": assignee,
            "balance": balance + amount,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        self.db.collection(self.COL_LEDGER).document(ledger_id).set({
            "username": assignee,
            "amount": amount,
            "source": source,
            "band_index": band_index,
            "earner_username": earner_username,
            "earned_for_date": earned_for_date.isoformat(),
            "created_at": firestore.SERVER_TIMESTAMP,
        })
        return True

    def _get_owed_balance(self, username: str) -> int:
        doc = self.db.collection(self.COL_OWED).document(username).get()
        return int(doc.to_dict().get("balance", 0)) if doc.exists else 0

    @staticmethod
    def minimum_dice_roll_points(owed_balance: int) -> int:
        """Min points a roll must score: +5 per full 10 owed (0 if owed < 10)."""
        owed = max(0, int(owed_balance))
        return (owed // 10) * 5

    def debit_owed_for_dice_roll(
        self, username: str, amount: int, *, roll_id: str
    ) -> Dict[str, Any]:
        """Subtract owed balance for a dice roll (idempotent per roll_id)."""
        try:
            if not username:
                return {"status": "error", "message": "Username required"}
            amount = int(amount)
            if amount <= 0:
                balance = self._get_owed_balance(username)
                return {
                    "status": "success",
                    "points_subtracted": 0,
                    "owed_balance_before": balance,
                    "owed_balance_after": balance,
                }

            ledger_id = f"dice_roll_{roll_id}"
            balance_before = self._get_owed_balance(username)
            if self._ledger_exists(ledger_id):
                return {
                    "status": "success",
                    "points_subtracted": 0,
                    "owed_balance_before": balance_before,
                    "owed_balance_after": balance_before,
                }

            points_subtracted = min(amount, balance_before)
            balance_after = balance_before - points_subtracted

            owed_ref = self.db.collection(self.COL_OWED).document(username)
            owed_ref.set({
                "username": username,
                "balance": balance_after,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)

            self.db.collection(self.COL_LEDGER).document(ledger_id).set({
                "username": username,
                "amount": -points_subtracted,
                "source": "dice_roll",
                "roll_id": roll_id,
                "created_at": firestore.SERVER_TIMESTAMP,
            })

            return {
                "status": "success",
                "points_subtracted": points_subtracted,
                "owed_balance_before": balance_before,
                "owed_balance_after": balance_after,
            }
        except Exception as e:
            return handle_exception(e, "Failed to debit owed points for dice roll")

    def create_item_for_earned_day(
        self,
        earner_username: str,
        earn_day: date,
        reset_day: date,
    ) -> bool:
        """Create pending bonus item(s) for an earn day; reset_day sets expiry calendar."""
        try:
            if self._has_bonus_for_earn_day(earner_username, earn_day):
                return False

            self._lock_earn_day_if_needed(earner_username, earn_day)
            points, goal = self._points_and_goal_for_earn_day(earner_username, earn_day)
            band = compute_performance_band(points, goal)
            if band is None:
                return False

            tier = self._tier_for_band(earner_username, band)
            if tier is None:
                return False

            configs = earned_reward_configs(tier, band)
            if not configs:
                return False

            expires_at = self.expire_at_for_created_reset(reset_day)
            kind = tier.get("kind", "reward")
            couple_id = self.get_couple_id(earner_username)

            created = False
            for slot, cfg in enumerate(configs):
                doc_id = self._item_doc_id(earner_username, earn_day, slot)
                item_ref = self.db.collection(self.COL_ITEMS).document(doc_id)
                if item_ref.get().exists:
                    continue
                assignee = self.resolve_assignee(earner_username, cfg["assign_to"])
                self._write_bonus_item(
                    doc_id,
                    earner_username=earner_username,
                    assignee=assignee,
                    couple_id=couple_id,
                    band=band,
                    kind=kind,
                    description=cfg["item_text"],
                    owed_conversion_points=cfg["owed_conversion_points"],
                    earned_for_date=earn_day,
                    reset_day=reset_day,
                    expires_at=expires_at,
                    points=points,
                    goal=goal,
                    slot=slot,
                )
                created = True
                self.logger.info(
                    f"Created performance bonus {doc_id} for {earner_username} "
                    f"(assignee={assignee}, band={band}, slot={slot}, "
                    f"reset_day={reset_day}, owed={cfg['owed_conversion_points']})"
                )
            return created
        except Exception as e:
            self.logger.error(
                f"Failed to create performance bonus for {earner_username} "
                f"earn_day={earn_day}: {e}"
            )
            return False

    def create_item_for_yesterday(self, earner_username: str, today_central: date) -> bool:
        """Create bonus item(s) from yesterday's locked points if applicable."""
        yesterday = today_central - timedelta(days=1)
        return self.create_item_for_earned_day(
            earner_username, yesterday, reset_day=today_central
        )

    def credit_owed_for_earned_day(
        self,
        earner_username: str,
        earn_day: date,
        reason: str,
    ) -> bool:
        """Band math → owed balance + ledger; no pending list item."""
        try:
            if self._has_bonus_for_earn_day(earner_username, earn_day):
                return False

            self._lock_earn_day_if_needed(earner_username, earn_day)
            points, goal = self._points_and_goal_for_earn_day(earner_username, earn_day)
            band = compute_performance_band(points, goal)
            if band is None:
                return False

            tier = self._tier_for_band(earner_username, band)
            if tier is None:
                return False

            configs = earned_reward_configs(tier, band)
            if not configs:
                return False

            credited = False
            for slot, cfg in enumerate(configs):
                amount = int(cfg["owed_conversion_points"])
                if amount <= 0:
                    continue
                ledger_id = f"{reason}_{earner_username}_{earn_day.isoformat()}"
                if slot > 0:
                    ledger_id += "_2"
                assignee = self.resolve_assignee(earner_username, cfg["assign_to"])
                if self._credit_owed_balance(
                    assignee,
                    amount,
                    ledger_id=ledger_id,
                    earner_username=earner_username,
                    earned_for_date=earn_day,
                    band_index=band,
                    source=reason,
                ):
                    credited = True
                    self.logger.info(
                        f"Credited {amount} owed to {assignee} for {earner_username} "
                        f"earn_day={earn_day} ({reason})"
                    )
            return credited
        except Exception as e:
            self.logger.error(
                f"Failed to credit owed for {earner_username} earn_day={earn_day}: {e}"
            )
            return False

    def easiest_for_earned_day(self, earner_username: str, earn_day: date) -> bool:
        """Empty/minimal earn day: band-0 owed only, ledger only."""
        try:
            reason = f"easiest_{earn_day.isoformat()}"
            base_ledger = f"{reason}_{earner_username}"
            if self._ledger_exists(base_ledger) or self._ledger_exists(f"{base_ledger}_2"):
                return False
            if self._has_bonus_for_earn_day(earner_username, earn_day):
                return False

            self._lock_earn_day_if_needed(earner_username, earn_day)
            points, goal = self._points_and_goal_for_earn_day(earner_username, earn_day)
            band = compute_performance_band(points, goal)
            if band is None:
                return False

            tier = self._tier_for_band(earner_username, 0)
            if tier is None:
                return False

            configs = earned_reward_configs(tier, 0)
            if not configs:
                return False

            credited = False
            for slot, cfg in enumerate(configs):
                amount = int(cfg["owed_conversion_points"])
                if amount <= 0:
                    continue
                ledger_id = f"{reason}_{earner_username}"
                if slot > 0:
                    ledger_id += "_2"
                assignee = self.resolve_assignee(earner_username, cfg["assign_to"])
                if self._credit_owed_balance(
                    assignee,
                    amount,
                    ledger_id=ledger_id,
                    earner_username=earner_username,
                    earned_for_date=earn_day,
                    band_index=0,
                    source=reason,
                ):
                    credited = True
            return credited
        except Exception as e:
            self.logger.error(
                f"Failed easiest path for {earner_username} earn_day={earn_day}: {e}"
            )
            return False

    def process_missed_reset_rewards(
        self, earner_username: str, today_central: date
    ) -> None:
        """
        Catch up performance rewards for skipped reset days.
        See docs/DAILY_RESET_BEHAVIOR.md.
        """
        last_reset = self.get_last_reset_date(earner_username)
        if last_reset is None:
            return

        missed = missed_reset_dates(last_reset, today_central)
        if not missed:
            return

        gap = len(missed)
        primary_earn = today_central - timedelta(days=gap + 1)

        if gap == 1:
            m = missed[0]
            earn_day = m - timedelta(days=1)
            self.create_item_for_earned_day(earner_username, earn_day, reset_day=m)
            return

        for m in missed:
            earn_day = m - timedelta(days=1)
            if earn_day == primary_earn:
                self.credit_owed_for_earned_day(
                    earner_username,
                    earn_day,
                    reason=f"missed_reset_{earn_day.isoformat()}",
                )
            else:
                self.easiest_for_earned_day(earner_username, earn_day)

    def run_reset_for_earner(self, earner_username: str, today_central: date) -> None:
        """Expire due items globally is called separately; create yesterday item for earner."""
        last_reset = self.get_last_reset_date(earner_username)
        gap = 0
        if last_reset is not None:
            gap = len(missed_reset_dates(last_reset, today_central))
        if gap == 0:
            self.create_item_for_yesterday(earner_username, today_central)
        else:
            self.easiest_for_earned_day(
                earner_username, today_central - timedelta(days=1)
            )

    def days_remaining(self, item_data: Dict[str, Any], now: Optional[datetime] = None) -> int:
        """Display only — tied to reset calendar days, not wall-clock expiry."""
        if now is None:
            now = self._now()
        created = self._created_reset_date(item_data)
        if created is None:
            return 1
        today = now.date()
        expire_day = self.expire_on_reset_date(created)
        if today <= created:
            return 2
        if today < expire_day:
            return 1
        if today == expire_day:
            return 1
        return 0

    def get_pending_bonus_items(self, assignee_username: str) -> List[Dict[str, Any]]:
        """Read pending items only; expiry happens in expire_due_items at daily reset."""
        now = self._now()
        items = []
        query = self.db.collection(self.COL_ITEMS).where(
            filter=firestore.And([
                FieldFilter("assignee_username", "==", assignee_username),
                FieldFilter("status", "==", "pending"),
            ])
        )
        for doc in query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            data["days_remaining"] = self.days_remaining(data, now)
            data["type"] = "performance_bonus"
            data["category"] = "Consequence" if data.get("kind") == "consequence" else "Reward"
            data["points"] = 0
            data["difficulty"] = 0
            data["can_abandon"] = True
            items.append(data)
        items.sort(key=lambda x: x.get("earned_for_date", ""))
        return items

    def _get_item(self, item_id: str) -> Optional[tuple]:
        ref = self.db.collection(self.COL_ITEMS).document(item_id)
        doc = ref.get()
        if not doc.exists:
            return None
        return ref, doc.to_dict()

    def complete_bonus_item(self, item_id: str, username: str) -> Dict[str, Any]:
        try:
            row = self._get_item(item_id)
            if not row:
                return {"status": "error", "message": "Item not found"}
            ref, data = row
            if data.get("assignee_username") != username:
                return {"status": "error", "message": "Unauthorized"}
            if data.get("status") != "pending":
                return {"status": "error", "message": "Item is not pending"}
            ref.update({
                "status": "completed",
                "completed_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            return {"status": "success", "message": "Bonus item completed"}
        except Exception as e:
            return handle_exception(e, "Failed to complete bonus item")

    def abandon_bonus_item(self, item_id: str, username: str) -> Dict[str, Any]:
        try:
            row = self._get_item(item_id)
            if not row:
                return {"status": "error", "message": "Item not found"}
            ref, data = row
            if data.get("assignee_username") != username:
                return {"status": "error", "message": "Unauthorized"}
            if data.get("status") != "pending":
                return {"status": "error", "message": "Item is not pending"}
            self.convert_to_owed_points(data, item_id)
            ref.update({
                "status": "expired",
                "abandoned": True,
                "expired_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            return {"status": "success", "message": "Bonus item abandoned and converted to owed points"}
        except Exception as e:
            return handle_exception(e, "Failed to abandon bonus item")

    def get_owed_points(self, username: str) -> Dict[str, Any]:
        try:
            balances = {}
            users = [username]
            spouse = self._get_spouse_username(username)
            if spouse:
                users.append(spouse)
            min_roll_points = {}
            for u in users:
                doc = self.db.collection(self.COL_OWED).document(u).get()
                bal = int(doc.to_dict().get("balance", 0)) if doc.exists else 0
                balances[u] = bal
                min_roll_points[u] = self.minimum_dice_roll_points(bal)
            return {
                "status": "success",
                "balances": balances,
                "min_roll_points": min_roll_points,
            }
        except Exception as e:
            return handle_exception(e, "Failed to get owed points")

    def create_test_bonus_item(self, assignee_username: str) -> Dict[str, Any]:
        """Create a random pending bonus item for the current user (testing)."""
        try:
            settings = self.get_tier_settings(assignee_username)
            if settings.get("status") != "success":
                return settings
            tiers = settings.get("tiers", default_tier_settings())
            band = random.randint(0, min(len(tiers) - 1, 4))
            tier = tiers[band]
            configs = earned_reward_configs(tier, band)
            if not configs:
                configs = [normalize_reward_slot({"item_text": "Test bonus item"})]
            cfg = random.choice(configs)
            today = self._today()
            item_id = f"test_{assignee_username}_{int(self._now().timestamp())}"
            expires_at = self._reset_time_on(today + timedelta(days=2))
            earner = assignee_username
            assignee = assignee_username

            self.db.collection(self.COL_ITEMS).document(item_id).set({
                "earner_username": earner,
                "assignee_username": assignee,
                "couple_id": self.get_couple_id(assignee_username),
                "band_index": band,
                "kind": tier.get("kind", "reward"),
                "description": cfg["item_text"],
                "owed_conversion_points": cfg["owed_conversion_points"],
                "earned_for_date": (today - timedelta(days=1)).isoformat(),
                "created_at_reset_date": today.isoformat(),
                "expires_at": expires_at,
                "status": "pending",
                "test_item": True,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            return {"status": "success", "message": "Test bonus item added", "item_id": item_id}
        except Exception as e:
            return handle_exception(e, "Failed to create test bonus item")

    def clear_owed_points(self, username: str) -> Dict[str, Any]:
        """Zero owed-point balances for user and spouse (testing)."""
        try:
            users = [username]
            spouse = self._get_spouse_username(username)
            if spouse:
                users.append(spouse)
            cleared = []
            for u in users:
                self.db.collection(self.COL_OWED).document(u).set({
                    "username": u,
                    "balance": 0,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }, merge=True)
                cleared.append(u)
            return {"status": "success", "message": "Owed points cleared", "cleared": cleared}
        except Exception as e:
            return handle_exception(e, "Failed to clear owed points")
