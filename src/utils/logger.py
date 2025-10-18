"""
Centralized logging system for a Cloud Tasks application, compatible with
Google App Engine (production) and local development environments.

This version uses modern best practices for Google Cloud Logging, including
explicit handler attachment and structured logging for powerful filtering
and analysis in the Google Cloud Console.
"""
import os
import logging
from typing import Dict, Any

# Try to import Google Cloud Logging; fall back to standard logging if not available.
try:
    from google.cloud.logging.handlers import CloudLoggingHandler
    import google.cloud.logging
    CLOUD_LOGGING_AVAILABLE = True
except ImportError:
    CLOUD_LOGGING_AVAILABLE = False

class CloudTasksLogger:
    """
    A centralized logger that automatically switches between Google Cloud Logging
    (in a GCP environment) and a standard stream logger (for local development).
    """

    def __init__(self, name: str = "cloudtasks"):
        """Initializes the logger and sets up the appropriate handler."""
        self.name = name
        self.logger = logging.getLogger(self.name)
        # Set level to DEBUG to capture all logs. Handlers will filter later.
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False  # Prevent duplicate logs in the root logger.
        
        self._setup_logger()
        self._log_initial_environment_info()

    def _is_gcp_environment(self) -> bool:
        """
        Checks if the code is running in a Google Cloud Platform environment.
        This is a common way to detect environments like App Engine, Cloud Run, etc.
        """
        return 'GAE_ENV' in os.environ or 'GOOGLE_CLOUD_PROJECT' in os.environ

    def _setup_logger(self):
        """Sets up the logger with the appropriate backend based on the environment."""
        # Clear any existing handlers to prevent duplication during re-initialization.
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        if CLOUD_LOGGING_AVAILABLE and self._is_gcp_environment():
            # --- PRODUCTION/GCP LOGGING ---
            # Use Google Cloud Logging handler directly for better control.
            try:
                client = google.cloud.logging.Client()
                # The CloudLoggingHandler will send logs to the Cloud Logging API.
                handler = CloudLoggingHandler(client, name=self.name)
                # You can set the level on the handler itself for production.
                handler.setLevel(logging.INFO)
                self.logger.addHandler(handler)
                print(f"CloudTasks Logger: Attached Google Cloud Logging handler for '{self.name}'.")
            except Exception as e:
                # Fallback if Cloud Logging initialization fails for any reason.
                print(f"CloudTasks Logger: Cloud Logging failed ({e}), falling back to standard logger.")
                self._setup_standard_logger()
        else:
            # --- LOCAL DEVELOPMENT LOGGING ---
            print("CloudTasks Logger: Using standard stream logger for local development.")
            self._setup_standard_logger()

    def _setup_standard_logger(self):
        """Sets up a standard Python logger that writes to the console."""
        handler = logging.StreamHandler()
        # The handler should capture all messages from the logger.
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _log_initial_environment_info(self):
        """Logs key environment details for debugging purposes on startup."""
        env_details = {
            "is_gcp": self._is_gcp_environment(),
            "cloud_logging_available": CLOUD_LOGGING_AVAILABLE,
            "logger_level": logging.getLevelName(self.logger.getEffectiveLevel()),
            "project_id": os.getenv('GOOGLE_CLOUD_PROJECT', 'Not Set'),
        }
        self.info("Logger initialized.", **env_details)

    def _log(self, level: int, message: str, **kwargs):
        """
        Internal log method that handles structured data.

        In Google Cloud Logging, 'kwargs' will be attached as a structured
        'jsonPayload', which is incredibly useful for filtering and analysis.
        For the local logger, we'll format it into a simple string.
        """
        if kwargs:
            # Format kwargs into the message for both environments to avoid empty logs
            formatted_kwargs = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
            formatted_message = f"{message} ({formatted_kwargs})"
            self.logger.log(level, formatted_message)
        else:
            # No extra data, just log the message
            self.logger.log(level, message)

    # --- Public Logging Methods ---
    def debug(self, message: str, **kwargs: Any):
        """Logs a message with level DEBUG."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any):
        """Logs a message with level INFO."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any):
        """Logs a message with level WARNING."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any):
        """Logs a message with level ERROR."""
        self._log(logging.ERROR, message, **kwargs)

    # --- Legacy Methods for Backward Compatibility ---
    def ensure_minimum_check(self, username: str, check_type: str, current_count: int, 
                           minimum_required: int, items_generated: int = 0):
        """Log ensure minimum check results"""
        if items_generated > 0:
            self.info(f"{check_type}: generated {items_generated} items", 
                     username=username, check_type=check_type, 
                     current_count=current_count, minimum_required=minimum_required,
                     items_generated=items_generated)
    
    def ai_call(self, username: str, purpose: str, model: str, tokens_used: int, 
                success: bool, summary: str = ""):
        """Log AI call with token usage and summary"""
        status = "✓" if success else "✗"
        self.info(f"AI {purpose}: {tokens_used} tokens {status}", 
                 username=username, purpose=purpose, model=model, 
                 tokens_used=tokens_used, success=success, summary=summary)
    
    def api_interaction(self, endpoint: str, method: str, username: str, 
                       status_code: int, response_summary: str = ""):
        """Log major API interactions"""
        self.info(f"{method} {endpoint}: {status_code} {response_summary}",
                 endpoint=endpoint, method=method, username=username, 
                 status_code=status_code, response_summary=response_summary)
    
    def task_completion(self, username: str, task_id: str, difficulty: int, 
                       reward_earned: bool):
        """Log task completion with reward status"""
        reward_text = "🎁" if reward_earned else ""
        self.info(f"Task completed: difficulty {difficulty} {reward_text}",
                 username=username, task_id=task_id, difficulty=difficulty, 
                 reward_earned=reward_earned)
    
    def reward_selection(self, username: str, reward_id: str, option_selected: str):
        """Log reward option selection"""
        self.info(f"Reward selected: {option_selected[:50]}...",
                 username=username, reward_id=reward_id, option_selected=option_selected)

# --- Global logger instance ---
# This makes it easy to import and use the logger from anywhere in the app.
logger = CloudTasksLogger()

# --- Convenience functions for backward compatibility ---
def debug(message: str, **kwargs):
    logger.debug(message, **kwargs)

def info(message: str, **kwargs):
    logger.info(message, **kwargs)

def warning(message: str, **kwargs):
    logger.warning(message, **kwargs)

def error(message: str, **kwargs):
    logger.error(message, **kwargs)

# --- Example Usage ---
# You can import `logger` from this file in other parts of your application.
if __name__ == '__main__':
    print("\n--- Running Logger Examples ---")

    # Simple info log
    logger.info("User logged in successfully.", username="testuser@example.com", session_id="abc-123")

    # A debug log (will only show up locally by default)
    logger.debug("Processing queue item.", item_id=987, queue_name="default")
    
    # A warning
    logger.warning("API response time is high.", endpoint="/api/v1/data", response_time_ms=2500)

    # An error
    logger.error("Failed to connect to database.", db_host="10.0.0.5", error_code=503)

    print("\n--- End of Examples ---")
    print("In Google Cloud, the extra data (username, item_id, etc.) would appear as a searchable jsonPayload.")