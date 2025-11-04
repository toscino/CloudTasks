"""
Authentication service - wrapper for flask_base authentication
"""
from src.utils.config import get_spouse


def get_user_info(app_manager):
    """Get current authenticated user from flask_base"""
    return app_manager.current_user


def get_auth_status(app_manager):
    """Get authentication status from flask_base"""
    username = app_manager.current_user
    # flask_base returns demo_user if not authenticated, so check if it's not demo
    is_authenticated = username != app_manager.demo_user
    return is_authenticated, username


def get_spouse_username(username):
    """Get spouse username for a given user"""
    spouse_username = get_spouse(username)
    
    # Return spouse if found, None if no spouse linked (single user mode)
    # None is a valid state - no errors needed
    return spouse_username


# Note: Use flask_base's built-in auth parameter instead:
# @app_manager.route("/path", auth=True)  # Requires any auth
# @app_manager.route("/path", "permission")  # Requires specific permission
