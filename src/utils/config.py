"""
Configuration constants - shared configuration values across the application
"""
import pytz
from datetime import datetime, timezone


# Timezone Configuration
CENTRAL_TIMEZONE = pytz.timezone('America/Chicago')

# Collection Names
COLLECTIONS = {
    'tasks': 'tasks',
    'rewards': 'rewards',
    'goals': 'goals',
    'daily_task_templates': 'daily_task_templates',
    'daily_task_instances': 'daily_task_instances',
    'morning_card_templates': 'morning_card_templates',
    'morning_card_selections': 'morning_card_selections',
    'collaboration_tracker': 'collaboration_tracker',
    'tracker_history': 'tracker_history',
    'generation_locks': 'generation_locks'
}

# Task Management Constants
MIN_TASKS_PER_CATEGORY = 5
ACTIVE_SESSION_TASK_COUNT = 4

# Task Categories
TASK_CATEGORIES = ['Work', 'Kids', 'Spouse', 'House', 'Self']

# Goal Categories
GOAL_CATEGORIES = ['Work', 'Kids', 'Spouse', 'House', 'Self']

# Default Values
DEFAULT_TASK_DIFFICULTY = 3
DEFAULT_TASK_DURATION = 10
DEFAULT_COLLABORATION_TRACKER_VALUE = 5
DEFAULT_DICE_ROLL_CREDIT_CAP = 10

# Rate Limiting
DEFAULT_RATE_LIMITS = {
    'read': "50 per minute",
    'write': "20 per minute",
    'update': "30 per minute",
    'delete': "30 per minute",
    'generate': "10 per minute"
}

# Time Periods
TIME_PERIODS = {
    'morning': (6, 8),      # 6am - 8am
    'workday': (8, 15),    # 8am - 3pm
    'evening': (15, 22),   # 3pm - 10pm
    'weekend': None        # Saturday/Sunday
}

def get_timezone():
    """
    Get the central timezone instance.
    
    Returns:
        pytz timezone object for America/Chicago
    """
    return CENTRAL_TIMEZONE


def get_utc_now():
    """
    Get current datetime in UTC.
    
    Returns:
        datetime object with UTC timezone
    """
    return datetime.now(timezone.utc)


def get_spouse(username: str):
    """
    Get the spouse username for a given user from database.
    
    Args:
        username: User's username
        
    Returns:
        Spouse's username or None if no spouse linked
        
    Note: Returns None for single-user mode (valid state)
    """
    try:
        # Import here to avoid circular dependency
        import os
        from google.cloud import firestore
        from src.utils.logger import logger
        
        # Try to get database instance from flask app context first
        from flask import current_app
        if current_app:
            db = current_app.config.get('DB')
            if db:
                user_ref = db.collection('users').document(username)
                user_doc = user_ref.get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    spouse_username = user_data.get('spouse_username')
                    return spouse_username if spouse_username else None
        
        # Fallback: create Firestore client directly (for scripts and background tasks)
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
        if project_id:
            db = firestore.Client(project=project_id)
            user_ref = db.collection('users').document(username)
            user_doc = user_ref.get()
            
            if user_doc.exists:
                user_data = user_doc.to_dict()
                spouse_username = user_data.get('spouse_username')
                return spouse_username if spouse_username else None
                
    except Exception as e:
        logger.debug(f"Could not fetch spouse from database for {username}: {e}")
    
    # Fallback: return None (single user mode)
    return None


def get_collection(name: str) -> str:
    """
    Get Firestore collection name.
    
    Args:
        name: Collection key
        
    Returns:
        Collection name string
    """
    return COLLECTIONS.get(name, name)

