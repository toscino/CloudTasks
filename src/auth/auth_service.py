"""
Authentication service - handles user authentication and session management
"""
import os
from functools import wraps
from typing import Callable, Any, Tuple
from flask import request, session, jsonify
from src.utils.logger import logger


def get_username_from_secret_key(secret_key):
    """Map secret key to username server-side"""
    if not secret_key:
        return 'test_user'  # No key = test user
    
    # Map secret keys to usernames
    if secret_key == os.getenv('USER1_SECRET_KEY'):
        return 'Ian'
    elif secret_key == os.getenv('USER2_SECRET_KEY'):
        return 'Karleigh'
    elif secret_key == os.getenv('USER3_SECRET_KEY'):
        return 'user3'  # Third user
    else:
        return 'test_user'  # Unknown keys default to test user


def get_spouse_username(username):
    """Get spouse username for a given user"""
    spouse_mapping = {
        'Ian': 'Karleigh',
        'Karleigh': 'Ian',
        'user3': 'test_user',  # Third user's spouse
        'test_user': 'test_user'  # Demo user's spouse
    }
    return spouse_mapping.get(username, 'test_user')


def get_user_info():
    """Get authenticated user info using session or secret key validation"""
    try:
        # First check if user is already authenticated in session
        if 'authenticated_user' in session and 'is_authenticated' in session:
            if session['is_authenticated']:
                return session['authenticated_user']
        
        # Fallback to secret key validation
        # Try to get secret key from headers first
        secret_key = request.headers.get('X-Secret-Key')
        
        # Fallback to query parameters
        if not secret_key:
            secret_key = request.args.get('secret_key')
        
        # Determine username server-side (no key = test_user)
        username = get_username_from_secret_key(secret_key)
        session['authenticated_user'] = username
        session['is_authenticated'] = True
        return username
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        # Fallback for any errors
        return 'test_user'


def get_auth_status():
    """Get authentication status using session or secret key validation"""
    try:
        # First check if user is already authenticated in session
        if 'authenticated_user' in session and 'is_authenticated' in session:
            if session['is_authenticated']:
                return True, session['authenticated_user']
        
        # Fallback to secret key validation
        # Try to get secret key from headers first
        secret_key = request.headers.get('X-Secret-Key')
        
        # Fallback to query parameters
        if not secret_key:
            secret_key = request.args.get('secret_key')
        
        # Determine username server-side (no key = test_user)
        username = get_username_from_secret_key(secret_key)
        # Store in session for future requests
        session['authenticated_user'] = username
        session['is_authenticated'] = True
        return True, username
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return False, 'test_user'


def require_auth(f: Callable) -> Callable:
    """
    Decorator that requires authentication for route handlers.
    
    Automatically checks authentication status and returns 401 if not authenticated.
    Passes the authenticated username to the wrapped function.
    
    Usage:
        @app.route('/api/tasks')
        @require_auth
        def get_tasks(username):
            return task_service.get_tasks(username)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs) -> Any:
        try:
            is_authenticated, username = get_auth_status()
            
            if not is_authenticated:
                return jsonify({
                    'status': 'error',
                    'message': 'Authentication required'
                }), 401
            
            # Pass username as first argument to the wrapped function
            return f(username, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Authentication decorator error: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Authentication failed'
            }), 401
    
    return decorated_function
