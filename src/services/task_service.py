"""
Task service - handles task-related business logic
"""
from google.cloud import firestore
from src.models.task import TaskModel, create_task_from_request_data
from src.utils.error_handlers import handle_exception
from typing import List, Dict, Any


class TaskService:
    """Service for task-related operations"""
    
    def __init__(self, app_manager, task_master):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.task_master = task_master
    
    def get_tasks(self, username: str) -> Dict[str, Any]:
        """Get active task session (5 tasks) and stats"""
        try:
            self.logger.debug(f"Getting tasks for username: {username}")
            
            # Use TaskMaster to get active session tasks
            tasks = self.task_master.get_active_session_tasks(username)
            
            self.logger.debug(f"Active session tasks for {username}: {len(tasks)}")
            
            # Get stats from daily_task_service
            from src.services.daily_task_service import DailyTaskService
            daily_task_service = DailyTaskService(self.app_manager)
            stats_data = daily_task_service.get_todays_instances(username)
            
            # Extract stats
            stats = {}
            if stats_data.get('status') == 'success':
                instances = stats_data.get('instances', [])
                stats = {
                    'total_instances': len(instances),
                    'completed_instances': len([i for i in instances if i.get('completed', False)]),
                    'total_points': stats_data.get('total_points', 0),
                    'completed_points': stats_data.get('completed_points', 0)
                }
        
            return {
                'status': 'success',
                'tasks': tasks,
                'stats': stats
            }
        except Exception as e:
            return handle_exception(e, f"Failed to get tasks for {username}")
    
    def get_task_statistics(self, username: str) -> Dict[str, Any]:
        """Get task counts by category"""
        try:
            self.logger.debug(f"Getting task statistics for username: {username}")
            
            # Get all tasks for user
            all_tasks_query = self.db.collection('tasks').where('username', '==', username)
            all_tasks = list(all_tasks_query.stream())
            
            # Initialize category counters
            categories = ["Work", "Kids", "Spouse", "House", "Self"]
            uncompleted_tasks_by_category = {cat: 0 for cat in categories}
            completed_tasks_by_category = {cat: 0 for cat in categories}
            
            # Count tasks by category and completion status
            for doc in all_tasks:
                task_data = doc.to_dict()
                category = task_data.get('category', 'Self')
                completed = task_data.get('completed', False)
                
                if category in categories:
                    if completed:
                        completed_tasks_by_category[category] += 1
                    else:
                        uncompleted_tasks_by_category[category] += 1
            
            # Calculate totals
            total_uncompleted = sum(uncompleted_tasks_by_category.values())
            total_completed = sum(completed_tasks_by_category.values())
            
            # Calculate minimum threshold status
            minimum_threshold_status = {}
            for category in categories:
                current = uncompleted_tasks_by_category[category]
                minimum_threshold_status[category] = {
                    'current': current,
                    'minimum': 5,
                    'below_minimum': current < 5
                }
            
            return {
                'status': 'success',
                'uncompleted_tasks_by_category': uncompleted_tasks_by_category,
                'completed_tasks_by_category': completed_tasks_by_category,
                'minimum_threshold_status': minimum_threshold_status,
                'total_uncompleted': total_uncompleted,
                'total_completed': total_completed
            }
        except Exception as e:
            return handle_exception(e, f"Failed to get task statistics for {username}")
    
    def create_task(self, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Create task"""
        try:
            if not data or not data.get('description'):
                return {'error': 'Task description is required'}
            
            # Create task model
            task_model = create_task_from_request_data(data, username)
            
            if not task_model.validate():
                return {'error': 'Invalid task data'}
            
            # Create new task in Firestore
            doc_ref = self.db.collection('tasks').add(task_model.to_firestore_dict())
            
            return {
                'status': 'success',
                'message': 'Task created successfully',
                'task_id': doc_ref[1].id
            }
        except Exception as e:
            return handle_exception(e, "Failed to create task")
    
    def complete_task(self, task_id: str, username: str) -> Dict[str, Any]:
        """Complete daily task and refresh session"""
        try:
            self.logger.debug(f"Completing daily task {task_id} for user {username}")
            
            # Verify the daily task instance belongs to this user
            doc_ref = self.db.collection('daily_task_instances').document(task_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                self.logger.error(f"Daily task instance {task_id} not found")
                return {
                    'status': 'error',
                    'message': 'Task not found'
                }
            
            instance_data = doc.to_dict()
            if instance_data.get('username') != username:
                self.logger.error(f"Daily task instance {task_id} belongs to {instance_data.get('username')}, not {username}")
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Task belongs to another user'
                }
            
            if instance_data.get('completed', False):
                return {
                    'status': 'error',
                    'message': 'Task already completed'
                }
            
            if instance_data.get('abandoned', False):
                return {
                    'status': 'error',
                    'message': 'Task has been abandoned'
                }
            
            self.logger.debug(f"Daily task instance {task_id} verified, calling TaskMaster")
            
            # Use TaskMaster to complete task and refresh session
            result = self.task_master.complete_task_and_refresh_session(username, task_id)
            
            self.logger.debug(f"TaskMaster returned {len(result['tasks'])} new tasks")
            
            # Check and update collaboration tracker on 100-point threshold
            # Use existing collaboration_service from app_manager
            collab_service = self.app_manager.collaboration_service
            collab_service.check_and_update_tracker_on_threshold(username)
            
            return {
                'status': 'success',
                'message': 'Task completed successfully',
                'new_tasks': result['tasks']
            }
        except Exception as e:
            return handle_exception(e, f"Error completing task {task_id}")
    
    def save_task(self, task_id: str, username: str) -> Dict[str, Any]:
        """Toggle save status"""
        try:
            doc_ref = self.db.collection('tasks').document(task_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Task not found'
                }
            
            task_data = doc.to_dict()
            if task_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Task belongs to another user'
                }
            
            current_saved = task_data.get('saved', False)
            doc_ref.update({
                'saved': not current_saved,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            return {
                'status': 'success',
                'message': f'Task {"saved" if not current_saved else "unsaved"} successfully'
            }
        except Exception as e:
            return handle_exception(e, "Failed to update task")
