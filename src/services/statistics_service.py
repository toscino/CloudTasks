"""
Statistics service - handles statistics and comparison logic
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, timedelta
from src.utils.config import get_timezone
from src.utils.error_handlers import handle_exception
from typing import Dict, Any


class StatisticsService:
    """Service for statistics and comparison operations"""
    
    def __init__(self, app_manager, task_master):
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.task_master = task_master
    
    def get_weekly_points(self, username: str) -> Dict[str, Any]:
        """Get weekly difficulty points"""
        try:
            # Calculate Friday 5pm to Friday 5pm week boundaries
            # Get current time in local timezone (Central - Iowa/Chicago)
            local_tz = get_timezone()
            now = datetime.now(local_tz)
            
            # Determine if we should show last week's score (Friday 5pm through Sunday)
            show_last_week = False
            if now.weekday() == 4 and now.hour >= 17:  # Friday 5pm or later
                show_last_week = True
            elif now.weekday() == 5:  # Saturday
                show_last_week = True
            elif now.weekday() == 6:  # Sunday
                show_last_week = True
            
            # Find the current week boundaries (Friday 5pm to Friday 5pm)
            # If it's Friday and before 5pm, we're still in the previous week
            # If it's Friday and after 5pm, or Saturday/Sunday, we're in the new week
            
            if now.weekday() == 4 and now.hour < 17:  # Friday before 5pm
                # We're still in the previous week, so current week ends at next Friday 5pm
                days_until_next_friday = 0  # Today is Friday
                current_week_end = now + timedelta(days=days_until_next_friday)
                current_week_end = current_week_end.replace(hour=17, minute=0, second=0, microsecond=0)
            else:
                # We're past Friday 5pm, so find the next Friday 5pm
                days_until_friday = (4 - now.weekday()) % 7  # Days until Friday (0-6)
                if days_until_friday == 0:  # Today is Friday
                    days_until_friday = 7  # Next Friday
                current_week_end = now + timedelta(days=days_until_friday)
                current_week_end = current_week_end.replace(hour=17, minute=0, second=0, microsecond=0)
            
            # Week start is 7 days before week end
            current_week_start = current_week_end - timedelta(days=7)
            
            # If showing last week's score, adjust the week boundaries
            if show_last_week:
                # Show the previous week's score
                current_week_start = current_week_start - timedelta(days=7)
                current_week_end = current_week_end - timedelta(days=7)
            
            self.logger.debug(f"Weekly points calculation for {username}")
            self.logger.debug(f"Week start: {current_week_start}")
            self.logger.debug(f"Week end: {current_week_end}")
            self.logger.debug(f"Current time: {now}")
            
            # COMPOSITE INDEX REQUIRED: tasks(username, completed, completed_at)
            # Optimized query: filter by username, completed=true, and completed_at within week range
            tasks_query = self.db.collection('tasks').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('completed', '==', True),
                    FieldFilter('completed_at', '>=', current_week_start),
                    FieldFilter('completed_at', '<', current_week_end)
                ])
            )
            tasks_docs = list(tasks_query.stream())
            
            self.logger.debug(f"Found {len(tasks_docs)} completed tasks within week for {username}")
            
            total_points = 0
            completed_tasks_count = 0
            
            for doc in tasks_docs:
                task_data = doc.to_dict()
                difficulty = task_data.get('difficulty', 0)
                total_points += difficulty
                completed_tasks_count += 1
            
            self.logger.debug(f"Total weekly points: {total_points} from {completed_tasks_count} tasks")
            
            return {
                'status': 'success',
                'weekly_points': total_points,
                'completed_tasks': completed_tasks_count,
                'week_start': current_week_start.isoformat(),
                'week_end': current_week_end.isoformat(),
                'showing_last_week': show_last_week
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get weekly points: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get weekly points: {str(e)}'
            }
