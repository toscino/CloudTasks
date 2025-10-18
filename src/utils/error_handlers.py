"""
Error handling utilities - centralized error handlers and responses
"""
from flask import jsonify


def create_error_response(message, status_code=500, retry_after=None):
    """Create a standardized error response"""
    response = {
        'status': 'error',
        'message': message
    }
    
    if retry_after:
        response['retry_after'] = str(retry_after)
    
    return jsonify(response), status_code


def create_success_response(message, data=None, status_code=200):
    """Create a standardized success response"""
    response = {
        'status': 'success',
        'message': message
    }
    
    if data:
        response.update(data)
    
    return jsonify(response), status_code


def ratelimit_handler(e):
    """Error handler for rate limit exceeded"""
    return create_error_response(
        'Rate limit exceeded. Please slow down and try again later.',
        429,
        str(e.retry_after) if hasattr(e, 'retry_after') else '60'
    )
