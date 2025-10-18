"""
Task service - handles task-related business logic
"""
from google.cloud import firestore
from src.models.task import TaskModel, create_task_from_request_data
from src.utils.background_tasks import ensure_minimums
from src.utils.logger import logger
from typing import List, Dict, Any


class TaskService:
    """Service for task-related operations"""
    
    def __init__(self, db, task_master):
        self.db = db
        self.task_master = task_master
    
    def get_tasks(self, username: str) -> Dict[str, Any]:
        """Get active task session (4 tasks) for current user"""
        try:
            logger.debug(f"Getting tasks for username: {username}")
            
            # Use TaskMaster to get active session tasks (fast - no AI calls)
            tasks = self.task_master.get_active_session_tasks(username)
            
            logger.debug(f"Active session tasks for {username}: {len(tasks)}")
            
            # Fire off background task generation (non-blocking)
            ensure_minimums(self.task_master, username, check_tasks=True, check_rewards=False, check_challenges=False)
        
            return {
                'status': 'success',
                'tasks': tasks
            }
        except Exception as e:
            logger.error(f"Failed to get tasks for {username}: {str(e)}")
            return {
                'status': 'error',
                'message': f'Failed to get tasks: {str(e)}'
            }
    
    def get_task_statistics(self, username: str) -> Dict[str, Any]:
        """Get task statistics including counts by category"""
        try:
            logger.debug(f"Getting task statistics for username: {username}")
            
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
            logger.error(f"Failed to get task statistics for {username}: {str(e)}")
            return {
                'status': 'error',
                'message': f'Failed to get task statistics: {str(e)}'
            }
    
    def create_task(self, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Create a new task"""
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
            return {
                'status': 'error',
                'message': f'Failed to create task: {str(e)}'
            }
    
    def complete_task(self, task_id: str, username: str) -> Dict[str, Any]:
        """Mark a task as completed and refresh the task session"""
        try:
            logger.debug(f"Completing task {task_id} for user {username}")
            
            # Verify the task belongs to this user
            doc_ref = self.db.collection('tasks').document(task_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Task {task_id} not found")
                return {
                    'status': 'error',
                    'message': 'Task not found'
                }
            
            task_data = doc.to_dict()
            if task_data.get('username') != username:
                logger.error(f"Task {task_id} belongs to {task_data.get('username')}, not {username}")
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Task belongs to another user'
                }
            
            logger.debug(f"Task {task_id} verified, calling TaskMaster")
            
            # Use TaskMaster to complete task and refresh session
            result = self.task_master.complete_task_and_refresh_session(username, task_id)
            
            logger.debug(f"TaskMaster returned {len(result['tasks'])} new tasks, reward earned: {result['reward_earned']}")
            
            return {
                'status': 'success',
                'message': 'Task completed successfully',
                'new_tasks': result['tasks'],
                'reward_earned': result['reward_earned']
            }
        except Exception as e:
            logger.error(f"Error completing task {task_id}: {str(e)}")
            return {
                'status': 'error',
                'message': f'Failed to complete task: {str(e)}'
            }
    
    def save_task(self, task_id: str, username: str) -> Dict[str, Any]:
        """Toggle save status for a task"""
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
            return {
                'status': 'error',
                'message': f'Failed to update task: {str(e)}'
            }
