"""
Error handling utilities - centralized error handlers and responses
"""
from functools import wraps
from typing import Dict, Any, Callable, Tuple
from flask import jsonify
from src.utils.exceptions import CloudTasksException, NotFoundError, UnauthorizedError, ValidationError, FirestoreError
from src.utils.logger import logger


def create_error_response(message: str, status_code: int = 500, retry_after: str = None) -> Tuple[Any, int]:
    """Create a standardized error response"""
    response = {
        'status': 'error',
        'message': message
    }
    
    if retry_after:
        response['retry_after'] = str(retry_after)
    
    return jsonify(response), status_code


def create_success_response(message: str, data: Dict[str, Any] = None, status_code: int = 200) -> Tuple[Any, int]:
    """Create a standardized success response"""
    response = {
        'status': 'success',
        'message': message
    }
    
    if data:
        response.update(data)
    
    return jsonify(response), status_code


def ratelimit_handler(e: Exception) -> Tuple[Any, int]:
    """Error handler for rate limit exceeded"""
    return create_error_response(
        'Rate limit exceeded. Please slow down and try again later.',
        429,
        str(e.retry_after) if hasattr(e, 'retry_after') else '60'
    )


def handle_service_response(result: Dict[str, Any]) -> Tuple[Any, int]:
    """
    Process a service layer response and return appropriate Flask response.
    
    Handles the standard service response pattern:
    - Checks result['status'] for 'error' or 'success'
    - Maps common error messages to appropriate HTTP status codes
    - Returns jsonified response with correct status code
    
    Args:
        result (dict): Service layer response with 'status' and 'message' keys
        
    Returns:
        tuple: (jsonified_response, status_code)
        
    Example:
        result = service.get_tasks(username)
        return handle_service_response(result)
    """
    if result.get('status') == 'error':
        message_lower = result.get('message', '').lower()
        
        # Map error messages to HTTP status codes
        if 'not found' in message_lower:
            status_code = 404
        elif 'unauthorized' in message_lower:
            status_code = 403
        elif 'already completed' in message_lower or 'already been processed' in message_lower or 'already locked' in message_lower:
            status_code = 400
        elif 'validation' in message_lower or 'required' in message_lower or 'invalid' in message_lower:
            status_code = 400
        else:
            status_code = 500
        
        return jsonify(result), status_code
    
    # Success response
    return jsonify(result), 200


def with_error_handling(f: Callable) -> Callable:
    """
    Decorator that automatically handles service response patterns.
    
    Wraps route handlers that return service layer responses,
    automatically processing them with handle_service_response().
    
    Usage:
        @app.route('/api/tasks')
        @with_error_handling
        def get_tasks(username):
            return task_service.get_tasks(username)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs) -> Any:
        result = f(*args, **kwargs)
        
        # If result is already a Flask response, return it as-is
        if hasattr(result, 'status_code'):
            return result
        
        # If result is a dict with 'status' key, process it
        if isinstance(result, dict) and 'status' in result:
            return handle_service_response(result)
        
        # Otherwise return as-is (for non-standard responses)
        return result
    
    return decorated_function


def handle_exception(e: Exception, context: str = "") -> Dict[str, Any]:
    """
    Handle exceptions and convert to service response format.
    
    Maps specific exception types to appropriate error messages and status codes.
    Logs the error for debugging while returning user-friendly messages.
    
    Args:
        e: Exception that was raised
        context: Additional context about where the error occurred
        
    Returns:
        Dict with 'status' and 'message' keys
        
    Example:
        try:
            # operation
        except NotFoundError as e:
            return handle_exception(e, "Failed to get tasks")
        except Exception as e:
            return handle_exception(e, "Unexpected error")
    """
    # Log the error with context
    if context:
        logger.error(f"{context}: {str(e)}")
    else:
        logger.error(f"Exception: {str(e)}")
    
    # Handle custom exceptions
    if isinstance(e, NotFoundError):
        return {
            'status': 'error',
            'message': e.user_message or 'Resource not found'
        }
    elif isinstance(e, UnauthorizedError):
        return {
            'status': 'error',
            'message': e.user_message or 'Unauthorized access'
        }
    elif isinstance(e, ValidationError):
        return {
            'status': 'error',
            'message': e.user_message or 'Validation failed'
        }
    elif isinstance(e, FirestoreError):
        return {
            'status': 'error',
            'message': e.user_message or 'Database operation failed'
        }
    elif isinstance(e, CloudTasksException):
        return {
            'status': 'error',
            'message': e.user_message or str(e)
        }
    
    # Handle standard exceptions
    error_type = type(e).__name__
    
    # Map common exceptions to user-friendly messages
    if 'NotFound' in error_type or 'NotExist' in error_type:
        return {
            'status': 'error',
            'message': 'Resource not found'
        }
    elif 'Permission' in error_type or 'Access' in error_type:
        return {
            'status': 'error',
            'message': 'Unauthorized access'
        }
    elif 'Validation' in error_type or 'Value' in error_type:
        return {
            'status': 'error',
            'message': 'Invalid input provided'
        }
    
    # Default: return original error message
    return {
        'status': 'error',
        'message': str(e)
    }
