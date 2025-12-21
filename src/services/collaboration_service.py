"""
Collaboration service - manages the shared collaboration tracker and user goals
"""
from datetime import datetime, timedelta
import pytz
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from src.utils.config import get_timezone, get_spouse
from src.utils.error_handlers import handle_exception


class CollaborationService:
    """Service for collaboration tracker and goal management"""
    
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()
    
    def get_or_create_tracker(self):
        """Get tracker or create with initial value of 5"""
        try:
            # Try to get existing tracker
            tracker_query = self.db.collection('collaboration_tracker').limit(1)
            tracker_docs = list(tracker_query.stream())
            
            if tracker_docs:
                tracker_data = tracker_docs[0].to_dict()
                tracker_data['id'] = tracker_docs[0].id
                return tracker_data
            
            # Create new tracker if none exists
            tracker_data = {
                'current_value': 5,
                'last_updated': firestore.SERVER_TIMESTAMP,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            doc_ref = self.db.collection('collaboration_tracker').add(tracker_data)
            tracker_data['id'] = doc_ref[1].id
            self.logger.info("Created new collaboration tracker with value 5")
            
            return tracker_data
            
        except Exception as e:
            self.logger.error(f"Failed to get or create tracker: {e}")
            return None
    
    def _get_daily_points_for_date(self, username, date):
        """Get daily points for date (with inverted support)"""
        try:
            date_str = date.isoformat()
            
            total_points = 0
            
            # Get completed daily task instances for this date
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', date_str),
                    FieldFilter('completed', '==', True)
                ])
            )
            instances_docs = instances_query.stream()
            
            for instance_doc in instances_docs:
                instance_data = instance_doc.to_dict()
                # Exclude abandoned tasks from point calculations
                if not instance_data.get('abandoned', False):
                    total_points += instance_data.get('points', 0)
            
            # Get completed regular tasks for this date using completed_at timestamp
            # Convert date to start and end of day timestamps in Central time
            start_of_day = datetime.combine(date, datetime.min.time())
            end_of_day = datetime.combine(date, datetime.max.time())
            
            # Localize to Central timezone then convert to UTC for Firestore
            start_timestamp = self.central_tz.localize(start_of_day).astimezone(pytz.UTC)
            end_timestamp = self.central_tz.localize(end_of_day).astimezone(pytz.UTC)
            
            tasks_query = self.db.collection('tasks').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('completed', '==', True),
                    FieldFilter('completed_at', '>=', start_timestamp),
                    FieldFilter('completed_at', '<=', end_timestamp)
                ])
            )
            tasks_docs = tasks_query.stream()
            
            for task_doc in tasks_docs:
                task_data = task_doc.to_dict()
                # Use difficulty as points for regular tasks
                total_points += task_data.get('difficulty', 0)
            
            self.logger.debug(f"Daily points for {username} on {date_str}: {total_points}")
            return total_points
            
        except Exception as e:
            self.logger.error(f"Failed to get daily points for {username} on {date}: {e}")
            return 0
    
    def check_and_update_tracker_on_threshold(self, username):
        """Check if user crossed 100-point threshold and update tracker"""
        try:
            today_central = datetime.now(self.central_tz).date()
            
            # Get current total points for user today (with inverted support)
            current_points = self._get_daily_points_for_date(username, today_central)
            
            self.logger.debug(f"Checking threshold for {username}: {current_points} points, threshold_count calculation")
            
            # Calculate how many 100-point thresholds have been crossed
            # Use absolute value for threshold count (always positive points)
            threshold_count = abs(current_points) // 100
            
            self.logger.debug(f"Threshold count for {username}: {threshold_count} (from {current_points} points)")
            
            # Get last recorded threshold count for today
            threshold_key = f"threshold_{today_central.isoformat()}_{username}"
            threshold_ref = self.db.collection('threshold_tracking').document(threshold_key)
            threshold_doc = threshold_ref.get()
            
            last_threshold_count = 0
            if threshold_doc.exists:
                threshold_data = threshold_doc.to_dict()
                last_threshold_count = threshold_data.get('threshold_count', 0)
            
            self.logger.debug(f"Last threshold count for {username}: {last_threshold_count}, current: {threshold_count}")
            
            # Check if new thresholds were crossed
            if threshold_count > last_threshold_count:
                # Calculate how many thresholds to apply
                thresholds_to_apply = threshold_count - last_threshold_count
                
                self.logger.debug(f"Applying {thresholds_to_apply} threshold(s) for {username}")
                
                # Get user settings (for spouse and inverted status) - single database call
                # Use cached user_service from app_manager if available
                user_service = getattr(self.app_manager, 'user_service', None)
                if not user_service:
                    from src.services.user_service import UserService
                    user_service = UserService(self.app_manager)
                user_settings = user_service.get_user_settings(username)
                spouse_username = user_settings.get('spouse_username')
                is_inverted = user_settings.get('inverted', False)
                
                self.logger.debug(f"User {username} inverted status: {is_inverted}")
                
                # Get current tracker
                tracker = self.get_or_create_tracker()
                if not tracker:
                    self.logger.error("Failed to get tracker for threshold update")
                    return
                
                old_value = tracker['current_value']
                
                # Calculate movement (how many thresholds to apply)
                user_movement = thresholds_to_apply
                
                # Apply inverted status if user has inverted enabled
                # Inverted users move tracker toward 1, non-inverted toward 9
                if is_inverted:
                    user_movement = -user_movement
                    self.logger.debug(f"Inverted movement: {thresholds_to_apply} → {user_movement}")
                
                # Update tracker (shared tracker moves based on this user's progress)
                new_value = old_value + user_movement
                
                # Cap at 1-9 range
                new_value = max(1, min(9, new_value))
                
                tracker_ref = self.db.collection('collaboration_tracker').document(tracker['id'])
                tracker_ref.update({
                    'current_value': new_value,
                    'last_updated': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                
                # Update threshold tracking for this user
                threshold_ref.set({
                    'username': username,
                    'date': today_central.isoformat(),
                    'threshold_count': threshold_count,
                    'points': current_points,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }, merge=True)
                
                # Log to history (get spouse points for logging, but don't check their threshold)
                spouse_points = self._get_daily_points_for_date(spouse_username, today_central) if spouse_username else 0
                self._log_tracker_history(
                    today_central, 
                    current_points, 
                    spouse_points, 
                    old_value, 
                    new_value, 
                    user_movement, 
                    0,  # No spouse movement in this call - they'll check their own
                    username, 
                    spouse_username
                )
                
                self.logger.info(f"Updated tracker on threshold for {username}: {old_value} → {new_value} (+{user_movement} from user crossing {thresholds_to_apply} threshold(s))")
            
        except Exception as e:
            self.logger.error(f"Failed to check and update tracker on threshold for {username}: {e}")
    
    def _log_tracker_history(self, date, user_points, spouse_points, old_value, new_value, user_movement, spouse_movement, username=None, spouse_username=None, is_test=False):
        """Log tracker update to history"""
        try:
            # Skip logging if no username provided
            if not username:
                return
            
            history_data = {
                'date': date.isoformat(),
                'user_points': user_points,
                'spouse_points': spouse_points,
                'old_value': old_value,
                'new_value': new_value,
                'user_movement': user_movement,
                'spouse_movement': spouse_movement,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            # Only include is_test field if True
            if is_test:
                history_data['is_test'] = True
            
            self.db.collection('tracker_history').add(history_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log tracker history: {e}")
    
    def get_tracker_display(self, username):
        """Get tracker value"""
        try:
            tracker = self.get_or_create_tracker()
            
            if not tracker:
                return {
                    'status': 'error',
                    'message': 'Failed to get tracker'
                }
            
            return {
                'status': 'success',
                'tracker_value': tracker['current_value']
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get tracker display for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get tracker display: {str(e)}'
            }
    
    def reset_tracker_history(self):
        """Reset tracker to initial state and clear all history"""
        try:
            # Delete all tracker history
            history_query = self.db.collection('tracker_history')
            history_docs = history_query.stream()
            deleted_count = 0
            
            for doc in history_docs:
                doc.reference.delete()
                deleted_count += 1
            
            # Reset tracker to initial value of 5
            tracker = self.get_or_create_tracker()
            if tracker:
                tracker_ref = self.db.collection('collaboration_tracker').document(tracker['id'])
                tracker_ref.update({
                    'current_value': 5,
                    'last_updated': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            self.logger.info(f"Reset tracker history - deleted {deleted_count} records, reset tracker to 5")
            return {'status': 'success', 'deleted': deleted_count}
        except Exception as e:
            self.logger.error(f"Failed to reset tracker history: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_todays_total_points(self, username):
        """Get total points today"""
        try:
            # Get today's date in Central time
            today_central = datetime.now(self.central_tz).date()
            
            # Use existing method to get daily points
            total_points = self._get_daily_points_for_date(username, today_central)
            
            return {
                'status': 'success',
                'total_points': total_points,
                'date': today_central.isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to get today's points for {username}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_tracker_at_2am(self):
        """Get the collaboration tracker value at 2am reset time (last event before 2am today)"""
        try:
            now_central = datetime.now(self.central_tz)
            today_central = now_central.date()
            
            # Calculate 2am today in Central timezone
            reset_time_today = datetime.combine(today_central, datetime.min.time().replace(hour=2))
            reset_time_today = self.central_tz.localize(reset_time_today)
            
            # Query tracker_history for entries before 2am today
            # Order by date descending to get the most recent entry
            history_query = self.db.collection('tracker_history').order_by(
                'date', direction=firestore.Query.DESCENDING
            )
            
            # Get all history entries and find the last one before 2am today
            last_entry_before_2am = None
            for doc in history_query.stream():
                history_data = doc.to_dict()
                entry_date_str = history_data.get('date', '')
                
                # Parse the date string
                try:
                    entry_date = datetime.fromisoformat(entry_date_str).date()
                    # Check if this entry is from before today, or from today but before 2am
                    if entry_date < today_central:
                        # This is from a previous day, so it's before 2am today
                        last_entry_before_2am = history_data
                        break
                    elif entry_date == today_central:
                        # This is from today, check the created_at timestamp
                        created_at = history_data.get('created_at')
                        if created_at:
                            # Convert Firestore timestamp to datetime
                            if hasattr(created_at, 'timestamp'):
                                created_datetime = datetime.fromtimestamp(created_at.timestamp(), tz=self.central_tz)
                            else:
                                created_datetime = created_at
                            
                            if created_datetime < reset_time_today:
                                # This entry was created before 2am today
                                last_entry_before_2am = history_data
                                break
                except (ValueError, AttributeError) as e:
                    self.logger.warning(f"Failed to parse date from history entry: {e}")
                    continue
            
            if last_entry_before_2am:
                tracker_value = last_entry_before_2am.get('new_value', 5)
                entry_date = last_entry_before_2am.get('date', 'unknown')
                return {
                    'status': 'success',
                    'tracker_value': tracker_value,
                    'date': entry_date,
                    'source': 'history'
                }
            else:
                # No history found before 2am, return current tracker value
                tracker = self.get_or_create_tracker()
                current_value = tracker['current_value'] if tracker else 5
                return {
                    'status': 'success',
                    'tracker_value': current_value,
                    'date': today_central.isoformat(),
                    'source': 'current'
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get tracker at 2am: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get tracker at 2am: {str(e)}'
            }
    