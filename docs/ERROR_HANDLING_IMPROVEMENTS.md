# Error Handling Improvements

## Overview

Created custom exception classes and helper functions to improve error handling throughout the application.

## New Components

### 1. Custom Exceptions (`src/utils/exceptions.py`)

Created hierarchy of custom exceptions:

```python
CloudTasksException          # Base exception
├── NotFoundError            # Resource not found
├── UnauthorizedError        # Unauthorized access
├── ValidationError          # Input validation failed
├── DatabaseError            # Database operation failed
│   └── FirestoreError      # Firestore-specific error
├── ExternalServiceError     # External service (OpenAI) failed
├── ConfigurationError       # Configuration invalid/missing
└── LogicError              # Business logic validation failed
```

**Key Features**:
- Each exception has both `message` (technical) and `user_message` (user-friendly)
- Hierarchical structure allows catching specific error types
- Better error categorization

### 2. Exception Handler (`src/utils/error_handlers.py`)

Added `handle_exception()` function:

```python
def handle_exception(e: Exception, context: str = "") -> Dict[str, Any]:
    """
    Handle exceptions and convert to service response format.
    
    Maps specific exception types to appropriate error messages.
    Logs errors for debugging while returning user-friendly messages.
    """
```

**Benefits**:
- Consistent error handling across services
- Automatic logging with context
- User-friendly error messages
- Maps exception types to appropriate status codes

## Before vs After

### Before (Generic Exception Handling)
```python
def get_goals(self, username: str) -> Dict[str, Any]:
    try:
        # Query goals
        goals_query = self.db.collection('goals').where('username', '==', username)
        goals_docs = goals_query.stream()
        
        # Process results
        goals_by_category = {}
        for doc in goals_docs:
            goal_data = prepare_firestore_document(doc)
            # ...
        
        return {'status': 'success', 'goals': goals_by_category}
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to get goals: {str(e)}'
        }
```

**Problems**:
- Too broad - catches all exceptions
- No distinction between error types
- Could hide bugs
- Generic error messages

### After (Specific Exception Handling)
```python
def get_goals(self, username: str) -> Dict[str, Any]:
    try:
        # Query goals
        goals_query = self.db.collection('goals').where('username', '==', username)
        goals_docs = goals_query.stream()
        
        # Process results
        goals_by_category = {}
        for doc in goals_docs:
            goal_data = prepare_firestore_document(doc)
            # ...
        
        return {'status': 'success', 'goals': goals_by_category}
    except FirestoreError as e:
        return handle_exception(e, "Failed to query goals")
    except Exception as e:
        return handle_exception(e, "Unexpected error getting goals")
```

**Benefits**:
- Specific exception types
- Better error messages
- Easier debugging
- Proper error categorization

## Usage Examples

### Example 1: Resource Not Found
```python
from src.utils.exceptions import NotFoundError

def get_goal(self, goal_id: str, username: str) -> Dict[str, Any]:
    try:
        doc_ref = self.db.collection('goals').document(goal_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise NotFoundError(
                f"Goal {goal_id} not found",
                user_message="Goal not found"
            )
        
        # Process goal
        return {'status': 'success', 'goal': goal_data}
    except NotFoundError:
        return handle_exception(e, "Failed to get goal")
    except Exception as e:
        return handle_exception(e, "Unexpected error")
```

### Example 2: Validation Error
```python
from src.utils.exceptions import ValidationError

def create_goal(self, data: Dict[str, Any], username: str) -> Dict[str, Any]:
    try:
        if not data or not data.get('description'):
            raise ValidationError(
                "Description is required",
                user_message="Goal description is required"
            )
        
        if len(data['description']) > 500:
            raise ValidationError(
                "Description too long",
                user_message="Description must be 500 characters or less"
            )
        
        # Create goal
        return {'status': 'success', 'goal_id': goal_id}
    except ValidationError:
        return handle_exception(e, "Failed to create goal")
    except Exception as e:
        return handle_exception(e, "Unexpected error")
```

### Example 3: Unauthorized Access
```python
from src.utils.exceptions import UnauthorizedError

def update_goal(self, goal_id: str, data: Dict[str, Any], username: str) -> Dict[str, Any]:
    try:
        doc_ref = self.db.collection('goals').document(goal_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise NotFoundError("Goal not found", user_message="Goal not found")
        
        goal_data = doc.to_dict()
        if goal_data.get('username') != username:
            raise UnauthorizedError(
                f"Goal {goal_id} belongs to {goal_data.get('username')}, not {username}",
                user_message="Unauthorized: Goal belongs to another user"
            )
        
        # Update goal
        return {'status': 'success'}
    except (NotFoundError, UnauthorizedError) as e:
        return handle_exception(e, "Failed to update goal")
    except Exception as e:
        return handle_exception(e, "Unexpected error")
```

## Migration Strategy

### Step 1: Use New Exceptions Gradually
- Start with new code
- Refactor critical paths first
- Keep existing code working

### Step 2: Replace Generic Exception Handling
- Replace `except Exception as e:` with specific exceptions
- Use `handle_exception()` for consistent responses
- Add context strings for better logging

### Step 3: Add Validation
- Raise `ValidationError` for invalid input
- Raise `NotFoundError` for missing resources
- Raise `UnauthorizedError` for access violations

## Benefits

1. **Better Error Messages**:
   - User-friendly messages for API responses
   - Technical messages for logging
   - Context-aware error handling

2. **Easier Debugging**:
   - Specific exception types
   - Better error categorization
   - Context in logs

3. **More Robust**:
   - Don't hide bugs with broad catches
   - Proper error propagation
   - Better error recovery

4. **Consistent**:
   - Standardized error handling
   - Uniform error responses
   - Centralized error logic

## Implementation Status

### Completed ✅
- Created custom exception classes
- Created `handle_exception()` helper function
- Updated imports in goal_service.py
- No linter errors

### Recommended Next Steps
1. Gradually refactor services to use new exceptions
2. Start with critical paths (create, update, delete operations)
3. Add validation errors for input validation
4. Add specific exceptions for common error cases

## Notes

- Existing code continues to work (backward compatible)
- Can be adopted gradually
- No breaking changes
- Improves code quality over time

