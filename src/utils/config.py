"""
Configuration constants - shared configuration values across the application
"""
import pytz


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

# User Configuration
# Map usernames to their spouse usernames
SPOUSE_MAPPING = {
    'Ian': 'Karleigh',
    'Karleigh': 'Ian',
    'user3': 'test_user',
    'test_user': 'user3'
}

# Default Values
DEFAULT_TASK_DIFFICULTY = 3
DEFAULT_TASK_DURATION = 10
DEFAULT_COLLABORATION_TRACKER_VALUE = 5

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


def get_spouse(username: str) -> str:
    """
    Get the spouse username for a given user.
    
    Args:
        username: User's username
        
    Returns:
        Spouse's username or 'test_user' if not found
    """
    return SPOUSE_MAPPING.get(username, 'test_user')


def get_collection(name: str) -> str:
    """
    Get Firestore collection name.
    
    Args:
        name: Collection key
        
    Returns:
        Collection name string
    """
    return COLLECTIONS.get(name, name)

