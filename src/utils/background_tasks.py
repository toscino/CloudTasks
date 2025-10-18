"""
Background task utilities - handles background task generation and management
"""
import threading
from src.utils.logger import logger


def ensure_minimums(task_master, username, check_tasks=True, check_rewards=True, check_challenges=True):
    """Centralized function to ensure minimum counts for tasks, rewards, and challenges"""
    
    logger.debug(f"ensure_minimums called for {username} - tasks:{check_tasks}, rewards:{check_rewards}, challenges:{check_challenges}")
    
    def ensure_tasks():
        try:
            logger.debug(f"Background: Running ensure_minimum_tasks for {username}")
            task_master.ensure_minimum_tasks(username)
            logger.debug(f"Background: ensure_minimum_tasks completed for {username}")
        except Exception as e:
            logger.error(f"Background: ensure_minimum_tasks failed for {username}: {e}")
    
    def ensure_rewards():
        try:
            logger.debug(f"Background: Running ensure_minimum_reward_options for {username}")
            task_master.reward_master.ensure_minimum_reward_options(username)
            logger.debug(f"Background: ensure_minimum_reward_options completed for {username}")
        except Exception as e:
            logger.error(f"Background: ensure_minimum_reward_options failed for {username}: {e}")
    
    def ensure_challenges():
        try:
            logger.debug(f"Background: Running ensure_minimum_challenges for {username}")
            task_master.challenge_master.ensure_minimum_challenges(username)
            logger.debug(f"Background: ensure_minimum_challenges completed for {username}")
        except Exception as e:
            logger.error(f"Background: ensure_minimum_challenges failed for {username}: {e}")
    
    # Start separate threads for each check - run in parallel
    if check_tasks:
        logger.debug(f"Starting task generation thread for {username}")
        threading.Thread(target=ensure_tasks, daemon=True).start()
    if check_rewards:
        logger.debug(f"Starting reward generation thread for {username}")
        threading.Thread(target=ensure_rewards, daemon=True).start()
    if check_challenges:
        logger.debug(f"Starting challenge generation thread for {username}")
        threading.Thread(target=ensure_challenges, daemon=True).start()
    
    logger.debug(f"Background ensure_minimums started for {username} - {sum([check_tasks, check_rewards, check_challenges])} threads")
