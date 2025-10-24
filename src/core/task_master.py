"""
TaskMaster - Manages task creation and ensures minimum task counts per category
"""
import random
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, timedelta
import pytz
from .task_generator import TaskGenerator
from src.utils.logger import logger


class TaskMaster:
    """Manages task creation and ensures minimum task counts per category"""
    
    CATEGORIES = ["Work", "Kids", "Spouse", "House", "Self"]
    MIN_TASKS_PER_CATEGORY = 5
    TASKS_TO_ADD_IF_BELOW_MIN = 10
    
    # Time-based category weights for different users and time periods
    TIME_WEIGHTS = {
        "Ian": {
            "morning": {"Work": 0, "Kids": 2, "Spouse": 3, "House": 1, "Self": 4},
            "workday": {"Work": 1, "Kids": 0, "Spouse": 2, "House": 10,"Self": 4},
            "evening": {"Work": 0, "Kids": 5, "Spouse": 4, "House": 2, "Self": 2},
            "weekend": {"Work": 0, "Kids": 3, "Spouse": 2, "House": 3, "Self": 1}
        },
        "Karleigh": {
            "morning": {"Work": 0, "Kids": 1, "Spouse": 4, "House": 1, "Self": 4},
            "workday": {"Work": 10,"Kids": 0, "Spouse": 2, "House": 0, "Self": 4},
            "evening": {"Work": 0, "Kids": 5, "Spouse": 4, "House": 2, "Self": 2},
            "weekend": {"Work": 1, "Kids": 3, "Spouse": 2, "House": 2, "Self": 1}
        },
        "default": {
            "morning": {"Work": 1, "Kids": 1, "Spouse": 1, "House": 1, "Self": 1},
            "workday": {"Work": 1, "Kids": 1, "Spouse": 1, "House": 1, "Self": 1},
            "evening": {"Work": 1, "Kids": 1, "Spouse": 1, "House": 1, "Self": 1},
            "weekend": {"Work": 1, "Kids": 1, "Spouse": 1, "House": 1, "Self": 1}
        }
    }
    
    def __init__(self, db):
        self.db = db
        self.task_generator = TaskGenerator(db)
        # Import RewardMaster here to avoid circular imports
        from .reward_master import RewardMaster
        self.reward_master = RewardMaster(db)
        # Import ChallengeMaster here to avoid circular imports
        from .challenge_master import ChallengeMaster
        self.challenge_master = ChallengeMaster(db)
    
    def earn_reward(self, user, difficulty):
        """Check if user earns a reward based on task difficulty"""
        difficulty = difficulty ** 1.5
        if difficulty > random.randint(0, 40):
            return True
        return False
    
    def _get_time_period(self):
        """Determine current time period based on time and day (using Chicago timezone)"""
        # Use Chicago timezone for consistent time-based task selection
        local_tz = pytz.timezone('US/Central')
        now = datetime.now(local_tz)
        current_hour = now.hour
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # Weekend detection
        if current_weekday >= 5:  # Saturday=5, Sunday=6
            return "weekend"
        
        # Weekday time periods (workday is 8am-3pm)
        if 6 <= current_hour < 8:
            return "morning"
        elif 8 <= current_hour < 16:  # 4pm = 16:00
            return "workday"
        else:
            return "evening"
    
    def _get_time_based_weights(self, username):
        """Get time-based category weights for user"""
        time_period = self._get_time_period()
        
        # Get user-specific weights or default to equal weights
        if username in self.TIME_WEIGHTS:
            user_weights = self.TIME_WEIGHTS[username]
        else:
            user_weights = self.TIME_WEIGHTS["default"]
        return user_weights.get(time_period, self.TIME_WEIGHTS["default"]["workday"])
    
    def _sanitize_task_data(self, task_data):
        """Convert Firestore timestamps to datetime objects for JSON serialization"""
        timestamp_fields = ['created_at', 'updated_at', 'presented_at']
        current_time = datetime.now()
        
        for field in timestamp_fields:
            if field in task_data:
                value = task_data[field]
                # Convert Firestore timestamp to datetime if needed
                if hasattr(value, 'timestamp'):
                    task_data[field] = datetime.fromtimestamp(value.timestamp())
               
        # Ensure new AI fields have default values for backward compatibility
        if 'difficulty' not in task_data:
            task_data['difficulty'] = 3  # Default difficulty
        if 'duration' not in task_data:
            task_data['duration'] = 10  # Default duration in minutes
            
        return task_data
    
    def ensure_minimum_tasks(self, username):
        """Ensure user has at least MIN_TASKS_PER_CATEGORY tasks in each category"""
        # Use database-based locking for App Engine compatibility
        lock_key = f"task_generation_lock_{username}"
        
        try:
            # Try to acquire lock (create document if it doesn't exist)
            lock_ref = self.db.collection('generation_locks').document(lock_key)
            lock_doc = lock_ref.get()
            
            if lock_doc.exists:
                lock_data = lock_doc.to_dict()
                # Check if lock is still valid (not expired)
                lock_time = lock_data.get('locked_at')
                if lock_time and hasattr(lock_time, 'timestamp'):
                    lock_age = datetime.now() - datetime.fromtimestamp(lock_time.timestamp())
                    if lock_age.total_seconds() < 300:  # 5 minute timeout
                        logger.debug(f"Task generation already in progress for {username}, skipping")
                        return
                else:
                    logger.debug(f"Invalid lock data for {username}, proceeding")
            
            # Acquire lock
            lock_ref.set({
                'username': username,
                'locked_at': firestore.SERVER_TIMESTAMP,
                'type': 'task_generation'
            })
            
            logger.info(f"Ensuring minimum tasks for {username}")
            for category in self.CATEGORIES:
                count = self._count_tasks_in_category(username, category)
                logger.debug(f"Category {category}: {count} tasks (minimum: {self.MIN_TASKS_PER_CATEGORY})")
                logger.ensure_minimum_check(username, f"tasks_{category}", count, self.MIN_TASKS_PER_CATEGORY)
                if count < self.MIN_TASKS_PER_CATEGORY:
                    logger.debug(f"Generating {self.TASKS_TO_ADD_IF_BELOW_MIN} {category} tasks for {username}")
                    try:
                        result = self.task_generator.generate_tasks_for_category(username, category, self.TASKS_TO_ADD_IF_BELOW_MIN, upload_to_firestore=True)
                        generated_count = len(result) if result else 0
                        logger.debug(f"Generated {generated_count} {category} tasks for {username}")
                        logger.ensure_minimum_check(username, f"tasks_{category}", count, self.MIN_TASKS_PER_CATEGORY, generated_count)
                    except Exception as e:
                        logger.error(f"Failed to generate {category} tasks for {username}: {e}")
                else:
                    logger.debug(f"Category {category} has sufficient tasks ({count} >= {self.MIN_TASKS_PER_CATEGORY})")
            
            # Release lock
            lock_ref.delete()
            logger.debug(f"Released task generation lock for {username}")
            
        except Exception as e:
            logger.error(f"Failed to ensure minimum tasks for {username}: {e}")
            # Try to release lock on error
            try:
                lock_ref.delete()
            except:
                pass
    
    def _count_tasks_in_category(self, username, category):
        """Count queue tasks (unpresented tasks) for a user in a specific category
        
        Counts only unpresented tasks (presented_at == None) - these are the tasks
        available in the queue for selection.
        """
        try:
            # Get unpresented tasks for this category
            tasks_query = self.db.collection('tasks').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('category', '==', category),
                    FieldFilter('completed', '==', False),
                    FieldFilter('presented_at', '==', None)
                ])
            )
            
            tasks_docs = list(tasks_query.stream())
            return len(tasks_docs)
            
        except Exception as e:
            logger.error(f"Error counting unpresented tasks in category {category} for {username}: {e}")
            return 0
    
    def _select_tasks_with_weights(self, username, unpresented_tasks, tasks_needed):
        """Selects tasks using a dynamic weighted-choice algorithm."""
        if not unpresented_tasks or tasks_needed <= 0:
            return []

        # 1. Group available tasks by category
        tasks_by_category = {}
        for task in unpresented_tasks:
            category = task.get('category', 'Self')
            tasks_by_category.setdefault(category, []).append(task)
        
        # 2. Get the initial weights for categories that have tasks
        weights = self._get_time_based_weights(username)
        
        # Create lists of categories and their corresponding weights for random.choices
        # Only include categories that actually have tasks available.
        available_categories = [cat for cat in tasks_by_category if cat in weights and weights[cat] > 0]
        category_weights = [weights[cat] for cat in available_categories]

        logger.info(f"Available tasks by category: {[(cat, len(tasks)) for cat, tasks in tasks_by_category.items()]}")
        logger.debug(f"Initial weights for selection: {list(zip(available_categories, category_weights))}")

        selected_tasks = []
        # 3. Iteratively select tasks until we have enough or run out of options
        while len(selected_tasks) < tasks_needed and available_categories:
            # Choose a category based on the current weights
            chosen_category = random.choices(available_categories, weights=category_weights, k=1)[0]
            
            # Select and remove a random task from that category's list
            tasks_in_category = tasks_by_category[chosen_category]
            selected_task = tasks_in_category.pop(random.randrange(len(tasks_in_category)))
            
            selected_tasks.append(selected_task)
            logger.debug(f"Selected '{chosen_category}' task (weight: {weights.get(chosen_category, 0)})")

            # If a category has run out of tasks, remove it from future selections
            if not tasks_in_category:
                logger.debug(f"Category '{chosen_category}' is now empty. Removing from selection pool.")
                idx = available_categories.index(chosen_category)
                available_categories.pop(idx)
                category_weights.pop(idx)


        logger.debug(f"Final selection count: {len(selected_tasks)}")
        return selected_tasks    
    
    def get_active_session_tasks(self, username):
        """Get current active task session (4 tasks) for user"""
        try:
            # First, check if we have enough active presented tasks
            local_tz = pytz.timezone('US/Central')
            current_time = datetime.now(local_tz)
            
            # Get all incomplete tasks and filter for presented ones in Python
            # Note: Can't use != None in Firestore, so we get all tasks and filter
            presented_query = self.db.collection('tasks').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('completed', '==', False)
                ])
            )
            
            active_presented_tasks = []
            for doc in presented_query.stream():
                task_data = doc.to_dict()
                task_data['id'] = doc.id
                task_data = self._sanitize_task_data(task_data)
                
                presented_at = task_data.get('presented_at')
                # Check if task has been presented (not None/null)
                if presented_at is not None:
                    # Convert Firestore timestamp to datetime if needed
                    if hasattr(presented_at, 'timestamp'):
                        presented_datetime = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                    else:
                        presented_datetime = presented_at
                    
                    # Check if task is expired (2 hours old) OR if it's saved
                    is_saved = task_data.get('saved', False)
                    is_recent = current_time - presented_datetime < timedelta(hours=2)
                    age_hours = (current_time - presented_datetime).total_seconds() / 3600
                    
                    if is_recent or is_saved:
                        active_presented_tasks.append(task_data)
                        logger.debug(f"Task {task_data.get('id', 'unknown')} active: saved={is_saved}, age={age_hours:.1f}h")
                    else:
                        logger.debug(f"Deleting expired task {task_data.get('id', 'unknown')}: saved={is_saved}, age={age_hours:.1f}h")
                        # Delete the expired task immediately
                        self.db.collection('tasks').document(task_data['id']).delete()
            
            # If we have 4+ active presented tasks, return them immediately
            if len(active_presented_tasks) >= 4:
                logger.debug(f"Returning {len(active_presented_tasks)} existing active tasks for {username}")
                return active_presented_tasks[:4]
            
            # Otherwise, we need to create a new session
            logger.debug(f"Only {len(active_presented_tasks)} active presented tasks, creating new session for {username}")
            
            # Create new session with available presented tasks
            return self.create_new_task_session(username, active_presented_tasks)
            
        except Exception as e:
            logger.error(f"Error getting active session tasks for {username}: {e}")
            return []
    
    def create_new_task_session(self, username, existing_saved_tasks=None):
        """Create a new task session with 4 tasks using time-based weights"""
        try:
            # Get saved tasks with database filter
            saved_query = self.db.collection('tasks').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('completed', '==', False),
                    FieldFilter('saved', '==', True)
                ])
            )
            saved_tasks = []
            for doc in saved_query.stream():
                task_data = doc.to_dict()
                task_data['id'] = doc.id
                task_data = self._sanitize_task_data(task_data)
                saved_tasks.append(task_data)
            
            # Use provided saved tasks or get fresh ones
            if existing_saved_tasks is None:
                existing_saved_tasks = saved_tasks
            else:
                # Merge provided saved tasks with any new saved tasks from database
                provided_saved_ids = {t['id'] for t in existing_saved_tasks}
                new_saved_tasks = [t for t in saved_tasks if t['id'] not in provided_saved_ids]
                existing_saved_tasks.extend(new_saved_tasks)
            
            # Calculate how many new tasks we need
            tasks_needed = 4 - len(existing_saved_tasks)
            
            # If we have enough saved tasks, just return them
            if tasks_needed <= 0:
                logger.debug(f"Have {len(existing_saved_tasks)} saved tasks, returning them directly")
                return existing_saved_tasks[:4]
            
            # Get unpresented tasks directly with database filter
            # NO INDEX NEEDED: Multiple equality filters only (after standardizing presented_at to null)
            unsaved_query = self.db.collection('tasks').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('completed', '==', False),
                    FieldFilter('saved', '==', False),
                    FieldFilter('presented_at', '==', None)
                ])
            )
            unpresented_tasks = []
            for doc in unsaved_query.stream():
                task_data = doc.to_dict()
                task_data['id'] = doc.id
                task_data = self._sanitize_task_data(task_data)
                unpresented_tasks.append(task_data)
            
            logger.debug(f"Fetched {len(unpresented_tasks)} unpresented tasks from database")
            
            # Select tasks using time-based weights
            selected_tasks = self._select_tasks_with_weights(username, unpresented_tasks, tasks_needed)
            
            # Mark selected tasks as presented
            new_tasks = []
            for task in selected_tasks:
                task_ref = self.db.collection('tasks').document(task['id'])
                task_ref.update({
                    'presented_at': firestore.SERVER_TIMESTAMP
                })
                local_tz = pytz.timezone('US/Central')
                task['presented_at'] = datetime.now(local_tz)  # For immediate use
                task = self._sanitize_task_data(task)
                new_tasks.append(task)
            
            # If we don't have enough tasks, just work with what we have
            additional_needed = tasks_needed - len(new_tasks)
            if additional_needed > 0:
                logger.debug(f"Only {len(new_tasks)} unpresented tasks available, providing available tasks")
                # Note: Task generation will happen in background ensure_minimum_tasks() call
            
            # Combine saved tasks with new tasks
            all_tasks = existing_saved_tasks + new_tasks
            
            return all_tasks[:4]  # Return up to 4 tasks (may be fewer)
            
        except Exception as e:
            logger.error(f"Error creating new task session for {username}: {e}")
            return []
    
    def complete_task_and_refresh_session(self, username, completed_task_id):
        """Complete a task and refresh the entire session"""
        try:
            # First, get the current session tasks BEFORE marking as completed
            current_tasks = self.get_active_session_tasks(username)
            
            # Find the completed task to get its difficulty
            completed_task = None
            for task in current_tasks:
                if task['id'] == completed_task_id:
                    completed_task = task
                    break
            
            # Mark the completed task as completed
            completed_task_ref = self.db.collection('tasks').document(completed_task_id)
            completed_task_ref.update({
                'completed': True,
                'completed_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Check if this task is from a one-and-done goal that needs cleanup
            goal_id = completed_task.get('goal_id') if completed_task else None
            if goal_id:
                # Fetch the goal to check if it's a one-and-done goal
                goal_ref = self.db.collection('goals').document(goal_id)
                goal_doc = goal_ref.get()
                
                if goal_doc.exists:
                    goal_data = goal_doc.to_dict()
                    delete_on_complete = goal_data.get('delete_on_complete', False)
                    
                    if delete_on_complete:
                        logger.debug(f"Task {completed_task_id} is from one-and-done goal {goal_id}, cleaning up all tasks and goal")
                        
                        # Delete all tasks with this goal_id (including saved tasks)
                        remaining_tasks_query = self.db.collection('tasks').where(
                            filter=FieldFilter('goal_id', '==', goal_id)
                        )
                        remaining_tasks_docs = list(remaining_tasks_query.stream())
                        
                        deleted_count = 0
                        for task_doc in remaining_tasks_docs:
                            try:
                                task_doc.reference.delete()
                                deleted_count += 1
                            except Exception as e:
                                logger.debug(f"Failed to delete task {task_doc.id}: {e}")
                        
                        logger.debug(f"Deleted {deleted_count} tasks for one-and-done goal {goal_id}")
                        
                        # Delete the goal itself
                        try:
                            goal_ref.delete()
                            logger.debug(f"Deleted one-and-done goal {goal_id}")
                        except Exception as e:
                            logger.debug(f"Failed to delete goal {goal_id}: {e}")
            
            # Check if user earns a reward
            reward_earned = False
            if completed_task:
                difficulty = completed_task.get('difficulty', 3)
                reward_earned = self.earn_reward(username, difficulty)
                logger.task_completion(username, completed_task_id, difficulty, reward_earned)
                
                # If reward earned, store it in database for later selection
                if reward_earned:
                    logger.debug(f"Storing earned reward for {username}")
                    try:
                        reward_data = {
                            'username': username,
                            'earned_at': firestore.SERVER_TIMESTAMP,
                            'task_id': completed_task_id,
                            'task_difficulty': difficulty,
                            'status': 'pending',  # pending, selected, expired
                            'created_at': firestore.SERVER_TIMESTAMP,
                            'updated_at': firestore.SERVER_TIMESTAMP
                        }
                        self.db.collection('earned_rewards').add(reward_data)
                        logger.debug(f"Stored earned reward for {username}")
                    except Exception as e:
                        logger.error(f"Failed to store earned reward for {username}: {e}")
            
            # Delete all non-saved tasks from current session (except the completed one)
            for task in current_tasks:
                if not task.get('saved', False) and task['id'] != completed_task_id:
                    self.db.collection('tasks').document(task['id']).delete()
            
            # Create new session with 4 fresh tasks (saved tasks will be fetched automatically)
            new_session = self.create_new_task_session(username)
            
            # Return session with reward information
            return {
                'tasks': new_session,
                'reward_earned': reward_earned
            }
            
        except Exception as e:
            logger.error(f"Error completing task and refreshing session for {username}: {e}")
            return {'tasks': [], 'reward_earned': False}
    
