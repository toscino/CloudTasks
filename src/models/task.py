"""
Task data models and schemas
"""
from datetime import datetime
from google.cloud import firestore
from typing import Optional, Dict, Any


class TaskModel:
    """Task data model with validation and serialization"""
    
    def __init__(self, username: str, description: str, category: str = 'General', 
                 difficulty: int = 3, duration: int = 10, completed: bool = False, 
                 saved: bool = False, task_id: Optional[str] = None):
        self.username = username
        self.description = description
        self.category = category
        self.difficulty = difficulty
        self.duration = duration
        self.completed = completed
        self.saved = saved
        self.task_id = task_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.presented_at = None
        self.completed_at = None
    
    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dictionary"""
        return {
            'username': self.username,
            'description': self.description,
            'category': self.category,
            'difficulty': self.difficulty,
            'duration': self.duration,
            'completed': self.completed,
            'saved': self.saved,
            'presented_at': None,  # Standardized to null for unpresented tasks
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
    
    @classmethod
    def from_firestore_dict(cls, data: Dict[str, Any], task_id: str) -> 'TaskModel':
        """Create TaskModel from Firestore document data"""
        task = cls(
            username=data['username'],
            description=data['description'],
            category=data.get('category', 'General'),
            difficulty=data.get('difficulty', 3),
            duration=data.get('duration', 10),
            completed=data.get('completed', False),
            saved=data.get('saved', False),
            task_id=task_id
        )
        
        # Handle timestamps
        if 'created_at' in data and data['created_at']:
            if hasattr(data['created_at'], 'timestamp'):
                task.created_at = datetime.fromtimestamp(data['created_at'].timestamp())
            else:
                task.created_at = data['created_at']
        
        if 'updated_at' in data and data['updated_at']:
            if hasattr(data['updated_at'], 'timestamp'):
                task.updated_at = datetime.fromtimestamp(data['updated_at'].timestamp())
            else:
                task.updated_at = data['updated_at']
        
        if 'presented_at' in data and data['presented_at']:
            if hasattr(data['presented_at'], 'timestamp'):
                task.presented_at = datetime.fromtimestamp(data['presented_at'].timestamp())
            else:
                task.presented_at = data['presented_at']
        
        if 'completed_at' in data and data['completed_at']:
            if hasattr(data['completed_at'], 'timestamp'):
                task.completed_at = datetime.fromtimestamp(data['completed_at'].timestamp())
            else:
                task.completed_at = data['completed_at']
        
        return task
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.task_id,
            'username': self.username,
            'description': self.description,
            'category': self.category,
            'difficulty': self.difficulty,
            'duration': self.duration,
            'completed': self.completed,
            'saved': self.saved,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'presented_at': self.presented_at,
            'completed_at': self.completed_at
        }
    
    def validate(self) -> bool:
        """Validate task data"""
        if not self.username or not self.description:
            return False
        if self.difficulty < 1 or self.difficulty > 10:
            return False
        if self.duration < 1:
            return False
        return True


def create_task_from_request_data(data: Dict[str, Any], username: str) -> TaskModel:
    """Create TaskModel from API request data"""
    return TaskModel(
        username=username,
        description=data['description'],
        category=data.get('category', 'General'),
        difficulty=data.get('difficulty', 3),
        duration=data.get('duration', 10),
        completed=False,
        saved=False
    )
