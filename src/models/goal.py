"""
Goal data models and schemas
"""
from datetime import datetime
from google.cloud import firestore
from typing import Optional, Dict, Any


class GoalModel:
    """Goal data model with validation and serialization"""
    
    def __init__(self, username: str, description: str, category: str = 'General', 
                 priority: str = 'Medium', status: str = 'Active', goal_id: Optional[str] = None):
        self.username = username
        self.description = description
        self.category = category
        self.priority = priority
        self.status = status
        self.goal_id = goal_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dictionary"""
        return {
            'username': self.username,
            'description': self.description,
            'category': self.category,
            'priority': self.priority,
            'status': self.status,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
    
    @classmethod
    def from_firestore_dict(cls, data: Dict[str, Any], goal_id: str) -> 'GoalModel':
        """Create GoalModel from Firestore document data"""
        goal = cls(
            username=data['username'],
            description=data['description'],
            category=data.get('category', 'General'),
            priority=data.get('priority', 'Medium'),
            status=data.get('status', 'Active'),
            goal_id=goal_id
        )
        
        # Handle timestamps
        if 'created_at' in data and data['created_at']:
            if hasattr(data['created_at'], 'timestamp'):
                goal.created_at = datetime.fromtimestamp(data['created_at'].timestamp())
            else:
                goal.created_at = data['created_at']
        
        if 'updated_at' in data and data['updated_at']:
            if hasattr(data['updated_at'], 'timestamp'):
                goal.updated_at = datetime.fromtimestamp(data['updated_at'].timestamp())
            else:
                goal.updated_at = data['updated_at']
        
        return goal
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.goal_id,
            'username': self.username,
            'description': self.description,
            'category': self.category,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def validate(self) -> bool:
        """Validate goal data"""
        if not self.username or not self.description:
            return False
        if self.priority not in ['Low', 'Medium', 'High']:
            return False
        if self.status not in ['Active', 'Completed', 'Paused']:
            return False
        return True


class RewardGoalModel:
    """Reward goal data model (for spouse-selected rewards)"""
    
    def __init__(self, username: str, description: str, earned_by: str, 
                 reward_themes: list = None, status: str = 'pending', reward_goal_id: Optional[str] = None):
        self.username = username
        self.description = description
        self.earned_by = earned_by
        self.reward_themes = reward_themes or []
        self.status = status
        self.reward_goal_id = reward_goal_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.completed_at = None
    
    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dictionary"""
        return {
            'username': self.username,
            'description': self.description,
            'earned_by': self.earned_by,
            'reward_themes': self.reward_themes,
            'status': self.status,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
    
    @classmethod
    def from_firestore_dict(cls, data: Dict[str, Any], reward_goal_id: str) -> 'RewardGoalModel':
        """Create RewardGoalModel from Firestore document data"""
        reward_goal = cls(
            username=data['username'],
            description=data['description'],
            earned_by=data['earned_by'],
            reward_themes=data.get('reward_themes', []),
            status=data.get('status', 'pending'),
            reward_goal_id=reward_goal_id
        )
        
        # Handle timestamps
        if 'created_at' in data and data['created_at']:
            if hasattr(data['created_at'], 'timestamp'):
                reward_goal.created_at = datetime.fromtimestamp(data['created_at'].timestamp())
            else:
                reward_goal.created_at = data['created_at']
        
        if 'updated_at' in data and data['updated_at']:
            if hasattr(data['updated_at'], 'timestamp'):
                reward_goal.updated_at = datetime.fromtimestamp(data['updated_at'].timestamp())
            else:
                reward_goal.updated_at = data['updated_at']
        
        if 'completed_at' in data and data['completed_at']:
            if hasattr(data['completed_at'], 'timestamp'):
                reward_goal.completed_at = datetime.fromtimestamp(data['completed_at'].timestamp())
            else:
                reward_goal.completed_at = data['completed_at']
        
        return reward_goal
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.reward_goal_id,
            'username': self.username,
            'description': self.description,
            'earned_by': self.earned_by,
            'reward_themes': self.reward_themes,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'completed_at': self.completed_at
        }
    
    def validate(self) -> bool:
        """Validate reward goal data"""
        if not self.username or not self.description or not self.earned_by:
            return False
        if self.status not in ['pending', 'completed']:
            return False
        return True


def create_goal_from_request_data(data: Dict[str, Any], username: str) -> GoalModel:
    """Create GoalModel from API request data"""
    return GoalModel(
        username=username,
        description=data['description'],
        category=data.get('category', 'General'),
        priority=data.get('priority', 'Medium'),
        status=data.get('status', 'Active')
    )


def create_reward_goal_from_option(username: str, description: str, earned_by: str, themes: list) -> RewardGoalModel:
    """Create RewardGoalModel from selected reward option"""
    return RewardGoalModel(
        username=username,
        description=description,
        earned_by=earned_by,
        reward_themes=themes,
        status='pending'
    )
