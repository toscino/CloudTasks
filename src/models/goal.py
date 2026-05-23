"""
Goal data models and schemas
"""
from datetime import datetime
from google.cloud import firestore
from typing import Optional, Dict, Any


class GoalModel:
    """Goal data model with validation and serialization"""
    
    def __init__(self, username: str, description: str, category: str = 'General', 
                 priority: str = 'Medium', status: str = 'Active', goal_id: Optional[str] = None,
                 delete_on_complete: bool = False):
        self.username = username
        self.description = description
        self.category = category
        self.priority = priority
        self.status = status
        self.goal_id = goal_id
        self.delete_on_complete = delete_on_complete
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
            'delete_on_complete': self.delete_on_complete,
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
            goal_id=goal_id,
            delete_on_complete=data.get('delete_on_complete', False)
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
            'delete_on_complete': self.delete_on_complete,
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


def create_goal_from_request_data(data: Dict[str, Any], username: str) -> GoalModel:
    """Create GoalModel from API request data"""
    return GoalModel(
        username=username,
        description=data['description'],
        category=data.get('category', 'General'),
        priority=data.get('priority', 'Medium'),
        status=data.get('status', 'Active'),
        delete_on_complete=data.get('delete_on_complete', False)
    )
