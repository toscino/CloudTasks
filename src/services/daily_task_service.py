"""
Daily Task Service - handles daily task templates and instances
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta
import pytz
from src.utils.config import (
    get_timezone,
    get_collection,
    VACATION_WEEKDAY,
    TRAVEL_DAY_WEEKDAY,
)
from src.utils.reset_period import get_reset_day
from src.utils.firestore_helpers import prepare_firestore_document
from src.utils.exceptions import ValidationError, NotFoundError, UnauthorizedError, FirestoreError
from src.utils.error_handlers import handle_exception
from typing import List, Dict, Any


def compute_daily_goal_from_instances(instances: List[Dict[str, Any]]) -> int:
    """Sum points at the highest point tier for the day; floor at 0. Backup tasks excluded."""
    eligible = [i for i in instances if not i.get('is_backup', False)]
    if not eligible:
        return 0
    points_list = [int(i.get('points', 0) or 0) for i in eligible]
    max_pts = max(points_list)
    total = sum(p for p in points_list if p == max_pts)
    return max(0, total)


class DailyTaskService:
    """Service for daily task operations"""
    
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()

    def get_effective_weekday(self, username: str, target_date: date) -> int:
        """Weekday used for template matching (travel > vacation > calendar)."""
        user_service = getattr(self.app_manager, 'user_service', None)
        if not user_service:
            from src.services.user_service import UserService
            user_service = UserService(self.app_manager)

        user_settings = user_service.get_user_settings(username)
        if user_settings.get('travel_day_mode', False):
            self.logger.debug(f"Travel day mode for {username}, using weekday {TRAVEL_DAY_WEEKDAY}")
            return TRAVEL_DAY_WEEKDAY
        if user_settings.get('vacation_mode', False):
            self.logger.debug(f"Vacation mode for {username}, using weekday {VACATION_WEEKDAY}")
            return VACATION_WEEKDAY
        return target_date.weekday()

    def get_daily_tasks(self, username: str) -> Dict[str, Any]:
        """Get daily task templates"""
        try:
            # Query daily task templates for this user
            templates_query = self.db.collection('daily_task_templates').where('username', '==', username)
            templates_docs = templates_query.stream()
            
            templates = []
            for doc in templates_docs:
                template_data = prepare_firestore_document(doc)
                templates.append(template_data)
            
            return {
                'status': 'success',
                'templates': templates
            }
        except Exception as e:
            self.logger.error(f"Failed to get daily tasks for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get daily tasks: {str(e)}'
            }
    
    def create_daily_task(self, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Create daily task template"""
        try:
            if not data or not data.get('description'):
                raise ValidationError(
                    "Task description is required",
                    user_message="Task description is required"
                )
            
            if not data.get('points') or data.get('points') == 0:
                raise ValidationError(
                    "Points cannot be zero",
                    user_message="Points cannot be zero"
                )
            if data.get('points') < -100 or data.get('points') > 100:
                raise ValidationError(
                    "Points must be between -100 and 100",
                    user_message="Points must be between -100 and 100"
                )
            
            if not data.get('days_of_week') or len(data.get('days_of_week', [])) == 0:
                raise ValidationError(
                    "At least one day of week must be selected",
                    user_message="At least one day of week must be selected"
                )
            
            is_backup = bool(data.get('is_backup', False))

            # Validate days_of_week (0=Monday, 6=Sunday, 7=Travel)
            days_of_week = data.get('days_of_week', [])
            if not all(0 <= day <= TRAVEL_DAY_WEEKDAY for day in days_of_week):
                raise ValidationError(
                    "Invalid days of week",
                    user_message="Invalid days of week"
                )
            
            # Create template data
            template_data = {
                'username': username,
                'description': data['description'].strip(),
                'points': int(data['points']),
                'days_of_week': days_of_week,
                'is_backup': is_backup,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Create new template in Firestore
            doc_ref = self.db.collection('daily_task_templates').add(template_data)
            template_id = doc_ref[1].id
            
            # Check if today is in selected days and create instance
            reset_day = get_reset_day(tz=self.central_tz)
            today_weekday = self.get_effective_weekday(username, reset_day)

            if today_weekday in days_of_week:
                instance_data = {
                    'username': username,
                    'template_id': template_id,
                    'description': data['description'].strip(),
                    'points': int(data['points']),
                    'is_backup': is_backup,
                    'date': reset_day.isoformat(),
                    'completed': False,
                    'created_at': firestore.SERVER_TIMESTAMP
                }
                self.db.collection('daily_task_instances').add(instance_data)
                self.logger.info(f"Created today's instance for new template {template_id}")
            
            return {
                'status': 'success',
                'message': 'Daily task created successfully',
                'template_id': template_id
            }
        except ValidationError as e:
            return handle_exception(e, f"Failed to create daily task for {username}")
        except Exception as e:
            return handle_exception(e, f"Unexpected error creating daily task for {username}")
    
    def update_daily_task(self, task_id: str, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Update daily task template"""
        try:
            doc_ref = self.db.collection('daily_task_templates').document(task_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Daily task not found'
                }
            
            template_data = doc.to_dict()
            if template_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Daily task belongs to another user'
                }
            
            # Validate input
            if 'points' in data:
                if not data['points'] or data['points'] == 0:
                    return {'status': 'error', 'message': 'Points cannot be zero'}
                if data['points'] < -100 or data['points'] > 100:
                    return {'status': 'error', 'message': 'Points must be between -100 and 100'}
            
            if 'days_of_week' in data:
                days_of_week = data['days_of_week']
                if not days_of_week or len(days_of_week) == 0:
                    return {'status': 'error', 'message': 'At least one day of week must be selected'}
                if not all(0 <= day <= TRAVEL_DAY_WEEKDAY for day in days_of_week):
                    return {'status': 'error', 'message': 'Invalid days of week'}
            
            # Update fields
            update_data = {'updated_at': firestore.SERVER_TIMESTAMP}
            if 'description' in data:
                update_data['description'] = data['description'].strip()
            if 'points' in data:
                update_data['points'] = int(data['points'])
            if 'days_of_week' in data:
                update_data['days_of_week'] = data['days_of_week']
            if 'is_backup' in data:
                update_data['is_backup'] = bool(data['is_backup'])
            
            doc_ref.update(update_data)
            
            # Update today's instance if it exists
            reset_day = get_reset_day(tz=self.central_tz)
            instance_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('template_id', '==', task_id),
                    FieldFilter('date', '==', reset_day.isoformat())
                ])
            )
            instances = list(instance_query.stream())
            
            for instance_doc in instances:
                update_instance_data = {}
                if 'description' in update_data:
                    update_instance_data['description'] = update_data['description']
                if 'points' in update_data:
                    update_instance_data['points'] = update_data['points']
                if 'is_backup' in update_data:
                    update_instance_data['is_backup'] = update_data['is_backup']
                
                if update_instance_data:
                    instance_doc.reference.update(update_instance_data)
                    self.logger.info(f"Updated today's instance for template {task_id}")
            
            return {
                'status': 'success',
                'message': 'Daily task updated successfully'
            }
        except Exception as e:
            self.logger.error(f"Failed to update daily task {task_id} for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to update daily task: {str(e)}'
            }
    
    def delete_daily_task(self, task_id: str, username: str) -> Dict[str, Any]:
        """Delete daily task template"""
        try:
            doc_ref = self.db.collection('daily_task_templates').document(task_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Daily task not found'
                }
            
            template_data = doc.to_dict()
            if template_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Daily task belongs to another user'
                }
            
            # Delete template
            doc_ref.delete()
            
            # Also delete any existing instances for this template
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('template_id', '==', task_id)
                ])
            )
            instances_docs = instances_query.stream()
            
            for instance_doc in instances_docs:
                instance_doc.reference.delete()
            
            return {
                'status': 'success',
                'message': 'Daily task deleted successfully'
            }
        except Exception as e:
            self.logger.error(f"Failed to delete daily task {task_id} for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to delete daily task: {str(e)}'
            }
    
    def get_todays_instances(self, username: str) -> Dict[str, Any]:
        """Get today's task instances for stats only"""
        try:
            # First check if reset is needed
            self.check_and_reset_daily_tasks(username)
            
            reset_day = get_reset_day(tz=self.central_tz)
            
            # Query today's instances
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', reset_day.isoformat())
                ])
            )
            instances_docs = instances_query.stream()
            
            instances = []
            total_points = 0
            completed_points = 0
            
            for doc in instances_docs:
                instance_data = prepare_firestore_document(doc)
                instances.append(instance_data)
                total_points += instance_data.get('points', 0)
                if instance_data.get('completed', False):
                    completed_points += instance_data.get('points', 0)
            
            return {
                'status': 'success',
                'instances': instances,
                'total_points': total_points,
                'completed_points': completed_points,
                'date': reset_day.isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to get today's instances for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get today\'s instances: {str(e)}'
            }

    def compute_daily_goal(self, username: str, target_date: date) -> int:
        """Daily goal = sum of points at the top point tier (non-backup instances only)."""
        try:
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', target_date.isoformat()),
                ])
            )
            instances = [doc.to_dict() for doc in instances_query.stream()]
            return compute_daily_goal_from_instances(instances)
        except Exception as e:
            self.logger.error(f"Failed to compute daily goal for {username} on {target_date}: {e}")
            return 0

    def complete_daily_task(self, instance_id: str, username: str) -> Dict[str, Any]:
        """Complete daily task instance"""
        try:
            doc_ref = self.db.collection('daily_task_instances').document(instance_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Daily task instance not found'
                }
            
            instance_data = doc.to_dict()
            if instance_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Daily task instance belongs to another user'
                }
            
            if instance_data.get('completed', False):
                return {
                    'status': 'error',
                    'message': 'Daily task is already completed'
                }
            
            # Mark as completed
            doc_ref.update({
                'completed': True,
                'completed_at': firestore.SERVER_TIMESTAMP
            })

            # Update task points (standalone tracker)
            points_earned = instance_data.get('points', 0)
            task_points_service = getattr(self.app_manager, 'task_points_service', None)
            if task_points_service:
                task_points_service.add_points_on_completion(username, points_earned)
            
            return {
                'status': 'success',
                'message': 'Daily task completed successfully',
                'points_earned': points_earned
            }
        except Exception as e:
            self.logger.error(f"Failed to complete daily task {instance_id} for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to complete daily task: {str(e)}'
            }
    
    def abandon_daily_task(self, instance_id: str, username: str) -> Dict[str, Any]:
        """Abandon daily task instance"""
        try:
            doc_ref = self.db.collection('daily_task_instances').document(instance_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Daily task instance not found'
                }
            
            instance_data = doc.to_dict()
            if instance_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Daily task instance belongs to another user'
                }
            
            if instance_data.get('completed', False):
                return {
                    'status': 'error',
                    'message': 'Cannot abandon a completed task'
                }
            
            if instance_data.get('abandoned', False):
                return {
                    'status': 'error',
                    'message': 'Task is already abandoned'
                }
            
            # Mark as abandoned
            doc_ref.update({
                'abandoned': True,
                'abandoned_at': firestore.SERVER_TIMESTAMP
            })
            
            return {
                'status': 'success',
                'message': 'Daily task abandoned successfully'
            }
        except Exception as e:
            self.logger.error(f"Failed to abandon daily task {instance_id} for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to abandon daily task: {str(e)}'
            }
    
    def check_and_reset_daily_tasks(self, username: str) -> Dict[str, Any]:
        """
        Lazy daily reset (runs on site visit, not cron). At most once per reset day (4am–4am Chicago).
        See docs/DAILY_RESET_BEHAVIOR.md for late reset, skipped days, and performance bonuses.
        """
        try:
            now_central = datetime.now(self.central_tz)
            reset_day = get_reset_day(now_central, tz=self.central_tz)
            
            reset_query = self.db.collection('daily_task_resets').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('last_reset_date', '==', reset_day.isoformat())
                ])
            )
            reset_docs = list(reset_query.stream())
            
            if reset_docs:
                return {'status': 'success', 'message': 'Already reset today'}
            
            user_service = getattr(self.app_manager, 'user_service', None)
            if not user_service:
                from src.services.user_service import UserService
                user_service = UserService(self.app_manager)

            user_settings = user_service.get_user_settings(username)
            spouse_username = user_settings.get('spouse_username')

            perf = getattr(self.app_manager, 'performance_reward_service', None)
            if perf:
                perf.process_missed_reset_rewards(username, reset_day)
                if spouse_username:
                    perf.process_missed_reset_rewards(spouse_username, reset_day)
                perf.expire_due_items(reset_day)

            instances_created = self._reset_user_daily_tasks(username, reset_day)
            
            if spouse_username:
                self.logger.info(f"Also resetting daily tasks for spouse {spouse_username}")
                spouse_instances_created = self._reset_user_daily_tasks(spouse_username, reset_day)
                instances_created += spouse_instances_created
            
            return {
                'status': 'success',
                'message': f'Reset completed, created {instances_created} instances',
                'instances_created': instances_created
            }
        except Exception as e:
            self.logger.error(f"Failed to reset daily tasks for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to reset daily tasks: {str(e)}'
            }
    
    def _reverse_tracker_movement_from_history(self, username: str, today_central: date) -> bool:
        """Reverse collaboration tracker movement by reading today's history entries"""
        try:
            from src.services.collaboration_service import CollaborationService
            collab_service = CollaborationService(self.app_manager)
            
            # Query all tracker history entries for today
            date_str = today_central.isoformat()
            history_query = self.db.collection('tracker_history').where('date', '==', date_str)
            history_docs = list(history_query.stream())
            
            if not history_docs:
                self.logger.info(f"No tracker history entries found for {today_central}, nothing to reverse")
                return False
            
            # Sum up all movements from today's history entries
            total_movement = 0
            entries_processed = 0
            
            for doc in history_docs:
                history_data = doc.to_dict()
                user_movement = history_data.get('user_movement', 0)
                spouse_movement = history_data.get('spouse_movement', 0)
                
                # Add both movements (they're already signed correctly based on inverted status)
                total_movement += user_movement
                total_movement += spouse_movement
                entries_processed += 1
                
                self.logger.debug(f"History entry: user_movement={user_movement}, spouse_movement={spouse_movement}")
            
            if total_movement == 0:
                self.logger.info(f"Total movement from {entries_processed} history entries is 0, nothing to reverse")
                return False
            
            # Reverse the total movement
            reverse_movement = -total_movement
            
            self.logger.info(f"Reversing {entries_processed} history entries for {today_central}: total movement {total_movement} → reverse {reverse_movement}")
            
            # Get current tracker
            tracker = collab_service.get_or_create_tracker()
            if not tracker:
                self.logger.error("Failed to get tracker for reversal")
                return False
            
            old_value = tracker['current_value']
            new_value = old_value + reverse_movement
            
            # Cap at 1-9 range
            new_value = max(1, min(9, new_value))
            
            # Update tracker
            tracker_ref = self.db.collection('collaboration_tracker').document(tracker['id'])
            tracker_ref.update({
                'current_value': new_value,
                'last_updated': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            self.logger.info(f"Reversed tracker movement for {today_central}: {old_value} → {new_value} (reversed {total_movement} total movement)")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to reverse tracker movement from history for {today_central}: {e}")
            return False
    
    def reset_daily_tasks_with_tracker_reversal(self, username: str, reset_day: date = None) -> Dict[str, Any]:
        """Reset daily tasks and reverse collaboration tracker movement from today's history"""
        try:
            if reset_day is None:
                reset_day = get_reset_day(tz=self.central_tz)
            
            # Get user settings to check for spouse
            user_service = getattr(self.app_manager, 'user_service', None)
            if not user_service:
                from src.services.user_service import UserService
                user_service = UserService(self.app_manager)
            
            user_settings = user_service.get_user_settings(username)
            spouse_username = user_settings.get('spouse_username')
            
            # Reverse tracker movement from history (this handles both user and spouse movements)
            # History entries already contain both user_movement and spouse_movement
            self._reverse_tracker_movement_from_history(username, reset_day)
            
            # Now reset tasks normally (this will delete instances and clear threshold tracking)
            instances_created = self._reset_user_daily_tasks(username, reset_day)
            
            if spouse_username:
                spouse_instances_created = self._reset_user_daily_tasks(spouse_username, reset_day)
                instances_created += spouse_instances_created
            
            return {
                'status': 'success',
                'message': f'Reset completed with tracker reversal, created {instances_created} instances',
                'instances_created': instances_created
            }
            
        except Exception as e:
            self.logger.error(f"Failed to reset daily tasks with tracker reversal for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to reset daily tasks: {str(e)}'
            }

    def reset_daily_tasks_for_user_only(self, username: str, reset_day: date = None) -> Dict[str, Any]:
        """Reset daily tasks for one user only (no spouse reset or tracker reversal)."""
        try:
            if reset_day is None:
                reset_day = get_reset_day(tz=self.central_tz)

            instances_created = self._reset_user_daily_tasks(username, reset_day)
            return {
                'status': 'success',
                'message': f'Reset completed, created {instances_created} instances',
                'instances_created': instances_created,
            }
        except Exception as e:
            self.logger.error(f"Failed to reset daily tasks for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to reset daily tasks: {str(e)}',
            }

    def _reset_user_daily_tasks(self, username: str, today_central: date) -> int:
        """Reset daily tasks for a specific user (helper method)"""
        try:
            self.logger.info(f"Resetting daily tasks for {username} on {today_central}")

            task_points_service = getattr(self.app_manager, 'task_points_service', None)
            if task_points_service:
                locked_day = today_central - timedelta(days=1)
                task_points_service.lock_daily_threshold_for_date(username, locked_day)

            perf = getattr(self.app_manager, 'performance_reward_service', None)
            if perf:
                last_reset = perf.get_last_reset_date(username)
                gap = 0
                if last_reset is not None:
                    from src.services.performance_reward_service import missed_reset_dates
                    gap = len(missed_reset_dates(last_reset, today_central))
                if gap == 0:
                    perf.create_item_for_yesterday(username, today_central)
                else:
                    perf.easiest_for_earned_day(
                        username, today_central - timedelta(days=1)
                    )
            
            # Before creating new instances, delete any existing instances for today
            # This includes ALL instances regardless of status (completed, abandoned, presented)
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', today_central.isoformat())
                ])
            )
            deleted_count = 0
            completed_count = 0
            total_points_cleared = 0
            for instance in instances_query.stream():
                instance_data = instance.to_dict()
                if instance_data.get('completed', False):
                    completed_count += 1
                    total_points_cleared += instance_data.get('points', 0)
                instance.reference.delete()
                deleted_count += 1
            if completed_count > 0:
                self.logger.info(f"Deleted {deleted_count} instances for {username} on {today_central} ({completed_count} completed, {total_points_cleared} points cleared)")
            else:
                self.logger.info(f"Deleted {deleted_count} instances for {username} on {today_central}")
            
            # Clear task points daily tally for today (standalone task points; e.g. backup pool / streak)
            if task_points_service:
                task_points_service.clear_daily_points_for_reset(username, today_central)

            # Clear threshold tracking for this user for today (reset collaboration scoring)
            # This ensures future threshold calculations start from 0
            threshold_key = f"threshold_{today_central.isoformat()}_{username}"
            threshold_ref = self.db.collection('threshold_tracking').document(threshold_key)
            threshold_doc = threshold_ref.get()
            if threshold_doc.exists:
                threshold_ref.delete()
                self.logger.info(f"Cleared threshold tracking for {username} on {today_central}")
            
            # Get all active templates
            templates_query = self.db.collection('daily_task_templates').where('username', '==', username)
            templates_docs = templates_query.stream()
            
            today_weekday = self.get_effective_weekday(username, today_central)
            if today_weekday == TRAVEL_DAY_WEEKDAY:
                self.logger.info(f"Travel day mode enabled for {username}, using travel tasks")
            elif today_weekday == VACATION_WEEKDAY:
                self.logger.info(f"Vacation mode enabled for {username}, using Sunday tasks")

            instances_created = 0
            for template_doc in templates_docs:
                template_data = template_doc.to_dict()
                template_id = template_doc.id
                
                # Check if this template should run today
                days_of_week = template_data.get('days_of_week', [])
                if today_weekday in days_of_week:
                    # Create instance for today - explicitly set fields, do NOT set presented_at
                    instance_data = {
                        'username': username,
                        'template_id': template_id,
                        'description': template_data['description'],
                        'points': template_data['points'],
                        'is_backup': bool(template_data.get('is_backup', False)),
                        'date': today_central.isoformat(),
                        'completed': False,
                        'abandoned': False,  # Explicitly set to False
                        'created_at': firestore.SERVER_TIMESTAMP
                        # Note: presented_at is NOT set - new instances should not be presented yet
                    }
                    
                    self.db.collection('daily_task_instances').add(instance_data)
                    instances_created += 1
            
            # Record the reset
            reset_data = {
                'username': username,
                'last_reset_date': today_central.isoformat(),
                'last_reset_at': firestore.SERVER_TIMESTAMP
            }
            
            # Delete old reset records (keep only the latest)
            old_resets_query = self.db.collection('daily_task_resets').where('username', '==', username)
            old_resets_docs = old_resets_query.stream()
            
            for old_reset_doc in old_resets_docs:
                old_reset_doc.reference.delete()
            
            # Add new reset record
            self.db.collection('daily_task_resets').add(reset_data)
            
            self.logger.info(f"Created {instances_created} daily task instances for {username}")

            return instances_created
            
        except Exception as e:
            self.logger.error(f"Failed to reset daily tasks for {username}: {e}")
            return 0
