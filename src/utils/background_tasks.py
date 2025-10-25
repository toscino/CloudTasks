"""
Background task utilities - handles background task generation and management
"""
import threading
from src.utils.logger import logger


def ensure_minimums(task_master, username, check_tasks=True, check_rewards=True, check_challenges=False):
    """Centralized function to ensure minimum counts for tasks, rewards, and challenges"""
    
    
    def ensure_tasks():
        try:
            task_master.ensure_minimum_tasks(username)
        except Exception as e:
            logger.error(f"Background: ensure_minimum_tasks failed for {username}: {e}")
    
    def ensure_rewards():
        try:
            task_master.reward_master.ensure_minimum_reward_options(username)
        except Exception as e:
            logger.error(f"Background: ensure_minimum_reward_options failed for {username}: {e}")
    
    # DISABLED: Challenges system temporarily disabled
    # def ensure_challenges():
    #     try:
    #         logger.debug(f"Background: Running ensure_minimum_challenges for {username}")
    #         task_master.challenge_master.ensure_minimum_challenges(username)
    #         logger.debug(f"Background: ensure_minimum_challenges completed for {username}")
    #     except Exception as e:
    #         logger.error(f"Background: ensure_minimum_challenges failed for {username}: {e}")
    
    # Start separate threads for each check - run in parallel
    if check_tasks:
        threading.Thread(target=ensure_tasks, daemon=True).start()
    if check_rewards:
        threading.Thread(target=ensure_rewards, daemon=True).start()
    # DISABLED: Challenges system temporarily disabled
    # if check_challenges:
    #     logger.debug(f"Starting challenge generation thread for {username}")
    #     threading.Thread(target=ensure_challenges, daemon=True).start()
    
