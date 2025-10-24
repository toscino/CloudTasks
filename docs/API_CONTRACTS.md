# API Contracts

This document describes all API endpoints, their request/response formats, and usage patterns.

## Standard Response Format

All API endpoints return JSON in this format:

### Success Response
```json
{
  "status": "success",
  "message": "Optional human-readable message",
  ...additional fields
}
```

### Error Response
```json
{
  "status": "error",
  "message": "Error description"
}
```

## Authentication

### Session-Based Authentication
- All endpoints use session-based authentication
- Username determined server-side from session
- No authentication tokens required in requests
- Session persists across page navigation

### Login Endpoint

**POST** `/api/login`

**Request**:
```json
{
  "secret_key": "user-secret-key"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Login successful",
  "username": "Ian",
  "authenticated": true
}
```

### Get Current User

**GET** `/api/user`

**Response**:
```json
{
  "status": "success",
  "username": "Ian",
  "authenticated": true,
  "session_based": true
}
```

### Logout

**POST** `/api/logout`

**Response**:
```json
{
  "status": "success",
  "message": "Logged out successfully"
}
```

## Task Management

### Get Tasks

**GET** `/api/tasks`

**Description**: Get active tasks for current user (max 4 tasks)

**Response**:
```json
{
  "status": "success",
  "tasks": [
    {
      "id": "task123",
      "description": "Complete project proposal",
      "category": "Work",
      "difficulty": 7,
      "duration": 30,
      "saved": false,
      "completed": false
    }
  ]
}
```

### Get Task Statistics

**GET** `/api/tasks/statistics`

**Response**:
```json
{
  "status": "success",
  "total_tasks": 42,
  "completed_tasks": 18,
  "by_category": {
    "Work": 10,
    "House": 8,
    "Self": 5
  }
}
```

### Create Task

**POST** `/api/tasks`

**Request**:
```json
{
  "description": "Task description",
  "category": "Work",
  "difficulty": 5,
  "duration": 20
}
```

**Validation**:
- `description` (required): String, not empty
- `category` (optional): String, defaults to "General"
- `difficulty` (optional): Integer 1-10, defaults to 3
- `duration` (optional): Integer, defaults to 10

**Response**:
```json
{
  "status": "success",
  "message": "Task created successfully",
  "task": {
    "id": "task123",
    "description": "Task description",
    "category": "Work",
    "difficulty": 5,
    "duration": 20
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "status": "error",
  "message": "Task description is required"
}
```

### Complete Task

**PUT** `/api/tasks/<task_id>/complete`

**Response**:
```json
{
  "status": "success",
  "message": "Task completed successfully",
  "reward_earned": true
}
```

**Note**: `reward_earned` indicates if user earned a reward based on task difficulty

### Save Task

**PUT** `/api/tasks/<task_id>/save`

**Response**:
```json
{
  "status": "success",
  "message": "Task save status updated"
}
```

## Daily Tasks

### Get Daily Task Templates

**GET** `/api/daily-tasks`

**Response**:
```json
{
  "status": "success",
  "templates": [
    {
      "id": "template123",
      "description": "Exercise",
      "points": 5,
      "days_of_week": [0, 1, 2, 3, 4],
      "active": true
    }
  ]
}
```

### Create Daily Task Template

**POST** `/api/daily-tasks`

**Request**:
```json
{
  "description": "Exercise",
  "points": 5,
  "days_of_week": [0, 1, 2, 3, 4]
}
```

**Validation**:
- `description` (required): String, not empty
- `points` (required): Integer, not zero, range -100 to 100
- `days_of_week` (required): Array of integers (0-6), at least one day
  - 0 = Monday, 1 = Tuesday, ..., 6 = Sunday

**Response**:
```json
{
  "status": "success",
  "message": "Daily task template created",
  "template": {
    "id": "template123",
    "description": "Exercise",
    "points": 5,
    "days_of_week": [0, 1, 2, 3, 4]
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "status": "error",
  "message": "Points must be between -100 and 100"
}
```

### Get Today's Daily Tasks

**GET** `/api/daily-tasks/today`

**Response**:
```json
{
  "status": "success",
  "instances": [
    {
      "id": "instance123",
      "template_id": "template123",
      "description": "Exercise",
      "points": 5,
      "completed": false,
      "date": "2024-01-15"
    }
  ]
}
```

### Complete Daily Task Instance

**PUT** `/api/daily-tasks/today/<instance_id>/complete`

**Response**:
```json
{
  "status": "success",
  "message": "Daily task completed"
}
```

### Update Daily Task Template

**PUT** `/api/daily-tasks/<task_id>`

**Request**:
```json
{
  "description": "Exercise",
  "points": 5,
  "days": [0, 1, 2, 3, 4]
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Template updated"
}
```

### Delete Daily Task Template

**DELETE** `/api/daily-tasks/<task_id>`

**Response**:
```json
{
  "status": "success",
  "message": "Template deleted"
}
```

## Goals Management

### Get Goals

**GET** `/api/goals`

**Response**:
```json
{
  "status": "success",
  "goals": {
    "work": [
      {
        "id": "goal123",
        "description": "Learn Python",
        "priority": "High",
        "status": "Active",
        "delete_on_complete": false
      }
    ],
    "house": [],
    "spouse": []
  }
}
```

### Create Goal

**POST** `/api/goals`

**Request**:
```json
{
  "description": "Learn Python",
  "category": "work",
  "priority": "High",
  "status": "Active",
  "delete_on_complete": false
}
```

**Validation**:
- `description` (required): String, not empty
- `category` (required): String, must be one of: "work", "house", "spouse"
- `priority` (optional): String, one of: "High", "Medium", "Low", defaults to "Medium"
- `status` (optional): String, one of: "Active", "Paused", defaults to "Active"
- `delete_on_complete` (optional): Boolean, defaults to false

**Response**:
```json
{
  "status": "success",
  "message": "Goal created",
  "goal": {
    "id": "goal123",
    "description": "Learn Python",
    "priority": "High",
    "status": "Active"
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "status": "error",
  "message": "Goal description is required"
}
```

### Update Goal

**PUT** `/api/goals/<goal_id>`

**Request**:
```json
{
  "description": "Learn Python",
  "priority": "Medium",
  "status": "Active",
  "delete_on_complete": false
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Goal updated"
}
```

### Delete Goal

**DELETE** `/api/goals/<goal_id>`

**Response**:
```json
{
  "status": "success",
  "message": "Goal deleted"
}
```

### Get Goal Categories

**GET** `/api/goals/categories`

**Response**:
```json
{
  "status": "success",
  "categories": [
    {
      "value": "work",
      "label": "Work",
      "icon": "💼"
    },
    {
      "value": "house",
      "label": "House",
      "icon": "🏠"
    }
  ]
}
```

## Collaboration

### Get Collaboration Tracker

**GET** `/api/collaboration/tracker`

**Response**:
```json
{
  "status": "success",
  "tracker_value": 5,
  "par": 10,
  "stretch_goal": 20,
  "stretch_setting": 10,
  "adjustment_multiplier": 1
}
```

### Get Today's Points

**GET** `/api/collaboration/todays-points`

**Response**:
```json
{
  "status": "success",
  "total_points": 15
}
```

### Update Goals

**POST** `/api/collaboration/goals`

**Request**:
```json
{
  "stretch_setting": 10,
  "adjustment_multiplier": 1
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Goals updated"
}
```

### Get Collaboration History

**GET** `/api/collaboration/history`

**Response**:
```json
{
  "status": "success",
  "history": [
    {
      "date": "2024-01-15",
      "value": 5
    }
  ]
}
```

## Morning Cards

### Get Morning Card Templates

**GET** `/api/morning-cards`

**Response**:
```json
{
  "status": "success",
  "templates": [
    {
      "id": "card123",
      "card_text": "Morning meditation",
      "clothes_points": 1,
      "timer_minutes": 5,
      "ian_rules": [],
      "karleigh_rules": [],
      "active": true
    }
  ]
}
```

### Create Morning Card

**POST** `/api/morning-cards`

**Request**:
```json
{
  "card_text": "Morning meditation",
  "clothes_points": 1,
  "timer_minutes": 5,
  "ian_rules": [],
  "karleigh_rules": [],
  "active": true
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Card created",
  "card": {
    "id": "card123",
    "card_text": "Morning meditation",
    "clothes_points": 1,
    "timer_minutes": 5
  }
}
```

### Get Today's Selection

**GET** `/api/morning-cards/today`

**Response**:
```json
{
  "status": "success",
  "selection": {
    "locked": true,
    "selected_card_ids": ["card1", "card2"],
    "total_clothes_points": 3,
    "total_timer_minutes": 15,
    "ian_rules": [],
    "karleigh_rules": []
  }
}
```

### Lock Today's Selection

**POST** `/api/morning-cards/today/select`

**Request**:
```json
{
  "card_ids": ["card1", "card2"]
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Selection locked"
}
```

### Update Morning Card

**PUT** `/api/morning-cards/<card_id>`

**Request**:
```json
{
  "card_text": "Updated text",
  "clothes_points": 2,
  "timer_minutes": 10,
  "ian_rules": ["Rule 1"],
  "karleigh_rules": ["Rule 2"]
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Card updated"
}
```

### Delete Morning Card

**DELETE** `/api/morning-cards/<card_id>`

**Response**:
```json
{
  "status": "success",
  "message": "Card deleted"
}
```

## Error Handling

### HTTP Status Codes

- **200**: Success
- **400**: Bad Request (validation error)
- **403**: Forbidden (unauthorized access)
- **404**: Not Found (resource doesn't exist)
- **429**: Too Many Requests (rate limit exceeded)
- **500**: Internal Server Error

### Rate Limiting

Endpoints are rate-limited to prevent abuse:

**Per-Endpoint Limits**:
- Task reads (`GET /api/tasks`): 50 per minute
- Task writes (`POST /api/tasks`): 20 per minute
- Task updates (`PUT /api/tasks/*`): 30 per minute
- Daily task reads (`GET /api/daily-tasks`): 50 per minute
- Daily task writes (`POST /api/daily-tasks`): 20 per minute
- Goal reads (`GET /api/goals`): 50 per minute
- Goal writes (`POST /api/goals`): 20 per minute
- Default rate limit: 1000 per hour, 100 per minute

**Rate Limit Exceeded Response** (429 Too Many Requests):
```json
{
  "status": "error",
  "message": "Rate limit exceeded. Please try again later."
}
```

### Error Response Format

```json
{
  "status": "error",
  "message": "Error description"
}
```

## Best Practices

### Request Handling

1. Always check `status` field in response
2. Handle errors gracefully
3. Show user-friendly error messages
4. Log errors for debugging

### Example Usage

```javascript
async function loadTasks() {
    try {
        const data = await apiCall('/api/tasks');
        
        if (data.status === 'success') {
            tasks = data.tasks;
            renderTasks();
        } else {
            showError('#error-message', data.message);
        }
    } catch (error) {
        console.error('Failed to load tasks:', error);
        showError('#error-message', 'Failed to load tasks');
    }
}
```

### Loading States

Show loading states during API calls:

```javascript
showLoading('#loading-state');
hideLoading('#main-content');

try {
    const data = await apiCall('/api/endpoint');
    // Process data
} finally {
    hideLoading('#loading-state');
    showLoading('#main-content');
}
```

## Testing

### Test Endpoint

**GET** `/api/test`

**Purpose**: Test Firestore connection

**Response**:
```json
{
  "status": "success",
  "message": "Firestore connection successful"
}
```

## Notes

- All endpoints support CORS
- Session-based authentication is automatic
- Username is determined server-side
- No authentication tokens required
- All timestamps are in UTC

