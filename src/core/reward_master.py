"""
RewardMaster - Manages reward options and ensures minimum reward option counts
"""
import random
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, timedelta
from .reward_generator import RewardGenerator
from src.utils.logger import logger


class RewardMaster:
    """Manages reward options and ensures minimum reward option counts"""
    
    MIN_REWARD_OPTIONS = 10  # Keep 10 reward options in database
    REWARD_OPTIONS_TO_ADD_IF_BELOW_MIN = 10  # Add 10 more when below minimum
    
    def __init__(self, db):
        self.db = db
        self.reward_generator = RewardGenerator(db)
    
    def ensure_minimum_reward_options(self, username):
        """Ensure user has at least MIN_REWARD_OPTIONS reward options available"""
        # Use database-based locking for App Engine compatibility
        lock_key = f"reward_generation_lock_{username}"
        lock_ref = None
        
        try:
            # Try to acquire lock
            lock_ref = self.db.collection('generation_locks').document(lock_key)
            lock_doc = lock_ref.get()
            
            if lock_doc.exists:
                lock_data = lock_doc.to_dict()
                # Check if lock is still valid (not expired)
                lock_time = lock_data.get('locked_at')
                if lock_time and hasattr(lock_time, 'timestamp'):
                    lock_age = datetime.now() - datetime.fromtimestamp(lock_time.timestamp())
                    if lock_age.total_seconds() < 300:  # 5 minute timeout
                        logger.debug(f"Reward generation already in progress for {username}, skipping")
                        return
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
                'type': 'reward_generation'
            })
            
            logger.debug(f"Ensuring minimum reward options for {username}")
            
            count = self._count_reward_options(username)
            logger.ensure_minimum_check(username, "reward_options", count, self.MIN_REWARD_OPTIONS)
            
            if count < self.MIN_REWARD_OPTIONS:
                logger.debug(f"Generating {self.REWARD_OPTIONS_TO_ADD_IF_BELOW_MIN} reward options for {username}")
                try:
                    result = self.reward_generator.generate_reward_options_for_user(
                        username, 
                        count=self.REWARD_OPTIONS_TO_ADD_IF_BELOW_MIN, 
                        upload_to_firestore=True
                    )
                    generated_count = len(result) if result else 0
                    logger.ensure_minimum_check(username, "reward_options", count, self.MIN_REWARD_OPTIONS, generated_count)
                    # Verify the options were actually saved to database
                    if result:
                        verify_count = self._count_reward_options(username)
                        logger.debug(f"After generation, database shows {verify_count} unused options for {username}")
                except Exception as e:
                    logger.error(f"Failed to generate reward options for {username}: {e}")
                    # Don't re-raise the exception, just log it and continue to release the lock
            
            # Release lock (this will always execute)
            if lock_ref:
                lock_ref.delete()
                logger.debug(f"Released reward generation lock for {username}")
            
        except Exception as e:
            logger.error(f"Failed to ensure minimum reward options for {username}: {e}")
            # Try to release lock on error
            if lock_ref:
                try:
                    lock_ref.delete()
                    logger.debug(f"Released lock after error for {username}")
                except Exception as lock_error:
                    logger.error(f"Failed to release lock for {username}: {lock_error}")
    
    def _count_reward_options(self, username):
        """Count unused reward options for a user"""
        try:
            options_query = self.db.collection('reward_options').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('used', '==', False)
                ])
            )
            options_docs = options_query.stream()
            return len(list(options_docs))
        except Exception as e:
            logger.error(f"Error counting unused reward options for {username}: {e}")
            return 0
    
    def get_available_reward_options(self, username, earned_reward_id):
        """Get 4 reward options for a specific earned reward (mark as used when offered)"""
        try:
            # Get available reward options that haven't been used yet
            options_query = self.db.collection('reward_options').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('used', '==', False)
                ])
            )
            options_docs = list(options_query.stream())

            if len(options_docs) < 4:
                logger.warning(f"Only {len(options_docs)} options available, returning what we have")
                selected_options = options_docs
            else:
                # Randomly select 4 options
                selected_options = random.sample(options_docs, 4)
            
            # Convert to our format and mark as used
            reward_options = []
            for i, doc in enumerate(selected_options):
                option_data = doc.to_dict()
                option_data['id'] = doc.id
                option_data = self._sanitize_reward_data(option_data)
                reward_options.append(option_data)
                
                # Mark this option as used (offered to this earned reward)
                doc.reference.update({
                    'used': True,
                    'used_for_reward': earned_reward_id,
                    'used_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            logger.debug(f"Offered {len(reward_options)} options for earned reward {earned_reward_id} (marked as used)")
            return reward_options
            
        except Exception as e:
            logger.error(f"Error getting reward options for earned reward {earned_reward_id}: {e}")
            return []
    
    def select_reward_option(self, username, earned_reward_id, selected_option_id):
        """Select a reward option, create base reward idea, and delete the earned reward"""
        try:
            # Get the reward option
            doc_ref = self.db.collection('reward_options').document(selected_option_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Reward option {selected_option_id} not found")
                return None
            
            option_data = doc.to_dict()
            if option_data.get('username') != username:
                logger.error(f"Reward option {selected_option_id} belongs to {option_data.get('username')}, not {username}")
                return None
            
            # Mark as selected
            doc_ref.update({
                'selected': True,
                'selected_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Create spouse reward goal from selected reward
            from src.auth.auth_service import get_spouse_username
            spouse_username = get_spouse_username(username)
            reward_goal_data = {
                'username': spouse_username,
                'description': option_data['description'],
                'earned_by': username,  # Track who earned the original reward
                'reward_themes': option_data['themes'],  # Keep reward themes for context
                'status': 'pending',  # pending, completed
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            reward_goal_ref = self.db.collection('reward_goals').add(reward_goal_data)
            reward_goal_id = reward_goal_ref[1].id
            logger.debug(f"Created spouse reward goal {reward_goal_id}: {option_data['description']}")
            
            # Delete the earned reward document
            earned_reward_ref = self.db.collection('earned_rewards').document(earned_reward_id)
            earned_reward_ref.delete()
            
            # Return the option data with reward goal information
            option_data['id'] = doc.id
            option_data['selected_at'] = datetime.now()
            option_data['reward_goal_id'] = reward_goal_id
            logger.reward_selection(username, earned_reward_id, option_data['description'])
            return self._sanitize_reward_data(option_data)
            
        except Exception as e:
            logger.error(f"Error selecting reward option {selected_option_id} for earned reward {earned_reward_id}: {e}")
            return None
    
    
    def _sanitize_reward_data(self, reward_data):
        """Convert Firestore timestamps to datetime objects for JSON serialization"""
        timestamp_fields = ['created_at', 'updated_at', 'selected_at']
        current_time = datetime.now()
        
        for field in timestamp_fields:
            if field in reward_data:
                value = reward_data[field]
                # Convert Firestore timestamp to datetime if needed
                if hasattr(value, 'timestamp'):
                    reward_data[field] = datetime.fromtimestamp(value.timestamp())
                elif value is None:
                    reward_data[field] = current_time
        
        return reward_data
