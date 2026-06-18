"""
Task Points Service - manages standalone task points (per-person daily, joint balance, spending, streaks)
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
from src.utils.config import get_timezone
from src.utils.reset_period import get_reset_day

if TYPE_CHECKING:
    from src.services.daily_task_service import DailyTaskService


class TaskPointsService:
    """Service for standalone task points tracking"""

    STREAK_LOOKBACK_DAYS = 400
    STREAK_BATCH_DAYS = 100

    def __init__(self, app_manager, daily_task_service: Optional['DailyTaskService'] = None):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()
        self._daily_task_service = daily_task_service

    def set_daily_task_service(self, daily_task_service: 'DailyTaskService') -> None:
        """Wire DailyTaskService after construction (avoids circular init in app.py)."""
        self._daily_task_service = daily_task_service

    def _today(self) -> date:
        return get_reset_day(tz=self.central_tz)

    def get_daily_goal(self, username: str, target_date: date) -> int:
        """Per-day goal from scheduled instances (active day reads and write paths)."""
        if self._daily_task_service:
            return self._daily_task_service.compute_daily_goal(username, target_date)
        return 0

    def add_points_on_completion(self, username: str, points: int) -> Dict[str, Any]:
        """Add points to joint balance (only excess above daily goal), update daily total, update streak"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id'}

            today = self._today()
            date_str = today.isoformat()
            threshold = self.get_daily_goal(username, today)

            daily_key = f"{username}_{date_str}"
            daily_ref = self.db.collection('task_points_daily').document(daily_key)
            daily_doc = daily_ref.get()

            if daily_doc.exists:
                daily_data = daily_doc.to_dict()
                old_daily = daily_data.get('points_earned', 0)
            else:
                old_daily = 0

            new_daily = old_daily + points
            points_for_balance = max(0, new_daily - threshold) - max(0, old_daily - threshold)

            balance_ref = self.db.collection('task_points_balance').document(couple_id)
            balance_doc = balance_ref.get()

            if balance_doc.exists:
                current = balance_doc.to_dict()
                new_balance = current.get('balance', 0) + points_for_balance
            else:
                new_balance = points_for_balance

            balance_ref.set({
                'balance': new_balance,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)

            daily_ref.set({
                'username': username,
                'date': date_str,
                'points_earned': new_daily,
                'streak_threshold': threshold,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)

            self._update_streak(username, new_daily, threshold)

            return {'status': 'success', 'points_added': points_for_balance}
        except Exception as e:
            self.logger.error(f"Failed to add points for {username}: {e}")
            return {'status': 'error', 'message': str(e)}

    def _update_streak(self, username: str, points_earned_today: int, threshold: Optional[int] = None) -> None:
        """Update streak based on today's points vs daily goal"""
        try:
            if threshold is None:
                threshold = self.get_daily_goal(username, self._today())

            streak_ref = self.db.collection('task_streaks').document(username)
            streak_doc = streak_ref.get()

            today = self._today()

            if streak_doc.exists:
                data = streak_doc.to_dict()
                last_date_str = data.get('last_streak_date')
                current_streak = data.get('current_streak', 0)

                if points_earned_today >= threshold:
                    if last_date_str:
                        last_date = date.fromisoformat(last_date_str)
                        if last_date == today:
                            pass
                        elif last_date == today - timedelta(days=1):
                            current_streak += 1
                        else:
                            current_streak = 1
                    else:
                        current_streak = 1

                    streak_ref.set({
                        'current_streak': current_streak,
                        'last_streak_date': today.isoformat(),
                        'streak_threshold': threshold,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    }, merge=True)
                else:
                    streak_ref.set({
                        'current_streak': 0,
                        'last_streak_date': today.isoformat(),
                        'streak_threshold': threshold,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    }, merge=True)
            else:
                if points_earned_today >= threshold:
                    streak_ref.set({
                        'current_streak': 1,
                        'last_streak_date': today.isoformat(),
                        'streak_threshold': threshold,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    }, merge=True)
        except Exception as e:
            self.logger.error(f"Failed to update streak for {username}: {e}")

    def spend_points(self, username: str, amount: int, description: str = '') -> Dict[str, Any]:
        """Subtract points from joint balance and record spending"""
        try:
            if amount <= 0:
                return {'status': 'error', 'message': 'Amount must be positive'}

            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id'}

            balance_ref = self.db.collection('task_points_balance').document(couple_id)
            balance_doc = balance_ref.get()

            if not balance_doc.exists:
                current_balance = 0
            else:
                current_balance = balance_doc.to_dict().get('balance', 0)

            if current_balance < amount:
                return {'status': 'error', 'message': 'Insufficient points balance'}

            new_balance = current_balance - amount

            balance_ref.set({
                'balance': new_balance,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)

            self.db.collection('task_points_spending').add({
                'couple_id': couple_id,
                'amount': amount,
                'description': description or '',
                'username': username,
                'created_at': firestore.SERVER_TIMESTAMP
            })

            return {'status': 'success', 'new_balance': new_balance}
        except Exception as e:
            self.logger.error(f"Failed to spend points for {username}: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_balance(self, username: str) -> Dict[str, Any]:
        """Get joint balance for couple"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id', 'balance': 0}

            balance_ref = self.db.collection('task_points_balance').document(couple_id)
            balance_doc = balance_ref.get()

            if not balance_doc.exists:
                return {'status': 'success', 'balance': 0}

            data = balance_doc.to_dict()
            return {'status': 'success', 'balance': data.get('balance', 0)}
        except Exception as e:
            self.logger.error(f"Failed to get balance for {username}: {e}")
            return {'status': 'error', 'message': str(e), 'balance': 0}

    def get_daily_points(self, username: str, target_date: date) -> int:
        """Get per-person points for a specific date"""
        try:
            date_str = target_date.isoformat()
            daily_key = f"{username}_{date_str}"
            daily_ref = self.db.collection('task_points_daily').document(daily_key)
            daily_doc = daily_ref.get()

            if not daily_doc.exists:
                return 0

            data = daily_doc.to_dict()
            return data.get('points_earned', 0)
        except Exception as e:
            self.logger.error(f"Failed to get daily points for {username} on {target_date}: {e}")
            return 0

    def get_daily_points_and_threshold(
        self, username: str, target_date: date
    ) -> Tuple[int, Optional[int]]:
        """Points and threshold. Today: live compute. Locked days: stored only."""
        try:
            today = self._today()
            daily_key = f"{username}_{target_date.isoformat()}"
            daily_ref = self.db.collection('task_points_daily').document(daily_key)
            daily_doc = daily_ref.get()

            pts = 0
            if daily_doc.exists:
                pts = daily_doc.to_dict().get('points_earned', 0)

            if target_date == today:
                return (pts, self.get_daily_goal(username, today))

            if not daily_doc.exists:
                return (pts, None)
            thresh = daily_doc.to_dict().get('streak_threshold')
            return (pts, thresh if thresh is not None else None)
        except Exception as e:
            self.logger.error(f"Failed to get daily points/threshold for {username} on {target_date}: {e}")
            if target_date == self._today():
                return (0, self.get_daily_goal(username, self._today()))
            return (0, None)

    def get_daily_points_today(self, username: str) -> int:
        """Get per-person points for today"""
        return self.get_daily_points(username, self._today())

    def clear_daily_points_for_reset(self, username: str, target_date: date) -> None:
        """Clear per-person daily points for a date (called during daily reset).
        Balance is NOT modified - only the daily tally for a clean new day."""
        try:
            date_str = target_date.isoformat()
            daily_key = f"{username}_{date_str}"
            daily_ref = self.db.collection('task_points_daily').document(daily_key)
            if daily_ref.get().exists:
                daily_ref.delete()
                self.logger.info(f"Cleared task_points_daily for {username} on {date_str}")
        except Exception as e:
            self.logger.error(f"Failed to clear daily points for {username} on {target_date}: {e}")

    def lock_daily_threshold_for_date(
        self, username: str, locked_date: date, threshold: Optional[int] = None
    ) -> None:
        """Write final streak_threshold for a locked reset day (4am Chicago reset)."""
        try:
            if locked_date >= self._today():
                return
            if threshold is None:
                threshold = self.get_daily_goal(username, locked_date)
            date_str = locked_date.isoformat()
            daily_key = f"{username}_{date_str}"
            daily_ref = self.db.collection('task_points_daily').document(daily_key)
            payload: Dict[str, Any] = {
                'username': username,
                'date': date_str,
                'streak_threshold': threshold,
                'updated_at': firestore.SERVER_TIMESTAMP,
            }
            if daily_ref.get().exists:
                daily_ref.set(payload, merge=True)
            else:
                payload['points_earned'] = 0
                daily_ref.set(payload, merge=True)
        except Exception as e:
            self.logger.error(
                f"Failed to lock daily threshold for {username} on {locked_date}: {e}"
            )

    def _get_spouse_username(self, username: str) -> Optional[str]:
        try:
            user_ref = self.db.collection('users').document(username).get()
            if user_ref.exists:
                return user_ref.to_dict().get('spouse_username')
        except Exception as e:
            self.logger.error(f"Failed to get spouse for {username}: {e}")
        return None

    def _compute_streak_from_daily(self, username: str) -> int:
        """Streak from locked days with stored threshold; missing data breaks the streak."""
        today = self._today()
        col = self.db.collection('task_points_daily')
        count = 0
        offset = 1
        while offset <= self.STREAK_LOOKBACK_DAYS:
            batch_end = min(offset + self.STREAK_BATCH_DAYS - 1, self.STREAK_LOOKBACK_DAYS)
            refs = [
                col.document(f"{username}_{(today - timedelta(days=off)).isoformat()}")
                for off in range(offset, batch_end + 1)
            ]
            docs_by_id = {doc.id: doc for doc in self.db.get_all(refs)}
            for off in range(offset, batch_end + 1):
                check_date = today - timedelta(days=off)
                doc_id = f"{username}_{check_date.isoformat()}"
                doc = docs_by_id.get(doc_id)
                if not doc or not doc.exists:
                    return count
                data = doc.to_dict()
                thresh = data.get('streak_threshold')
                if thresh is None:
                    return count
                if data.get('points_earned', 0) >= thresh:
                    count += 1
                else:
                    return count
            offset = batch_end + 1
        return count

    def get_streak(self, username: str) -> Dict[str, Any]:
        """Get current streak and today's daily goal (active day computed live)."""
        try:
            _, threshold = self.get_daily_points_and_threshold(username, self._today())
            threshold = threshold if threshold is not None else 0
            current_streak = self._compute_streak_from_daily(username)
            return {
                'status': 'success',
                'current_streak': current_streak,
                'streak_threshold': threshold
            }
        except Exception as e:
            self.logger.error(f"Failed to get streak for {username}: {e}")
            return {'status': 'error', 'message': str(e), 'current_streak': 0, 'streak_threshold': 0}

    def get_today_summary(self, username: str) -> Dict[str, Any]:
        """Fast today points + thresholds for user and spouse (nav / stats header)."""
        try:
            today = self._today()
            usernames = [username]
            spouse_username = self._get_spouse_username(username)
            if spouse_username:
                usernames.append(spouse_username)

            today_points: Dict[str, int] = {}
            thresholds: Dict[str, int] = {}
            below_minimum: List[str] = []
            for u in usernames:
                pts, thresh = self.get_daily_points_and_threshold(u, today)
                today_points[u] = pts
                thresholds[u] = thresh if thresh is not None else 0
                if thresh is not None and pts < thresh:
                    below_minimum.append(u)

            return {
                'status': 'success',
                'today_points': today_points,
                'thresholds': thresholds,
                'below_minimum': below_minimum,
            }
        except Exception as e:
            self.logger.error(f"Failed to get today summary for {username}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'today_points': {},
                'thresholds': {},
                'below_minimum': [],
            }

    def get_config(self, username: str) -> Dict[str, Any]:
        """Return today's computed daily goal from scheduled task instances."""
        try:
            today = self._today()
            daily_goal = self.get_daily_goal(username, today)
            spouse_username = None
            user_ref = self.db.collection('users').document(username).get()
            if user_ref.exists:
                spouse_username = user_ref.to_dict().get('spouse_username')

            result: Dict[str, Any] = {'daily_goal_today': daily_goal}
            if spouse_username:
                result['spouse_daily_goal_today'] = self.get_daily_goal(spouse_username, today)
            return result
        except Exception as e:
            self.logger.error(f"Failed to get config for {username}: {e}")
            return {'daily_goal_today': 0}

    def update_config(self, username: str) -> Dict[str, Any]:
        """Daily goal is computed from tasks; config is read-only."""
        return {'status': 'success', 'config': self.get_config(username)}

    def get_spending_history(self, username: str, limit: int = 20) -> Dict[str, Any]:
        """Get recent spending records for couple"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id', 'history': []}

            query = (self.db.collection('task_points_spending')
                     .where('couple_id', '==', couple_id)
                     .limit(limit * 2))

            docs = list(query.stream())
            history_raw = []
            for doc in docs:
                data = doc.to_dict()
                created_at = data.get('created_at')
                if hasattr(created_at, 'timestamp'):
                    ts = created_at.timestamp()
                else:
                    ts = 0
                history_raw.append((ts, doc.id, data))

            history_raw.sort(key=lambda x: x[0], reverse=True)
            history_raw = history_raw[:limit]

            history = []
            for ts, doc_id, data in history_raw:
                created_at_val = data.get('created_at')
                if hasattr(created_at_val, 'timestamp'):
                    created_at_val = datetime.fromtimestamp(created_at_val.timestamp())
                history.append({
                    'id': doc_id,
                    'amount': data.get('amount', 0),
                    'description': data.get('description', ''),
                    'username': data.get('username', ''),
                    'created_at': created_at_val.isoformat() if created_at_val else None
                })

            return {'status': 'success', 'history': history}
        except Exception as e:
            self.logger.error(f"Failed to get spending history for {username}: {e}")
            return {'status': 'error', 'message': str(e), 'history': []}

    def get_balance_summary(self, username: str) -> Dict[str, Any]:
        """Get full balance summary: joint balance, today's points per person, streaks"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id'}

            balance_res = self.get_balance(username)
            if balance_res['status'] != 'success':
                return balance_res

            user_daily = self.get_daily_points_today(username)
            user_streak = self.get_streak(username)

            spouse_username = self._get_spouse_username(username)

            spouse_daily = 0
            spouse_streak = {'current_streak': 0, 'streak_threshold': 0}
            if spouse_username:
                spouse_daily = self.get_daily_points_today(spouse_username)
                spouse_streak = self.get_streak(spouse_username)

            return {
                'status': 'success',
                'balance': balance_res['balance'],
                'today_points': {
                    username: user_daily,
                    **({} if not spouse_username else {spouse_username: spouse_daily})
                },
                'streaks': {
                    username: user_streak,
                    **({} if not spouse_username else {spouse_username: spouse_streak})
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get balance summary for {username}: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_daily_history(self, username: str, num_days: int = 365) -> Dict[str, Any]:
        """Get per-day points and streak status for the last num_days for the couple (for calendar)."""
        try:
            today = self._today()
            end_date = today
            start_date = today - timedelta(days=max(0, num_days - 1))
            today_str = today.isoformat()

            threshold = self.get_daily_goal(username, today)

            user_ref = self.db.collection('users').document(username).get()
            spouse_username = user_ref.to_dict().get('spouse_username') if user_ref.exists else None
            usernames = [username]
            if spouse_username:
                usernames.append(spouse_username)

            days_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
            for d in range((end_date - start_date).days + 1):
                day = start_date + timedelta(days=d)
                day_str = day.isoformat()
                days_map[day_str] = {u: {'points': 0, 'made_streak': False} for u in usernames}

            col = self.db.collection('task_points_daily')
            for u in usernames:
                refs = [
                    col.document(f"{u}_{(start_date + timedelta(days=d)).isoformat()}")
                    for d in range((end_date - start_date).days + 1)
                ]
                for doc in self.db.get_all(refs):
                    if doc.exists:
                        data = doc.to_dict()
                        day_str = data.get('date')
                        if day_str and day_str in days_map:
                            pts = data.get('points_earned', 0)
                            day_threshold = data.get('streak_threshold')
                            if day_str == today_str:
                                day_threshold = self.get_daily_goal(u, today)
                                made = pts >= day_threshold
                            elif day_threshold is None:
                                made = False
                            else:
                                made = pts >= day_threshold
                            days_map[day_str][u] = {
                                'points': pts,
                                'made_streak': made
                            }

            return {
                'status': 'success',
                'threshold': threshold,
                'days': days_map
            }
        except Exception as e:
            self.logger.error(f"Failed to get daily history for {username}: {e}")
            return {'status': 'error', 'message': str(e), 'days': {}, 'threshold': 0}

    def get_couple_id(self, username: str) -> Optional[str]:
        """Get couple identifier (sorted usernames); single user = username"""
        try:
            user_ref = self.db.collection('users').document(username)
            user_doc = user_ref.get()

            if not user_doc.exists:
                return username

            user_data = user_doc.to_dict()
            spouse_username = user_data.get('spouse_username')

            if not spouse_username:
                return username

            usernames = sorted([username, spouse_username])
            return '_'.join(usernames)
        except Exception as e:
            self.logger.error(f"Failed to get couple_id for {username}: {e}")
            return None
