"""
ChallengeMaster - Manages challenge creation and ensures minimum challenge counts per reward goal
Challenges are tasks completed by spouse to fulfill earned rewards
"""
import random
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, timedelta
import pytz
from .task_generator import TaskGenerator
from src.utils.logger import logger


class ChallengeMaster:
    """Manages challenge creation and ensures minimum queued challenge counts per reward goal"""
    
    MIN_CHALLENGES_PER_GOAL = 2  # Keep 2 Queued challenges per active reward goal
    CHALLENGES_TO_ADD_IF_BELOW_MIN = 2  # Add 2 more when below minimum per goal
    
    def __init__(self, db):
        self.db = db
        self.task_generator = TaskGenerator(db)
    
    def _acquire_generation_lock(self, username):
        """Acquire generation lock with timeout"""
        lock_key = f"challenge_generation_lock_{username}"
        lock_ref = self.db.collection('generation_locks').document(lock_key)
        lock_doc = lock_ref.get()
        
        if lock_doc.exists:
            lock_data = lock_doc.to_dict()
            # Check if lock is still valid (not expired)
            lock_time = lock_data.get('locked_at')
            if lock_time and hasattr(lock_time, 'timestamp'):
                lock_age = datetime.now() - datetime.fromtimestamp(lock_time.timestamp())
                if lock_age.total_seconds() < 300:  # 5 minute timeout
                    logger.debug(f"Challenge generation already in progress for {username}, skipping")
                    return None
                else:
                    logger.debug(f"Lock expired for {username}, clearing and proceeding")
                    lock_ref.delete()
            else:
                logger.debug(f"Invalid lock data for {username}, clearing and proceeding")
                lock_ref.delete()
        
        # Acquire lock
        lock_ref.set({
            'username': username,
            'locked_at': firestore.SERVER_TIMESTAMP,
            'type': 'challenge_generation'
        })
        
        return lock_ref
    
    def _release_generation_lock(self, lock_ref, username):
        """Release generation lock"""
        if lock_ref:
            try:
                lock_ref.delete()
                logger.debug(f"Released challenge generation lock for {username}")
            except Exception as lock_error:
                logger.error(f"Failed to release lock for {username}: {lock_error}")
    
    def _get_active_reward_goals(self, username):
        """Get active reward goals"""
        goals_query = self.db.collection('reward_goals').where(
            filter=firestore.And([
                FieldFilter('username', '==', username),
                FieldFilter('status', '==', 'pending')
            ])
        )
        goals_docs = list(goals_query.stream())
        goal_ids = {doc.id for doc in goals_docs}
        
        logger.info(f"Found {len(goal_ids)} active reward goals for {username}")
        return goals_docs, goal_ids
    
    def _cleanup_invalid_challenges(self, username, goal_ids):
        """Delete invalid challenges"""
        current_time = datetime.now()
        challenges_query = self.db.collection('reward_tasks').where(
            filter=firestore.And([
                FieldFilter('username', '==', username),
                FieldFilter('status', '==', 'pending')
            ])
        )
        challenges_docs = list(challenges_query.stream())
        
        invalid_challenges = []
        for challenge_doc in challenges_docs:
            challenge_data = challenge_doc.to_dict()
            challenge_goal_id = challenge_data.get('reward_goal_id')
            
            if not challenge_goal_id or challenge_goal_id not in goal_ids:
                logger.debug(f"Removing invalid challenge (goal_id: {challenge_goal_id})")
                invalid_challenges.append(challenge_doc)
        
        # Delete invalid challenges
        for challenge_doc in invalid_challenges:
            try:
                challenge_doc.reference.delete()
                logger.debug(f"Deleted invalid challenge {challenge_doc.id}")
            except Exception as e:
                logger.debug(f"Failed to delete invalid challenge {challenge_doc.id}: {e}")
    
    def _count_queued_challenges_per_goal(self, username, goal_ids):
        """Count unpresented challenges per goal"""
        local_tz = pytz.timezone('US/Central')
        current_time = datetime.now(local_tz)
        challenges_query = self.db.collection('reward_tasks').where(
            filter=firestore.And([
                FieldFilter('username', '==', username),
                FieldFilter('status', '==', 'pending')
            ])
        )
        challenges_docs = list(challenges_query.stream())
        
        challenges_by_goal = {}
        expired_challenges_deleted = 0
        
        for challenge_doc in challenges_docs:
            challenge_data = challenge_doc.to_dict()
            challenge_goal_id = challenge_data.get('reward_goal_id')
            presented_at = challenge_data.get('presented_at')
            
            # Only count UNPRESENTED challenges toward the minimum requirement
            # Presented challenges are already "in use" and don't count toward minimum
            is_unpresented = False
            
            if presented_at is None:
                # Unpresented challenges count toward minimum requirement
                is_unpresented = True
            else:
                # Check if recently presented challenge is expired (> 12 hours old)
                if hasattr(presented_at, 'timestamp'):
                    presented_datetime = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                else:
                    presented_datetime = presented_at
                
                # Delete expired challenge immediately (like TaskMaster)
                if current_time - presented_datetime >= timedelta(hours=12):
                    try:
                        challenge_doc.reference.delete()
                        expired_challenges_deleted += 1
                        logger.debug(f"Cleaned up expired challenge {challenge_doc.id} during count")
                    except Exception as e:
                        logger.debug(f"Failed to delete expired challenge {challenge_doc.id}: {e}")
            
            # Only count unpresented challenges toward minimum requirement
            if is_unpresented and challenge_goal_id and challenge_goal_id in goal_ids:
                if challenge_goal_id not in challenges_by_goal:
                    challenges_by_goal[challenge_goal_id] = []
                challenges_by_goal[challenge_goal_id].append(challenge_doc)
        
        if expired_challenges_deleted > 0:
            logger.debug(f"Cleaned up {expired_challenges_deleted} expired challenges for {username} during count")
        
        return challenges_by_goal
    
    def _identify_goals_needing_challenges(self, username, challenges_by_goal, goal_ids, goals_docs):
        """Find goals needing challenges"""
        goals_needing_challenges = []
        
        for goal_id in goal_ids:
            current_challenge_count = len(challenges_by_goal.get(goal_id, []))
            logger.ensure_minimum_check(username, f"challenges_{goal_id}", current_challenge_count, self.MIN_CHALLENGES_PER_GOAL)
            
            if current_challenge_count < self.MIN_CHALLENGES_PER_GOAL:
                logger.debug(f"Goal {goal_id} needs more challenges (current: {current_challenge_count}, minimum: {self.MIN_CHALLENGES_PER_GOAL})")
                
                # Get goal document for challenge generation
                goal_doc = next((doc for doc in goals_docs if doc.id == goal_id), None)
                if goal_doc:
                    goals_needing_challenges.append(goal_doc)
        
        return goals_needing_challenges
    
    def _generate_challenges_for_goals(self, username, goals_needing_challenges, total_goals_count):
        """Generate challenges for goals needing them"""
        if not goals_needing_challenges:
            logger.debug("All goals already have sufficient challenges")
            return
        
        logger.debug(f"Generating {len(goals_needing_challenges)} new challenges")
        try:
            self.task_generator.user = username  # Set the user for this generation
            
            # Calculate difficulty based on number of reward goals in queue
            # Base difficulty of 3 + number of reward goals + random variation
            base_difficulty = 3 + total_goals_count
            logger.debug(f"Total reward goals in queue: {total_goals_count}, base difficulty: {base_difficulty}")
            
            # Prepare goals data with simple difficulty calculation
            goals_data = []
            for goal_doc in goals_needing_challenges:
                goal_data = goal_doc.to_dict()
                goal_data['id'] = goal_doc.id
                
                # Simple difficulty: base + random(-2, +2), clamped to minimum 1
                difficulty_variation = random.randint(-2, 2)
                selected_difficulty = max(1, base_difficulty + difficulty_variation)
                goal_data['selected_difficulty'] = selected_difficulty
                
                # Add this goal CHALLENGES_TO_ADD_IF_BELOW_MIN times so AI generates multiple challenges per goal
                logger.debug(f"Adding goal {goal_doc.id} {self.CHALLENGES_TO_ADD_IF_BELOW_MIN} times to goals_data")
                for i in range(self.CHALLENGES_TO_ADD_IF_BELOW_MIN):
                    goals_data.append(goal_data.copy())
                    logger.debug(f"  Added copy {i+1} of goal {goal_doc.id}")
                
                logger.debug(f"Goal {goal_doc.id} assigned difficulty {selected_difficulty} (base: {base_difficulty} + {difficulty_variation}) - will generate {self.CHALLENGES_TO_ADD_IF_BELOW_MIN} challenges")
            
            # Generate challenges in batch using AI - one challenge per goal_data entry
            logger.debug(f"Total goals_data entries: {len(goals_data)} (should be {len(goals_needing_challenges)} goals × {self.CHALLENGES_TO_ADD_IF_BELOW_MIN} = {len(goals_needing_challenges) * self.CHALLENGES_TO_ADD_IF_BELOW_MIN})")
            generated_challenges = self.task_generator.generate_reward_tasks_batch_with_weights(goals_data, len(goals_data))
            logger.debug(f"Generated {len(generated_challenges)} challenges from AI")
            
            # Save to database
            saved_count = 0
            for challenge_data in generated_challenges:
                try:
                    # Add database fields - challenges start unpresented (like tasks)
                    db_challenge_data = {
                        'username': username,
                        'reward_goal_id': challenge_data.get('ID'),  # AI returns 'ID', we map it to 'reward_goal_id' for database
                        'base_idea': challenge_data.get('base_idea'),
                        'type': 'reward',
                        'status': 'pending',
                        'description': challenge_data.get('description'),
                        'themes': challenge_data.get('themes', []),
                        'difficulty': challenge_data.get('difficulty', 3),  # Default to 3 if not specified
                        'duration': challenge_data.get('duration', 10),  # Default to 10 minutes if not specified
                        'created_at': firestore.SERVER_TIMESTAMP,
                        'updated_at': firestore.SERVER_TIMESTAMP,
                        'presented_at': None  # Standardized to null for unpresented challenges (like tasks)
                    }
                    
                    # Save to database
                    doc_ref = self.db.collection('reward_tasks').add(db_challenge_data)
                    saved_count += 1
                    logger.debug(f"Saved challenge for goal {challenge_data.get('ID')}: {challenge_data.get('description')[:50]}...")
                    
                except Exception as e:
                    logger.debug(f"Error saving challenge: {e}")
                    continue
            
            logger.debug(f"Successfully saved {saved_count} new challenges")
            
        except Exception as e:
            logger.error(f"Failed to generate challenges for {username}: {e}")
    
    def ensure_minimum_challenges(self, username):
        """Ensure minimum challenges per active reward goal"""
        lock_ref = None
        
        try:
            # Try to acquire lock
            lock_ref = self._acquire_generation_lock(username)
            if lock_ref is None:
                return  # Lock already held
            
            logger.info(f"Ensuring minimum challenges for {username}")
            
            # Get active reward goals
            goals_docs, goal_ids = self._get_active_reward_goals(username)
            
            # Clean up invalid challenges
            self._cleanup_invalid_challenges(username, goal_ids)
            
            # Count queued challenges per goal
            challenges_by_goal = self._count_queued_challenges_per_goal(username, goal_ids)
            
            # Identify goals needing challenges
            goals_needing_challenges = self._identify_goals_needing_challenges(username, challenges_by_goal, goal_ids, goals_docs)
            
            # Generate challenges for goals that need them
            self._generate_challenges_for_goals(username, goals_needing_challenges, len(goals_docs))
            
        except Exception as e:
            logger.error(f"Failed to ensure minimum challenges for {username}: {e}")
        finally:
            # Always release lock
            self._release_generation_lock(lock_ref, username)
    
    def get_active_challenges(self, username, limit=4):
        """Get active challenges (one per goal, max limit)"""
        try:
            # Get active reward goals for this user and sort them randomly
            goals_query = self.db.collection('reward_goals').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('status', '==', 'pending')
                ])
            )
            goals_docs = list(goals_query.stream())
            goal_ids = [doc.id for doc in goals_docs]
            
            # Shuffle goals randomly to provide variety
            random.shuffle(goal_ids)
            logger.debug(f"Found {len(goal_ids)} active reward goals, shuffled randomly")
            
            # Get all pending challenges for this user
            local_tz = pytz.timezone('US/Central')
            current_time = datetime.now(local_tz)
            challenges_query = self.db.collection('reward_tasks').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('status', '==', 'pending')
                ])
            )
            challenges_docs = list(challenges_query.stream())
            logger.debug(f"Found {len(challenges_docs)} pending challenge documents")
            
            # Group challenges by goal_id and filter for active ones
            challenges_by_goal = {}
            active_presented_challenges = []
            
            for doc in challenges_docs:
                challenge_data = doc.to_dict()
                challenge_data['id'] = doc.id
                presented_at = challenge_data.get('presented_at')
                goal_id = challenge_data.get('reward_goal_id')
                
                # Convert timestamps for immediate use
                if 'created_at' in challenge_data and hasattr(challenge_data['created_at'], 'timestamp'):
                    challenge_data['created_at'] = datetime.fromtimestamp(challenge_data['created_at'].timestamp(), tz=local_tz)
                
                if goal_id and goal_id in goal_ids:
                    if presented_at is not None:
                        # Challenge has been presented - check if still active (less than 12 hours old)
                        if hasattr(presented_at, 'timestamp'):
                            presented_datetime = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                        else:
                            presented_datetime = presented_at
                        
                        challenge_data['presented_at'] = presented_datetime
                        
                        # Check if challenge is expired (12 hours old) - DELETE IMMEDIATELY like TaskMaster
                        is_recent = current_time - presented_datetime < timedelta(hours=12)
                        age_hours = (current_time - presented_datetime).total_seconds() / 3600
                        
                        if is_recent:
                            active_presented_challenges.append(challenge_data)
                            logger.debug(f"Active presented challenge for goal {goal_id}: saved=False, age={age_hours:.1f}h")
                        else:
                            logger.debug(f"Deleting expired challenge for goal {goal_id}: age={age_hours:.1f}h")
                            # Delete the expired challenge immediately (like TaskMaster)
                            self.db.collection('reward_tasks').document(challenge_data['id']).delete()
                    else:
                        # Unpresented challenge - always available
                        if goal_id not in challenges_by_goal:
                            challenges_by_goal[goal_id] = []
                        challenges_by_goal[goal_id].append(challenge_data)
                        logger.debug(f"Unpresented challenge for goal {goal_id}: {challenge_data.get('description', 'No description')[:50]}...")
            
            # Select exactly one challenge per goal (up to limit)
            # First, group active presented challenges by goal
            presented_by_goal = {}
            for challenge in active_presented_challenges:
                goal_id = challenge.get('reward_goal_id')
                if goal_id not in presented_by_goal:
                    presented_by_goal[goal_id] = []
                presented_by_goal[goal_id].append(challenge)
            
            selected_challenges = []
            new_challenges = []
            
            for goal_id in goal_ids:
                if len(selected_challenges) >= limit:
                    break
                
                # First, try to use an existing active presented challenge for this goal
                if goal_id in presented_by_goal and presented_by_goal[goal_id]:
                    # Pick a random presented challenge for this goal
                    selected_challenge = random.choice(presented_by_goal[goal_id])
                    selected_challenges.append(selected_challenge)
                    logger.debug(f"Selected existing presented challenge for goal {goal_id}: {selected_challenge.get('description', 'No description')[:50]}...")
                elif goal_id in challenges_by_goal and challenges_by_goal[goal_id]:
                    # No presented challenge for this goal, pick an unpresented one and mark as presented
                    available_challenges = challenges_by_goal[goal_id]
                    selected_challenge = random.choice(available_challenges)
                    
                    # Mark challenge as presented
                    challenge_ref = self.db.collection('reward_tasks').document(selected_challenge['id'])
                    challenge_ref.update({
                        'presented_at': firestore.SERVER_TIMESTAMP
                    })
                    selected_challenge['presented_at'] = datetime.now(local_tz)  # For immediate use
                    
                    selected_challenges.append(selected_challenge)
                    new_challenges.append(selected_challenge)
                    logger.debug(f"Selected and presented challenge for goal {goal_id}: {selected_challenge.get('description', 'No description')[:50]}...")
            
            logger.debug(f"Selected {len(selected_challenges)} challenges ({len(new_challenges)} newly presented) from {len(goal_ids)} goals")
            return selected_challenges
            
        except Exception as e:
            logger.error(f"Error getting active challenges for {username}: {e}")
            return []
    
    def complete_challenge_and_goal(self, username, task_id):
        """Complete challenge and associated reward goal"""
        try:
            # Get the challenge
            challenge_ref = self.db.collection('reward_tasks').document(task_id)
            challenge_doc = challenge_ref.get()
            
            if not challenge_doc.exists:
                logger.error(f"Challenge {task_id} not found")
                return None
            
            challenge_data = challenge_doc.to_dict()
            if challenge_data.get('username') != username:
                logger.error(f"Challenge {task_id} belongs to {challenge_data.get('username')}, not {username}")
                return None
            
            reward_goal_id = challenge_data.get('reward_goal_id')
            if not reward_goal_id:
                logger.error(f"Challenge {task_id} has no associated reward goal")
                return None
            
            # Mark challenge as completed
            challenge_ref.update({
                'status': 'completed',
                'completed_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Mark the reward goal as completed
            goal_ref = self.db.collection('reward_goals').document(reward_goal_id)
            goal_doc = goal_ref.get()
            
            if goal_doc.exists:
                goal_ref.update({
                    'status': 'completed',
                    'completed_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                logger.debug(f"Marked reward goal {reward_goal_id} as completed")
                
                # Delete all remaining pending challenges for this goal
                remaining_challenges_query = self.db.collection('reward_tasks').where(
                    filter=firestore.And([
                        FieldFilter('reward_goal_id', '==', reward_goal_id),
                        FieldFilter('status', '==', 'pending')
                    ])
                )
                remaining_challenges_docs = list(remaining_challenges_query.stream())
                
                deleted_count = 0
                for remaining_challenge_doc in remaining_challenges_docs:
                    try:
                        remaining_challenge_doc.reference.delete()
                        deleted_count += 1
                    except Exception as e:
                        logger.debug(f"Failed to delete remaining challenge {remaining_challenge_doc.id}: {e}")
                
                logger.debug(f"Deleted {deleted_count} remaining challenges for completed goal {reward_goal_id}")
            else:
                logger.debug(f"Reward goal {reward_goal_id} not found")
            
            # Return the completed challenge data
            challenge_data['status'] = 'completed'
            local_tz = pytz.timezone('US/Central')
            challenge_data['completed_at'] = datetime.now(local_tz)
            
            return challenge_data
            
        except Exception as e:
            logger.error(f"Error completing challenge {task_id}: {e}")
            return None
    

