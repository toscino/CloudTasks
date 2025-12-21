"""
Daily Task Service - handles daily task templates and instances
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta
from src.utils.config import get_timezone, get_collection
from src.utils.firestore_helpers import prepare_firestore_document
from src.utils.exceptions import ValidationError, NotFoundError, UnauthorizedError, FirestoreError
from src.utils.error_handlers import handle_exception
from typing import List, Dict, Any


class DailyTaskService:
    """Service for daily task operations"""
    
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()
    
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
            
            # Validate days_of_week (0=Monday, 6=Sunday)
            days_of_week = data.get('days_of_week', [])
            if not all(0 <= day <= 6 for day in days_of_week):
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
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Create new template in Firestore
            doc_ref = self.db.collection('daily_task_templates').add(template_data)
            template_id = doc_ref[1].id
            
            # Check if today is in selected days and create instance
            today_central = datetime.now(self.central_tz).date()
            today_weekday = today_central.weekday()
            
            if today_weekday in days_of_week:
                instance_data = {
                    'username': username,
                    'template_id': template_id,
                    'description': data['description'].strip(),
                    'points': int(data['points']),
                    'date': today_central.isoformat(),
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
                if not all(0 <= day <= 6 for day in days_of_week):
                    return {'status': 'error', 'message': 'Invalid days of week'}
            
            # Update fields
            update_data = {'updated_at': firestore.SERVER_TIMESTAMP}
            if 'description' in data:
                update_data['description'] = data['description'].strip()
            if 'points' in data:
                update_data['points'] = int(data['points'])
            if 'days_of_week' in data:
                update_data['days_of_week'] = data['days_of_week']
            
            doc_ref.update(update_data)
            
            # Update today's instance if it exists
            today_central = datetime.now(self.central_tz).date()
            instance_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('template_id', '==', task_id),
                    FieldFilter('date', '==', today_central.isoformat())
                ])
            )
            instances = list(instance_query.stream())
            
            for instance_doc in instances:
                update_instance_data = {}
                if 'description' in update_data:
                    update_instance_data['description'] = update_data['description']
                if 'points' in update_data:
                    update_instance_data['points'] = update_data['points']
                
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
            
            # Get today's date in Central time
            today_central = datetime.now(self.central_tz).date()
            
            # Query today's instances
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', today_central.isoformat())
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
                'date': today_central.isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to get today's instances for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get today\'s instances: {str(e)}'
            }
    
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
            
            # Check and update tracker on 100-point threshold
            from src.services.collaboration_service import CollaborationService
            collab_service = CollaborationService(self.app_manager)
            collab_service.check_and_update_tracker_on_threshold(username)
            
            return {
                'status': 'success',
                'message': 'Daily task completed successfully',
                'points_earned': instance_data.get('points', 0)
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
        """Check and reset daily tasks after 2am"""
        try:
            now_central = datetime.now(self.central_tz)
            today_central = now_central.date()
            
            # Check if we've already reset today
            reset_query = self.db.collection('daily_task_resets').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('last_reset_date', '==', today_central.isoformat())
                ])
            )
            reset_docs = list(reset_query.stream())
            
            if reset_docs:
                # Already reset today
                return {'status': 'success', 'message': 'Already reset today'}
            
            # Check if it's past 2am today
            reset_time_today = datetime.combine(today_central, datetime.min.time().replace(hour=2))
            reset_time_today = self.central_tz.localize(reset_time_today)
            
            if now_central < reset_time_today:
                # Not yet 2am today, check if we need to reset from yesterday
                yesterday_central = today_central - timedelta(days=1)
                yesterday_reset_query = self.db.collection('daily_task_resets').where(
                    filter=firestore.And([
                        FieldFilter('username', '==', username),
                        FieldFilter('last_reset_date', '==', yesterday_central.isoformat())
                    ])
                )
                yesterday_reset_docs = list(yesterday_reset_query.stream())
                
                if yesterday_reset_docs:
                    # Reset yesterday, no need to reset today yet
                    return {'status': 'success', 'message': 'Reset not needed yet'}
            
            # Need to reset - reset for current user
            instances_created = self._reset_user_daily_tasks(username, today_central)
            
            # Also reset for spouse if linked
            user_service = getattr(self.app_manager, 'user_service', None)
            if not user_service:
                from src.services.user_service import UserService
                user_service = UserService(self.app_manager)
            
            user_settings = user_service.get_user_settings(username)
            spouse_username = user_settings.get('spouse_username')
            
            if spouse_username:
                self.logger.info(f"Also resetting daily tasks for spouse {spouse_username}")
                spouse_instances_created = self._reset_user_daily_tasks(spouse_username, today_central)
                instances_created += spouse_instances_created
            
            # Reset morning cards
            from src.services.morning_card_service import MorningCardService
            morning_card_service = MorningCardService(self.app_manager)
            morning_card_reset = morning_card_service.check_and_reset_cards()
            self.logger.info(f"Morning card reset: {morning_card_reset.get('message', 'unknown')}")
            
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
    
    def _reset_user_daily_tasks(self, username: str, today_central: date) -> int:
        """Reset daily tasks for a specific user (helper method)"""
        try:
            self.logger.info(f"Resetting daily tasks for {username} on {today_central}")
            
            # Before creating new instances, delete any existing instances for today
            # This includes ALL instances regardless of status (completed, abandoned, presented)
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', today_central.isoformat())
                ])
            )
            deleted_count = 0
            for instance in instances_query.stream():
                instance.reference.delete()
                deleted_count += 1
            self.logger.info(f"Deleted {deleted_count} old instances for {username} on {today_central}")
            
            # Clear threshold tracking for this user for today (reset collaboration scoring)
            threshold_key = f"threshold_{today_central.isoformat()}_{username}"
            threshold_ref = self.db.collection('threshold_tracking').document(threshold_key)
            threshold_doc = threshold_ref.get()
            if threshold_doc.exists:
                threshold_ref.delete()
                self.logger.info(f"Cleared threshold tracking for {username} on {today_central}")
            
            # Get all active templates
            templates_query = self.db.collection('daily_task_templates').where('username', '==', username)
            templates_docs = templates_query.stream()
            
            today_weekday = today_central.weekday()  # 0=Monday, 6=Sunday
            
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
