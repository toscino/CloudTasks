"""
Custom exceptions for the CloudTasks application
"""
from typing import Optional


class CloudTasksException(Exception):
    """Base exception for all CloudTasks errors"""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        """
        Initialize exception with technical and user-friendly messages.
        
        Args:
            message: Technical error message (for logging)
            user_message: User-friendly error message (for API responses)
        """
        self.message = message
        self.user_message = user_message or message
        super().__init__(self.message)


class NotFoundError(CloudTasksException):
    """Raised when a requested resource is not found"""
    pass


class UnauthorizedError(CloudTasksException):
    """Raised when user is not authorized to perform an action"""
    pass


class ValidationError(CloudTasksException):
    """Raised when input validation fails"""
    pass


class DatabaseError(CloudTasksException):
    """Raised when a database operation fails"""
    pass


class FirestoreError(DatabaseError):
    """Raised when a Firestore operation fails"""
    pass


class ExternalServiceError(CloudTasksException):
    """Raised when an external service fails"""
    pass


class ConfigurationError(CloudTasksException):
    """Raised when configuration is invalid or missing"""
    pass


class LogicError(CloudTasksException):
    """Raised when business logic validation fails"""
    pass

