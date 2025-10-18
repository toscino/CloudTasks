"""
Reward data models and schemas
"""
from datetime import datetime
from google.cloud import firestore
from typing import Optional, Dict, Any, List


class RewardModel:
    """Reward data model with validation and serialization"""
    
    def __init__(self, username: str, description: str, completed: bool = False, 
                 saved: bool = False, reward_id: Optional[str] = None):
        self.username = username
        self.description = description
        self.completed = completed
        self.saved = saved
        self.reward_id = reward_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dictionary"""
        return {
            'username': self.username,
            'description': self.description,
            'completed': self.completed,
            'saved': self.saved,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
    
    @classmethod
    def from_firestore_dict(cls, data: Dict[str, Any], reward_id: str) -> 'RewardModel':
        """Create RewardModel from Firestore document data"""
        reward = cls(
            username=data['username'],
            description=data['description'],
            completed=data.get('completed', False),
            saved=data.get('saved', False),
            reward_id=reward_id
        )
        
        # Handle timestamps
        if 'created_at' in data and data['created_at']:
            if hasattr(data['created_at'], 'timestamp'):
                reward.created_at = datetime.fromtimestamp(data['created_at'].timestamp())
            else:
                reward.created_at = data['created_at']
        
        if 'updated_at' in data and data['updated_at']:
            if hasattr(data['updated_at'], 'timestamp'):
                reward.updated_at = datetime.fromtimestamp(data['updated_at'].timestamp())
            else:
                reward.updated_at = data['updated_at']
        
        return reward
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.reward_id,
            'username': self.username,
            'description': self.description,
            'completed': self.completed,
            'saved': self.saved,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def validate(self) -> bool:
        """Validate reward data"""
        if not self.username or not self.description:
            return False
        return True


class EarnedRewardModel:
    """Earned reward data model"""
    
    def __init__(self, username: str, task_id: str, task_difficulty: int, 
                 status: str = 'pending', earned_reward_id: Optional[str] = None):
        self.username = username
        self.task_id = task_id
        self.task_difficulty = task_difficulty
        self.status = status
        self.earned_reward_id = earned_reward_id
        self.earned_at = datetime.now()
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.selected_option = None
    
    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dictionary"""
        return {
            'username': self.username,
            'earned_at': firestore.SERVER_TIMESTAMP,
            'task_id': self.task_id,
            'task_difficulty': self.task_difficulty,
            'status': self.status,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
    
    @classmethod
    def from_firestore_dict(cls, data: Dict[str, Any], earned_reward_id: str) -> 'EarnedRewardModel':
        """Create EarnedRewardModel from Firestore document data"""
        earned_reward = cls(
            username=data['username'],
            task_id=data['task_id'],
            task_difficulty=data['task_difficulty'],
            status=data.get('status', 'pending'),
            earned_reward_id=earned_reward_id
        )
        
        # Handle timestamps
        if 'earned_at' in data and data['earned_at']:
            if hasattr(data['earned_at'], 'timestamp'):
                earned_reward.earned_at = datetime.fromtimestamp(data['earned_at'].timestamp())
            else:
                earned_reward.earned_at = data['earned_at']
        
        if 'created_at' in data and data['created_at']:
            if hasattr(data['created_at'], 'timestamp'):
                earned_reward.created_at = datetime.fromtimestamp(data['created_at'].timestamp())
            else:
                earned_reward.created_at = data['created_at']
        
        if 'updated_at' in data and data['updated_at']:
            if hasattr(data['updated_at'], 'timestamp'):
                earned_reward.updated_at = datetime.fromtimestamp(data['updated_at'].timestamp())
            else:
                earned_reward.updated_at = data['updated_at']
        
        if 'selected_option' in data:
            earned_reward.selected_option = data['selected_option']
        
        return earned_reward
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.earned_reward_id,
            'username': self.username,
            'task_id': self.task_id,
            'task_difficulty': self.task_difficulty,
            'status': self.status,
            'earned_at': self.earned_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'selected_option': self.selected_option
        }
    
    def validate(self) -> bool:
        """Validate earned reward data"""
        if not self.username or not self.task_id:
            return False
        if self.task_difficulty < 1 or self.task_difficulty > 10:
            return False
        if self.status not in ['pending', 'selected', 'expired']:
            return False
        return True


def create_reward_from_request_data(data: Dict[str, Any], username: str) -> RewardModel:
    """Create RewardModel from API request data"""
    return RewardModel(
        username=username,
        description=data['description'],
        completed=False,
        saved=False
    )


def create_earned_reward_from_task(username: str, task_id: str, difficulty: int) -> EarnedRewardModel:
    """Create EarnedRewardModel from completed task"""
    return EarnedRewardModel(
        username=username,
        task_id=task_id,
        task_difficulty=difficulty,
        status='pending'
    )
