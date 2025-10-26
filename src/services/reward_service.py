"""
Reward service - handles reward-related business logic
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime
from src.models.reward import RewardModel, EarnedRewardModel, create_reward_from_request_data, create_earned_reward_from_task
from src.utils.background_tasks import ensure_minimums
from src.utils.firestore_helpers import prepare_firestore_document
from src.utils.exceptions import ValidationError, NotFoundError, UnauthorizedError, FirestoreError
from src.utils.error_handlers import handle_exception
from typing import List, Dict, Any


class RewardService:
    """Service for reward-related operations"""
    
    def __init__(self, db, task_master):
        self.db = db
        self.task_master = task_master
    
    def get_rewards(self, username: str) -> Dict[str, Any]:
        """Get rewards (max 4)"""
        try:
            # Simple query for testing purposes only
            rewards_query = self.db.collection('rewards').where('username', '==', username)
            rewards_docs = rewards_query.stream()
            
            rewards = []
            for doc in rewards_docs:
                reward_data = prepare_firestore_document(doc)
                
                # Only include incomplete rewards (client-side filtering)
                if not reward_data.get('completed', False):
                    rewards.append(reward_data)
            
            # Sort by saved status first (saved rewards first), then by created_at
            rewards.sort(key=lambda x: (not x.get('saved', False), x.get('created_at', '')), reverse=False)
            
            # Take only first 4 rewards
            rewards = rewards[:4]
            
            return {
                'status': 'success',
                'rewards': rewards
            }
        except Exception as e:
            return handle_exception(e, "Failed to get rewards")
    
    def create_reward(self, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Create reward"""
        try:
            if not data or not data.get('description'):
                return {'error': 'Reward description is required'}
            
            # Create reward model
            reward_model = create_reward_from_request_data(data, username)
            
            if not reward_model.validate():
                return {'error': 'Invalid reward data'}
            
            # Create new reward in Firestore
            doc_ref = self.db.collection('rewards').add(reward_model.to_firestore_dict())
            
            return {
                'status': 'success',
                'message': 'Reward created successfully',
                'reward_id': doc_ref[1].id
            }
        except Exception as e:
            return handle_exception(e, "Failed to create reward")
    
    def complete_reward(self, reward_id: str, username: str) -> Dict[str, Any]:
        """Complete reward"""
        try:
            # Verify the reward belongs to this user
            doc_ref = self.db.collection('rewards').document(reward_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Reward not found'
                }
            
            reward_data = doc.to_dict()
            if reward_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Reward belongs to another user'
                }
            
            doc_ref.update({
                'completed': True,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            return {
                'status': 'success',
                'message': 'Reward completed successfully'
            }
        except Exception as e:
            return handle_exception(e, "Failed to complete reward")
    
    def save_reward(self, reward_id: str, username: str) -> Dict[str, Any]:
        """Toggle save status"""
        try:
            doc_ref = self.db.collection('rewards').document(reward_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Reward not found'
                }
            
            reward_data = doc.to_dict()
            if reward_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Reward belongs to another user'
                }
            
            current_saved = reward_data.get('saved', False)
            doc_ref.update({
                'saved': not current_saved,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            return {
                'status': 'success',
                'message': f'Reward {"saved" if not current_saved else "unsaved"} successfully'
            }
        except Exception as e:
            return handle_exception(e, "Failed to update reward")
    
    def get_pending_rewards(self, username: str) -> Dict[str, Any]:
        """Get pending earned rewards"""
        try:
            # Query pending earned rewards for this user
            rewards_query = self.db.collection('earned_rewards').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('status', '==', 'pending')
                ])
            )
            rewards_docs = rewards_query.stream()
            
            pending_rewards = []
            for doc in rewards_docs:
                reward_data = doc.to_dict()
                reward_data['id'] = doc.id
                
                # Convert timestamps
                if 'earned_at' in reward_data and hasattr(reward_data['earned_at'], 'timestamp'):
                    reward_data['earned_at'] = datetime.fromtimestamp(reward_data['earned_at'].timestamp())
                
                pending_rewards.append(reward_data)
            
            # Fire off background reward generation (non-blocking)
            ensure_minimums(self.task_master, username, check_tasks=False, check_rewards=True, check_challenges=False)
            
            return {
                'status': 'success',
                'pending_rewards': pending_rewards
            }
        except Exception as e:
            return handle_exception(e, "Failed to get pending rewards")
    
    def generate_reward_options(self, reward_id: str, username: str) -> Dict[str, Any]:
        """Generate reward options for earned reward"""
        try:
            # Verify the earned reward belongs to this user
            doc_ref = self.db.collection('earned_rewards').document(reward_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Earned reward not found'
                }
            
            reward_data = doc.to_dict()
            if reward_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Earned reward belongs to another user'
                }
            
            if reward_data.get('status') != 'pending':
                return {
                    'status': 'error',
                    'message': 'Reward has already been processed'
                }
            
            # Generate reward options
            reward_options = self.task_master.reward_master.get_available_reward_options(username, reward_id)
            
            return {
                'status': 'success',
                'message': 'Reward options generated successfully',
                'reward_options': reward_options,
                'earned_reward_id': reward_id
            }
        except Exception as e:
            return handle_exception(e, "Failed to generate reward options")
    
    def select_reward_option(self, reward_id: str, option_id: str, username: str) -> Dict[str, Any]:
        """Select reward option and create reward goal"""
        try:
            # Verify the earned reward belongs to this user
            earned_doc_ref = self.db.collection('earned_rewards').document(reward_id)
            earned_doc = earned_doc_ref.get()
            
            if not earned_doc.exists:
                return {
                    'status': 'error',
                    'message': 'Earned reward not found'
                }
            
            earned_reward_data = earned_doc.to_dict()
            if earned_reward_data.get('username') != username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Earned reward belongs to another user'
                }
            
            if earned_reward_data.get('status') != 'pending':
                return {
                    'status': 'error',
                    'message': 'Reward has already been processed'
                }
            
            # Select the reward option (this will delete the earned reward)
            selected_option = self.task_master.reward_master.select_reward_option(username, reward_id, option_id)
            
            if selected_option:
                return {
                    'status': 'success',
                    'message': 'Reward option selected successfully',
                    'selected_option': selected_option
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Failed to select reward option'
                }
                
        except Exception as e:
            return handle_exception(e, "Failed to select reward option")
