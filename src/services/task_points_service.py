"""
Task Points Service - manages standalone task points (per-person daily, joint balance, spending, streaks)
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from src.utils.config import get_timezone


# Default config value (used for both tier unlock and streak threshold)
DEFAULT_POINTS_THRESHOLD = 200
DEFAULT_TIER_UNLOCK_POINTS = 200  # Alias for TaskMaster


class TaskPointsService:
    """Service for standalone task points tracking"""

    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()

    def get_couple_id(self, username: str) -> Optional[str]:
        """Get couple identifier (sorted usernames); single user = username"""
        try:
            user_ref = self.db.collection('users').document(username)
            user_doc = user_ref.get()

            if not user_doc.exists:
                return username  # Assume single user

            user_data = user_doc.to_dict()
            spouse_username = user_data.get('spouse_username')

            if not spouse_username:
                return username

            usernames = sorted([username, spouse_username])
            return '_'.join(usernames)
        except Exception as e:
            self.logger.error(f"Failed to get couple_id for {username}: {e}")
            return None

    def add_points_on_completion(self, username: str, points: int) -> Dict[str, Any]:
        """Add points to joint balance (only excess above streak threshold), update daily total, update streak"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id'}

            today = datetime.now(self.central_tz).date()
            date_str = today.isoformat()

            # Fetch config and daily total before updating (needed for balance formula)
            config = self.get_config(username)
            threshold = config.get('points_threshold', DEFAULT_POINTS_THRESHOLD)
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

            # 1. Update joint balance (only add excess above threshold)
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

            # 2. Update per-person daily total (store threshold in effect so past days aren't reinterpreted)
            daily_ref.set({
                'username': username,
                'date': date_str,
                'points_earned': new_daily,
                'streak_threshold': threshold,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)

            # 3. Update streak
            self._update_streak(username, new_daily)

            return {'status': 'success', 'points_added': points_for_balance}
        except Exception as e:
            self.logger.error(f"Failed to add points for {username}: {e}")
            return {'status': 'error', 'message': str(e)}

    def _update_streak(self, username: str, points_earned_today: int) -> None:
        """Update streak based on today's points vs threshold"""
        try:
            couple_id = self.get_couple_id(username)
            config = self.get_config(username)
            threshold = config.get('points_threshold', DEFAULT_POINTS_THRESHOLD)

            streak_ref = self.db.collection('task_streaks').document(username)
            streak_doc = streak_ref.get()

            today = datetime.now(self.central_tz).date()

            if streak_doc.exists:
                data = streak_doc.to_dict()
                last_date_str = data.get('last_streak_date')
                current_streak = data.get('current_streak', 0)

                if points_earned_today >= threshold:
                    if last_date_str:
                        last_date = date.fromisoformat(last_date_str)
                        if last_date == today:
                            pass  # Already counted today
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
                    # Below threshold - streak broken for today
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

    def get_daily_points_and_threshold(self, username: str, target_date: date, fallback_threshold: int) -> tuple:
        """Get points and the threshold that was in effect for that day (so we don't reinterpret past days). Returns (points, threshold)."""
        try:
            date_str = target_date.isoformat()
            daily_key = f"{username}_{date_str}"
            daily_ref = self.db.collection('task_points_daily').document(daily_key)
            daily_doc = daily_ref.get()

            if not daily_doc.exists:
                return (0, fallback_threshold)

            data = daily_doc.to_dict()
            pts = data.get('points_earned', 0)
            thresh = data.get('streak_threshold')
            if thresh is not None:
                return (pts, thresh)
            return (pts, fallback_threshold)
        except Exception as e:
            self.logger.error(f"Failed to get daily points/threshold for {username} on {target_date}: {e}")
            return (0, fallback_threshold)

    def get_daily_points_today(self, username: str) -> int:
        """Get per-person points for today"""
        today = datetime.now(self.central_tz).date()
        return self.get_daily_points(username, today)

    def clear_daily_points_for_reset(self, username: str, target_date: date) -> None:
        """Clear per-person daily points for a date (called during 2am reset).
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

    def _compute_streak_from_daily(self, username: str, fallback_threshold: int) -> int:
        """Compute current streak from task_points_daily. Uses each day's stored threshold so past days aren't reinterpreted. Walk backwards from yesterday."""
        today = datetime.now(self.central_tz).date()
        count = 0
        d = today - timedelta(days=1)
        while True:
            pts, thresh = self.get_daily_points_and_threshold(username, d, fallback_threshold)
            if pts >= thresh:
                count += 1
                d -= timedelta(days=1)
            else:
                break
        return count

    def get_streak(self, username: str) -> Dict[str, Any]:
        """Get current streak and threshold. Streak is computed from task_points_daily (same as calendar)."""
        try:
            config = self.get_config(username)
            threshold = config.get('points_threshold', DEFAULT_POINTS_THRESHOLD)
            current_streak = self._compute_streak_from_daily(username, threshold)
            return {
                'status': 'success',
                'current_streak': current_streak,
                'streak_threshold': threshold
            }
        except Exception as e:
            self.logger.error(f"Failed to get streak for {username}: {e}")
            return {'status': 'error', 'message': str(e), 'current_streak': 0, 'streak_threshold': DEFAULT_POINTS_THRESHOLD}

    def get_config(self, username: str) -> Dict[str, Any]:
        """Get task points config (points_threshold - used for both tier unlock and streak)"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                val = DEFAULT_POINTS_THRESHOLD
                return {'points_threshold': val, 'tier_unlock_points': val, 'streak_threshold': val}

            config_ref = self.db.collection('task_points_config').document(couple_id)
            config_doc = config_ref.get()

            if not config_doc.exists:
                val = DEFAULT_POINTS_THRESHOLD
                return {'points_threshold': val, 'tier_unlock_points': val, 'streak_threshold': val}

            data = config_doc.to_dict()
            val = data.get('points_threshold')
            if val is None:
                val = data.get('tier_unlock_points', data.get('streak_threshold', DEFAULT_POINTS_THRESHOLD))
            if val is None or val < 0:
                val = DEFAULT_POINTS_THRESHOLD
            return {'points_threshold': val, 'tier_unlock_points': val, 'streak_threshold': val}
        except Exception as e:
            self.logger.error(f"Failed to get config for {username}: {e}")
            val = DEFAULT_POINTS_THRESHOLD
            return {'points_threshold': val, 'tier_unlock_points': val, 'streak_threshold': val}

    def update_config(self, username: str, points_threshold: Optional[int] = None) -> Dict[str, Any]:
        """Update task points config (single threshold for tier unlock and streak)"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id'}

            if points_threshold is not None:
                if points_threshold < 0:
                    return {'status': 'error', 'message': 'points_threshold must be non-negative'}
                config_ref = self.db.collection('task_points_config').document(couple_id)
                config_ref.set({
                    'points_threshold': points_threshold,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }, merge=True)

            return {'status': 'success', 'config': self.get_config(username)}
        except Exception as e:
            self.logger.error(f"Failed to update config for {username}: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_spending_history(self, username: str, limit: int = 20) -> Dict[str, Any]:
        """Get recent spending records for couple"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id', 'history': []}

            query = (self.db.collection('task_points_spending')
                     .where('couple_id', '==', couple_id)
                     .limit(limit * 2))  # Fetch extra, sort in memory (avoids composite index)

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

            spouse_username = None
            user_ref = self.db.collection('users').document(username).get()
            if user_ref.exists:
                spouse_username = user_ref.to_dict().get('spouse_username')

            spouse_daily = 0
            spouse_streak = {'current_streak': 0, 'streak_threshold': user_streak.get('streak_threshold', DEFAULT_POINTS_THRESHOLD)}
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
            today = datetime.now(self.central_tz).date()
            end_date = today
            start_date = today - timedelta(days=max(0, num_days - 1))
            start_str = start_date.isoformat()
            end_str = end_date.isoformat()

            config = self.get_config(username)
            threshold = config.get('points_threshold', DEFAULT_POINTS_THRESHOLD)

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
                            if day_threshold is None:
                                day_threshold = threshold
                            days_map[day_str][u] = {
                                'points': pts,
                                'made_streak': pts >= day_threshold
                            }

            return {
                'status': 'success',
                'threshold': threshold,
                'days': days_map
            }
        except Exception as e:
            self.logger.error(f"Failed to get daily history for {username}: {e}")
            return {'status': 'error', 'message': str(e), 'days': {}, 'threshold': DEFAULT_POINTS_THRESHOLD}
