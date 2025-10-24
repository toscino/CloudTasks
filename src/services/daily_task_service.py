"""
Daily Task Service - handles daily task templates and instances
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta
from src.utils.logger import logger
from src.utils.config import get_timezone, get_collection
from src.utils.firestore_helpers import prepare_firestore_document
from typing import List, Dict, Any


class DailyTaskService:
    """Service for daily task operations"""
    
    def __init__(self, db):
        self.db = db
        self.central_tz = get_timezone()
    
    def get_daily_tasks(self, username: str) -> Dict[str, Any]:
        """Get all daily task templates for user"""
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
            logger.error(f"Failed to get daily tasks for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get daily tasks: {str(e)}'
            }
    
    def create_daily_task(self, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Create a new daily task template"""
        try:
            if not data or not data.get('description'):
                return {'status': 'error', 'message': 'Task description is required'}
            
            if not data.get('points') or data.get('points') == 0:
                return {'status': 'error', 'message': 'Points cannot be zero'}
            if data.get('points') < -100 or data.get('points') > 100:
                return {'status': 'error', 'message': 'Points must be between -100 and 100'}
            
            if not data.get('days_of_week') or len(data.get('days_of_week', [])) == 0:
                return {'status': 'error', 'message': 'At least one day of week must be selected'}
            
            # Validate days_of_week (0=Monday, 6=Sunday)
            days_of_week = data.get('days_of_week', [])
            if not all(0 <= day <= 6 for day in days_of_week):
                return {'status': 'error', 'message': 'Invalid days of week'}
            
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
                logger.info(f"Created today's instance for new template {template_id}")
            
            return {
                'status': 'success',
                'message': 'Daily task created successfully',
                'template_id': template_id
            }
        except Exception as e:
            logger.error(f"Failed to create daily task for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to create daily task: {str(e)}'
            }
    
    def update_daily_task(self, task_id: str, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Update an existing daily task template"""
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
                    logger.info(f"Updated today's instance for template {task_id}")
            
            return {
                'status': 'success',
                'message': 'Daily task updated successfully'
            }
        except Exception as e:
            logger.error(f"Failed to update daily task {task_id} for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to update daily task: {str(e)}'
            }
    
    def delete_daily_task(self, task_id: str, username: str) -> Dict[str, Any]:
        """Delete a daily task template"""
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
            logger.error(f"Failed to delete daily task {task_id} for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to delete daily task: {str(e)}'
            }
    
    def get_todays_instances(self, username: str) -> Dict[str, Any]:
        """Get today's task instances (after checking if reset is needed)"""
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
            logger.error(f"Failed to get today's instances for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get today\'s instances: {str(e)}'
            }
    
    def complete_daily_task(self, instance_id: str, username: str) -> Dict[str, Any]:
        """Mark a daily task instance as complete"""
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
            
            return {
                'status': 'success',
                'message': 'Daily task completed successfully',
                'points_earned': instance_data.get('points', 0)
            }
        except Exception as e:
            logger.error(f"Failed to complete daily task {instance_id} for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to complete daily task: {str(e)}'
            }
    
    def check_and_reset_daily_tasks(self, username: str) -> Dict[str, Any]:
        """Check if daily tasks need to be reset (lazy reset on first access after 2am)"""
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
            
            # Need to reset - create new instances for today
            logger.info(f"Resetting daily tasks for {username} on {today_central}")
            
            # Before creating new instances, delete any existing instances for today
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', today_central.isoformat())
                ])
            )
            for instance in instances_query.stream():
                instance.reference.delete()
            logger.info(f"Deleted old instances for {username} on {today_central}")
            
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
                    # Create instance for today
                    instance_data = {
                        'username': username,
                        'template_id': template_id,
                        'description': template_data['description'],
                        'points': template_data['points'],
                        'date': today_central.isoformat(),
                        'completed': False,
                        'created_at': firestore.SERVER_TIMESTAMP
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
            
            logger.info(f"Created {instances_created} daily task instances for {username}")
            
            # Update tracker for all missed days since last update
            from src.services.collaboration_service import CollaborationService
            collab_service = CollaborationService(self.db)
            days_processed = collab_service.update_tracker_catch_up(today_central)
            logger.info(f"Updated collaboration tracker for {days_processed} days")
            
            # Reset morning cards
            from src.services.morning_card_service import MorningCardService
            morning_card_service = MorningCardService(self.db)
            morning_card_reset = morning_card_service.check_and_reset_cards()
            logger.info(f"Morning card reset: {morning_card_reset.get('message', 'unknown')}")
            
            return {
                'status': 'success',
                'message': f'Reset completed, created {instances_created} instances, updated tracker for {days_processed} days',
                'instances_created': instances_created,
                'tracker_days_processed': days_processed
            }
        except Exception as e:
            logger.error(f"Failed to reset daily tasks for {username}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to reset daily tasks: {str(e)}'
            }
