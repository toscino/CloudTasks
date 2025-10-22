"""
Collaboration service - manages the shared collaboration tracker and user goals
"""
import pytz
from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from src.utils.logger import logger
from src.auth.auth_service import get_spouse_username


class CollaborationService:
    """Service for collaboration tracker and goal management"""
    
    def __init__(self, db):
        self.db = db
        self.central_tz = pytz.timezone('America/Chicago')
    
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
            logger.info("Created new collaboration tracker with value 5")
            
            return tracker_data
            
        except Exception as e:
            logger.error(f"Failed to get or create tracker: {e}")
            return None
    
    def get_user_goals(self, username):
        """Get user's stretch setting and calculate par/stretch goals"""
        try:
            # Get user's stretch setting
            goals_query = self.db.collection('user_goals').where('username', '==', username).limit(1)
            goals_docs = list(goals_query.stream())
            
            stretch_setting = 10  # Default stretch setting
            adjustment_multiplier = 1  # Default adjustment multiplier
            if goals_docs:
                goals_data = goals_docs[0].to_dict()
                stretch_setting = goals_data.get('stretch_setting', 10)
                adjustment_multiplier = goals_data.get('adjustment_multiplier', 1)
            
            # Calculate par (sum of positive daily task points)
            par = self._calculate_user_par(username)
            
            return {
                'par': par,
                'stretch_setting': stretch_setting,
                'stretch_goal': par + stretch_setting,
                'adjustment_multiplier': adjustment_multiplier
            }
            
        except Exception as e:
            logger.error(f"Failed to get user goals for {username}: {e}")
            return {
                'par': 0,
                'stretch_setting': 10,
                'stretch_goal': 10
            }
    
    def set_user_stretch_setting(self, username, stretch_setting, adjustment_multiplier=None):
        """Set user's stretch setting and optional adjustment multiplier"""
        try:
            if stretch_setting < 0 or stretch_setting > 100:
                return {'status': 'error', 'message': 'Stretch setting must be between 0 and 100'}
            
            if adjustment_multiplier is not None and adjustment_multiplier not in [-1, 1]:
                return {'status': 'error', 'message': 'Adjustment multiplier must be -1 or 1'}
            
            # Check if user goals already exist
            goals_query = self.db.collection('user_goals').where('username', '==', username).limit(1)
            goals_docs = list(goals_query.stream())
            
            goals_data = {
                'username': username,
                'stretch_setting': stretch_setting,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Add adjustment multiplier if provided
            if adjustment_multiplier is not None:
                goals_data['adjustment_multiplier'] = adjustment_multiplier
            
            if goals_docs:
                # Update existing
                goals_docs[0].reference.update(goals_data)
                logger.info(f"Updated goals for {username}: stretch={stretch_setting}, multiplier={adjustment_multiplier}")
            else:
                # Create new (default multiplier to 1 if not provided)
                if adjustment_multiplier is None:
                    goals_data['adjustment_multiplier'] = 1
                goals_data['created_at'] = firestore.SERVER_TIMESTAMP
                self.db.collection('user_goals').add(goals_data)
                logger.info(f"Created goals for {username}: stretch={stretch_setting}, multiplier={adjustment_multiplier or 1}")
            
            return {'status': 'success', 'message': 'Goals updated successfully'}
            
        except Exception as e:
            logger.error(f"Failed to set goals for {username}: {e}")
            return {'status': 'error', 'message': f'Failed to update goals: {str(e)}'}
    
    def _calculate_user_par(self, username):
        """Calculate par (sum of positive daily task points) for a user"""
        try:
            # Get all active daily task templates for user
            templates_query = self.db.collection('daily_task_templates').where('username', '==', username)
            templates_docs = templates_query.stream()
            
            par = 0
            for template_doc in templates_docs:
                template_data = template_doc.to_dict()
                points = template_data.get('points', 0)
                if points > 0:  # Only count positive points
                    par += points
            
            logger.debug(f"Calculated par for {username}: {par}")
            return par
            
        except Exception as e:
            logger.error(f"Failed to calculate par for {username}: {e}")
            return 0
    
    def calculate_tracker_adjustment(self, username, daily_points):
        """Calculate +1, 0, or -1 based on user's performance, multiplied by user's adjustment multiplier"""
        try:
            goals = self.get_user_goals(username)
            par = goals['par']
            stretch_goal = goals['stretch_goal']
            multiplier = goals.get('adjustment_multiplier', 1)  # Default to 1 (normal direction)
            logger.debug(f"User {username} has an adjustment multiplier of {multiplier}")
            if daily_points > stretch_goal:
                # Above stretch goal (good day)
                base_adjustment = 1
            elif daily_points >= par:
                # Between par and stretch goal
                base_adjustment = 0
            else:
                # Below par (bad day)
                base_adjustment = -1
            
            # Apply user's multiplier (-1 inverts the direction, 1 keeps it normal)
            adjustment = base_adjustment * multiplier
            
            logger.debug(f"Adjustment for {username}: {daily_points} points (par: {par}, stretch: {stretch_goal}, multiplier: {multiplier}) = {adjustment}")
            return adjustment
            
        except Exception as e:
            logger.error(f"Failed to calculate adjustment for {username}: {e}")
            return 0
    
    def _get_daily_points_for_date(self, username, date):
        """Get total points earned by user on a specific date"""
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
            
            logger.debug(f"Daily points for {username} on {date_str}: {total_points}")
            return total_points
            
        except Exception as e:
            logger.error(f"Failed to get daily points for {username} on {date}: {e}")
            return 0
    
    def _update_tracker_for_date(self, date):
        """Update tracker for a specific date"""
        try:
            # Get both users' points for this date
            user_points = self._get_daily_points_for_date('Ian', date)
            spouse_points = self._get_daily_points_for_date('Karleigh', date)
            
            # Calculate adjustments
            user_adjustment = self.calculate_tracker_adjustment('Ian', user_points)
            spouse_adjustment = self.calculate_tracker_adjustment('Karleigh', spouse_points)
            
            # Get current tracker
            tracker = self.get_or_create_tracker()
            if not tracker:
                logger.error("Failed to get tracker for update")
                return
            
            old_value = tracker['current_value']
            new_value = old_value + user_adjustment + spouse_adjustment
            
            # Cap at 1-9 range
            new_value = max(1, min(9, new_value))
            
            # Update tracker
            tracker_ref = self.db.collection('collaboration_tracker').document(tracker['id'])
            tracker_ref.update({
                'current_value': new_value,
                'last_updated': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Log to history
            self._log_tracker_history(date, user_points, spouse_points, old_value, new_value, user_adjustment, spouse_adjustment)
            
            logger.info(f"Updated tracker for {date.isoformat()}: {old_value} → {new_value} (Ian: {user_adjustment}, Karleigh: {spouse_adjustment})")
            
        except Exception as e:
            logger.error(f"Failed to update tracker for {date}: {e}")
    
    def _log_tracker_history(self, date, user_points, spouse_points, old_value, new_value, user_adjustment, spouse_adjustment):
        """Log tracker update to history for debugging"""
        try:
            user_goals = self.get_user_goals('Ian')
            spouse_goals = self.get_user_goals('Karleigh')
            
            history_data = {
                'date': date.isoformat(),
                'user_points': user_points,
                'user_goal': user_goals['par'],
                'user_stretch': user_goals['stretch_goal'],
                'spouse_points': spouse_points,
                'spouse_goal': spouse_goals['par'],
                'spouse_stretch': spouse_goals['stretch_goal'],
                'old_value': old_value,
                'new_value': new_value,
                'user_adjustment': user_adjustment,
                'spouse_adjustment': spouse_adjustment,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            self.db.collection('tracker_history').add(history_data)
            
        except Exception as e:
            logger.error(f"Failed to log tracker history: {e}")
    
    def update_tracker_catch_up(self, today_date):
        """Update tracker for all days since last update"""
        try:
            # Get tracker and its last_updated date
            tracker = self.get_or_create_tracker()
            if not tracker:
                logger.error("Failed to get tracker for catch-up")
                return 0
            
            # Convert last_updated to date
            last_updated_timestamp = tracker['last_updated']
            if hasattr(last_updated_timestamp, 'timestamp'):
                last_updated = datetime.fromtimestamp(last_updated_timestamp.timestamp(), tz=self.central_tz).date()
            else:
                last_updated = last_updated_timestamp.date()
            
            # Calculate days to process (yesterday backwards to last_updated)
            days_to_process = []
            current_date = today_date - timedelta(days=1)  # Start with yesterday
            
            while current_date > last_updated:
                days_to_process.append(current_date)
                current_date -= timedelta(days=1)
            
            # Process each day in chronological order (oldest first)
            for date in reversed(days_to_process):
                self._update_tracker_for_date(date)
            
            logger.info(f"Processed {len(days_to_process)} days for tracker catch-up")
            return len(days_to_process)
            
        except Exception as e:
            logger.error(f"Failed to update tracker catch-up: {e}")
            return 0
    
    def get_tracker_display(self, username):
        """Get tracker value and user's goals for display"""
        try:
            tracker = self.get_or_create_tracker()
            goals = self.get_user_goals(username)
            
            if not tracker:
                return {
                    'status': 'error',
                    'message': 'Failed to get tracker'
                }
            
            return {
                'status': 'success',
                'tracker_value': tracker['current_value'],
                'par': goals['par'],
                'stretch_setting': goals['stretch_setting'],
                'stretch_goal': goals['stretch_goal'],
                'adjustment_multiplier': goals.get('adjustment_multiplier', 1)
            }
            
        except Exception as e:
            logger.error(f"Failed to get tracker display for {username}: {e}")
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
            
            logger.info(f"Reset tracker history - deleted {deleted_count} records, reset tracker to 5")
            return {'status': 'success', 'deleted': deleted_count}
        except Exception as e:
            logger.error(f"Failed to reset tracker history: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_todays_total_points(self, username):
        """Get total points earned today (daily tasks + regular tasks)"""
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
            logger.error(f"Failed to get today's points for {username}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def progress_day_for_testing(self, ian_points=None, karleigh_points=None):
        """Manually trigger end-of-day processing for testing with optional point overrides"""
        try:
            # Get today's date in Central time
            today_central = datetime.now(self.central_tz).date()
            
            # If points are provided, use them directly; otherwise calculate from database
            if ian_points is None or karleigh_points is None:
                # Calculate actual points from database
                user_points = self._get_daily_points_for_date('Ian', today_central)
                spouse_points = self._get_daily_points_for_date('Karleigh', today_central)
            else:
                # Use provided test values
                user_points = ian_points
                spouse_points = karleigh_points
            
            # Calculate adjustments
            user_adjustment = self.calculate_tracker_adjustment('Ian', user_points)
            spouse_adjustment = self.calculate_tracker_adjustment('Karleigh', spouse_points)
            
            # Get current tracker
            tracker = self.get_or_create_tracker()
            if not tracker:
                return {'status': 'error', 'message': 'Failed to get tracker'}
            
            old_value = tracker['current_value']
            new_value = old_value + user_adjustment + spouse_adjustment
            
            # Cap at 1-9 range
            new_value = max(1, min(9, new_value))
            
            # Update tracker
            tracker_ref = self.db.collection('collaboration_tracker').document(tracker['id'])
            tracker_ref.update({
                'current_value': new_value,
                'last_updated': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Log to history
            self._log_tracker_history(today_central, user_points, spouse_points, old_value, new_value, user_adjustment, spouse_adjustment)
            
            logger.info(f"Manually processed day: {today_central.isoformat()} - Ian: {user_points}, Karleigh: {spouse_points}, Tracker: {old_value} → {new_value}")
            
            return {
                'status': 'success', 
                'message': f'Day processed: {today_central.isoformat()}',
                'date': today_central.isoformat(),
                'ian_points': user_points,
                'karleigh_points': spouse_points,
                'old_tracker': old_value,
                'new_tracker': new_value,
                'ian_adjustment': user_adjustment,
                'karleigh_adjustment': spouse_adjustment
            }
        except Exception as e:
            logger.error(f"Failed to progress day: {e}")
            return {'status': 'error', 'message': str(e)}
