"""
Statistics service - handles statistics and comparison logic
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, timedelta
from src.utils.background_tasks import ensure_minimums
from src.utils.logger import logger
from src.utils.config import get_timezone
from src.utils.error_handlers import handle_exception
from typing import Dict, Any


class StatisticsService:
    """Service for statistics and comparison operations"""
    
    def __init__(self, db, task_master):
        self.db = db
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
            
            logger.debug(f"Weekly points calculation for {username}")
            logger.debug(f"Week start: {current_week_start}")
            logger.debug(f"Week end: {current_week_end}")
            logger.debug(f"Current time: {now}")
            
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
            
            logger.debug(f"Found {len(tasks_docs)} completed tasks within week for {username}")
            
            total_points = 0
            completed_tasks_count = 0
            
            for doc in tasks_docs:
                task_data = doc.to_dict()
                difficulty = task_data.get('difficulty', 0)
                total_points += difficulty
                completed_tasks_count += 1
            
            logger.debug(f"Total weekly points: {total_points} from {completed_tasks_count} tasks")
            
            return {
                'status': 'success',
                'weekly_points': total_points,
                'completed_tasks': completed_tasks_count,
                'week_start': current_week_start.isoformat(),
                'week_end': current_week_end.isoformat(),
                'showing_last_week': show_last_week
            }
            
        except Exception as e:
            logger.error(f"Failed to get weekly points: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get weekly points: {str(e)}'
            }
    
    def get_reward_comparison(self, username: str, spouse_username: str) -> Dict[str, Any]:
        """Get pending rewards comparison"""
        try:
            # Count pending rewards for both users
            user_rewards_query = self.db.collection('reward_goals').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('status', '==', 'pending')
                ])
            )
            user_rewards_docs = list(user_rewards_query.stream())
            user_rewards_count = len(user_rewards_docs)
            
            spouse_rewards_query = self.db.collection('reward_goals').where(
                filter=firestore.And([
                    FieldFilter('username', '==', spouse_username),
                    FieldFilter('status', '==', 'pending')
                ])
            )
            spouse_rewards_docs = list(spouse_rewards_query.stream())
            spouse_rewards_count = len(spouse_rewards_docs)
            
            logger.debug(f"Reward comparison - {username}: {user_rewards_count}, {spouse_username}: {spouse_rewards_count}")
            
            return {
                'status': 'success',
                'user_rewards': user_rewards_count,
                'spouse_rewards': spouse_rewards_count,
                'user_name': username,
                'spouse_name': spouse_username
            }
            
        except Exception as e:
            logger.error(f"Failed to get reward comparison: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get reward comparison: {str(e)}'
            }
    
    def get_challenges(self, username: str) -> Dict[str, Any]:
        """Get active challenges (one per goal)"""
        try:
            logger.debug(f"Fetching challenges for user: {username}")
            
            # Import ChallengeMaster
            from src.core.challenge_master import ChallengeMaster
            challenge_master = ChallengeMaster(self.db)
            
            # Get existing active challenges (fast - no AI calls)
            challenges = challenge_master.get_active_challenges(username, limit=4)
            
            logger.debug(f"Active challenges for {username}: {len(challenges)}")
            
            # Fire off background task generation (non-blocking)
            ensure_minimums(self.task_master, username, check_tasks=False, check_rewards=False, check_challenges=True)
            
            return {
                'status': 'success',
                'challenges': challenges
            }
            
        except Exception as e:
            logger.error(f"Failed to get challenges for {username}: {str(e)}")
            return {
                'status': 'error',
                'message': f'Failed to get challenges: {str(e)}'
            }
    
    def complete_challenge(self, task_id: str, username: str) -> Dict[str, Any]:
        """Complete challenge and reward goal"""
        try:
            # Import ChallengeMaster
            from src.core.challenge_master import ChallengeMaster
            challenge_master = ChallengeMaster(self.db)
            
            # Complete the challenge and associated goal
            completed_task = challenge_master.complete_challenge_and_goal(username, task_id)
            
            if not completed_task:
                return {
                    'status': 'error',
                    'message': 'Challenge not found or unauthorized'
                }
            
            return {
                'status': 'success',
                'message': 'Challenge completed successfully'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to complete challenge: {str(e)}'
            }
