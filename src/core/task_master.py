"""
TaskMaster - Manages task selection from daily tasks using point-based selection
"""
import random
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime
import pytz
from src.utils.logger import logger
from src.utils.config import get_spouse
from src.utils.random_selection import resolve_random_selection


class TaskMaster:
    """Manages task selection from daily tasks using point-based selection"""
    
    def __init__(self, db):
        self.db = db
    
    def _sanitize_task_data(self, task_data):
        """Convert Firestore timestamps for JSON serialization"""
        timestamp_fields = ['created_at', 'updated_at', 'presented_at']
        current_time = datetime.now()
        
        for field in timestamp_fields:
            if field in task_data:
                value = task_data[field]
                # Convert Firestore timestamp to datetime if needed
                if hasattr(value, 'timestamp'):
                    task_data[field] = datetime.fromtimestamp(value.timestamp())
               
        # Ensure fields have default values for backward compatibility
        if 'difficulty' not in task_data:
            task_data['difficulty'] = 3  # Default difficulty
        if 'duration' not in task_data:
            task_data['duration'] = 10  # Default duration in minutes
            
        return task_data
    
    def _select_tasks_by_points(self, username, tasks_needed=5, exclude_task_ids=None):
        """Select tasks by point value (largest absolute points first)"""
        try:
            local_tz = pytz.timezone('US/Central')
            today_central = datetime.now(local_tz).date()
            
            # Get all daily task instances for today (not completed, not abandoned)
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', today_central.isoformat()),
                    FieldFilter('completed', '==', False)
                ])
            )
            
            available_tasks = []
            seen_instance_ids = set()  # Prevent duplicates from query
            
            for doc in instances_query.stream():
                instance_id = doc.id
                
                # Skip if we've already seen this instance ID (duplicate prevention)
                if instance_id in seen_instance_ids:
                    logger.warning(f"Duplicate instance ID detected in query: {instance_id} for {username}")
                    continue
                seen_instance_ids.add(instance_id)
                
                instance_data = doc.to_dict()
                instance_data['id'] = instance_id
                
                # Skip abandoned tasks
                if instance_data.get('abandoned', False):
                    continue
                
                # Skip excluded tasks
                if exclude_task_ids and instance_id in exclude_task_ids:
                    continue
                
                # Skip tasks that are already presented (unless we're refreshing)
                if instance_data.get('presented_at'):
                    continue
                
                available_tasks.append(instance_data)
            
            if not available_tasks:
                logger.debug(f"No available tasks for {username}")
                return []
            
            # Group tasks by absolute point value (descending)
            tasks_by_points = {}
            for task in available_tasks:
                points = abs(task.get('points', 0))
                if points not in tasks_by_points:
                    tasks_by_points[points] = []
                tasks_by_points[points].append(task)
            
            # Sort point values descending
            sorted_point_values = sorted(tasks_by_points.keys(), reverse=True)
            
            selected_tasks = []
            # Select tasks starting from highest point tier
            for point_value in sorted_point_values:
                tasks_at_tier = tasks_by_points[point_value]
                # Randomly shuffle tasks at this tier
                random.shuffle(tasks_at_tier)
                
                # Select up to remaining needed tasks from this tier
                remaining_needed = tasks_needed - len(selected_tasks)
                if remaining_needed <= 0:
                    break
                
                selected_from_tier = tasks_at_tier[:remaining_needed]
                selected_tasks.extend(selected_from_tier)
                
                if len(selected_tasks) >= tasks_needed:
                    break
            
            logger.debug(f"Selected {len(selected_tasks)} tasks by points for {username} (from {len(available_tasks)} available, needed {tasks_needed})")
            return selected_tasks[:tasks_needed]
            
        except Exception as e:
            logger.error(f"Error selecting tasks by points for {username}: {e}")
            return []    
    
    def get_active_session_tasks(self, username):
        """Get active task session (up to 5 tasks, fewer if not enough available)"""
        try:
            local_tz = pytz.timezone('US/Central')
            today_central = datetime.now(local_tz).date()
            now = datetime.now(local_tz)
            
            # Get all daily task instances for today (not completed, not abandoned)
            instances_query = self.db.collection('daily_task_instances').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('date', '==', today_central.isoformat()),
                    FieldFilter('completed', '==', False)
                ])
            )
            
            active_presented_tasks = []
            seen_instance_ids = set()  # Prevent duplicates from query
            
            for doc in instances_query.stream():
                instance_id = doc.id
                
                # Skip if we've already seen this instance ID (duplicate prevention)
                if instance_id in seen_instance_ids:
                    logger.warning(f"Duplicate instance ID detected in get_active_session_tasks: {instance_id} for {username}")
                    continue
                seen_instance_ids.add(instance_id)
                
                instance_data = doc.to_dict()
                
                # Skip abandoned tasks
                if instance_data.get('abandoned', False):
                    continue
                
                # Check if task has been presented
                presented_at = instance_data.get('presented_at')
                if presented_at is not None:
                    # Format for frontend compatibility
                    instance_data['id'] = instance_id
                    
                    # Check if description still has unresolved patterns (shouldn't happen, but handle gracefully)
                    description = instance_data.get('description', '')
                    if '[' in description and ']' in description:
                        # Still has unresolved pattern, resolve it now
                        resolved_description = resolve_random_selection(description)
                        instance_data['description'] = resolved_description
                        # Update instance in database
                        task_ref = self.db.collection('daily_task_instances').document(instance_id)
                        task_ref.update({'description': resolved_description})
                    else:
                        instance_data['description'] = description
                    
                    instance_data['points'] = instance_data.get('points', 0)
                    instance_data['difficulty'] = instance_data.get('points', 0)  # Use points as difficulty for display
                    instance_data['category'] = 'Daily'
                    instance_data['type'] = 'daily'
                    active_presented_tasks.append(instance_data)
            
            # If we have 5+ active presented tasks, return first 5
            if len(active_presented_tasks) >= 5:
                logger.debug(f"Returning {len(active_presented_tasks)} existing active tasks for {username}, showing 5 (checked {len(seen_instance_ids)} unique instances)")
                return active_presented_tasks[:5]
            
            # Otherwise, we need to create a new session
            logger.debug(f"Only {len(active_presented_tasks)} active presented tasks, creating new session for {username} (checked {len(seen_instance_ids)} unique instances)")
            
            # Create new session with available presented tasks
            return self.create_new_task_session(username, active_presented_tasks)
            
        except Exception as e:
            logger.error(f"Error getting active session tasks for {username}: {e}")
            return []
    
    def create_new_task_session(self, username, existing_presented_tasks=None):
        """Create new task session (up to 5 tasks, fewer if not enough available)"""
        try:
            # Use provided presented tasks or start fresh
            if existing_presented_tasks is None:
                existing_presented_tasks = []
            
            # Deduplicate existing tasks by ID
            seen_ids = set()
            deduplicated_existing = []
            for task in existing_presented_tasks:
                if task['id'] not in seen_ids:
                    seen_ids.add(task['id'])
                    deduplicated_existing.append(task)
                else:
                    logger.warning(f"Duplicate task ID in existing_presented_tasks: {task['id']} for {username}")
            
            existing_presented_tasks = deduplicated_existing
            
            # Calculate how many new tasks we need (up to 5 total)
            max_tasks = 5
            tasks_needed = max_tasks - len(existing_presented_tasks)
            
            # If we have enough tasks, just return them
            if tasks_needed <= 0:
                logger.debug(f"Have {len(existing_presented_tasks)} presented tasks, returning them directly")
                return existing_presented_tasks[:max_tasks]
            
            # Get IDs of tasks already in session to exclude them
            exclude_task_ids = {t['id'] for t in existing_presented_tasks}
            
            logger.debug(f"Creating new session for {username}: {len(existing_presented_tasks)} existing, need {tasks_needed} more")
            
            # Select tasks using point-based selection (may return fewer than requested)
            selected_tasks = self._select_tasks_by_points(username, tasks_needed, exclude_task_ids)
            
            # Mark selected tasks as presented
            new_tasks = []
            for task in selected_tasks:
                # Double-check we're not duplicating
                if task['id'] in exclude_task_ids:
                    logger.warning(f"Attempted to add duplicate task {task['id']} to session for {username}")
                    continue
                
                # Resolve random selections in description before presenting
                original_description = task.get('description', '')
                resolved_description = resolve_random_selection(original_description)
                
                task_ref = self.db.collection('daily_task_instances').document(task['id'])
                task_ref.update({
                    'presented_at': firestore.SERVER_TIMESTAMP,
                    'description': resolved_description  # Store resolved description in instance
                })
                local_tz = pytz.timezone('US/Central')
                task['presented_at'] = datetime.now(local_tz)  # For immediate use
                
                # Format for frontend compatibility (use resolved description)
                task['description'] = resolved_description
                task['points'] = task.get('points', 0)
                task['difficulty'] = task.get('points', 0)  # Use points as difficulty for display
                task['category'] = 'Daily'
                task['type'] = 'daily'
                
                new_tasks.append(task)
                exclude_task_ids.add(task['id'])  # Prevent duplicates
            
            # Combine existing tasks with new tasks
            all_tasks = existing_presented_tasks + new_tasks
            
            logger.debug(f"Created new session with {len(all_tasks)} tasks for {username} (max 5)")
            return all_tasks[:max_tasks]  # Return up to 5 tasks (may be fewer if not enough available)
            
        except Exception as e:
            logger.error(f"Error creating new task session for {username}: {e}")
            return []
    
    def complete_task_and_refresh_session(self, username, completed_task_id):
        """Complete daily task and refresh session"""
        try:
            # First, get the current session tasks BEFORE marking as completed
            current_tasks = self.get_active_session_tasks(username)
            
            # Find the completed task
            completed_task = None
            for task in current_tasks:
                if task['id'] == completed_task_id:
                    completed_task = task
                    break
            
            if not completed_task:
                logger.error(f"Task {completed_task_id} not found in current session for {username}")
                return {'tasks': current_tasks}
            
            # Mark daily task instance as completed
            completed_task_ref = self.db.collection('daily_task_instances').document(completed_task_id)
            completed_task_ref.update({
                'completed': True,
                'completed_at': firestore.SERVER_TIMESTAMP
            })
            
            logger.debug(f"Marked daily task {completed_task_id} as completed for {username}")
            
            # Check and update tracker on 100-point threshold
            # Note: This is called from task_master, so we need to create a minimal service
            # Since we can't easily access app_manager here, we'll skip threshold check
            # The threshold check will be handled in daily_task_service.complete_daily_task
            # which is called from the API endpoint
            
            # Remove completed task from current session
            remaining_tasks = [t for t in current_tasks if t['id'] != completed_task_id]
            
            # Get IDs of tasks already in session (including remaining ones)
            exclude_task_ids = {t['id'] for t in remaining_tasks}
            
            # Get 1 replacement task using point-based selection
            replacement_tasks = self._select_tasks_by_points(username, tasks_needed=1, exclude_task_ids=exclude_task_ids)
            
            # Mark replacement task as presented and resolve random selections
            for task in replacement_tasks:
                # Resolve random selections in description before presenting
                original_description = task.get('description', '')
                resolved_description = resolve_random_selection(original_description)
                
                task_ref = self.db.collection('daily_task_instances').document(task['id'])
                task_ref.update({
                    'presented_at': firestore.SERVER_TIMESTAMP,
                    'description': resolved_description  # Store resolved description in instance
                })
                local_tz = pytz.timezone('US/Central')
                task['presented_at'] = datetime.now(local_tz)
                
                # Format for frontend compatibility (use resolved description)
                task['description'] = resolved_description
                task['points'] = task.get('points', 0)
                task['difficulty'] = task.get('points', 0)
                task['category'] = 'Daily'
                task['type'] = 'daily'
            
            # Combine remaining tasks with replacement
            new_session = remaining_tasks + replacement_tasks
            
            # Deduplicate by task ID
            seen_ids = set()
            deduplicated_session = []
            for task in new_session:
                if task['id'] not in seen_ids:
                    seen_ids.add(task['id'])
                    deduplicated_session.append(task)
            
            logger.debug(f"Refreshed session: {len(deduplicated_session)} tasks for {username} (max 5)")
            
            # Return session
            return {
                'tasks': deduplicated_session[:5]  # Ensure max 5 tasks, but may be fewer
            }
            
        except Exception as e:
            logger.error(f"Error completing task and refreshing session for {username}: {e}")
            return {'tasks': []}
    
