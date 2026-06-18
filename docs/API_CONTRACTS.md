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

**Description**: Get active daily task session (5 tasks), pending performance bonus items for the assignee, and owed-point balances for the couple.

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
  ],
  "bonus_items": [
    {
      "id": "karleigh_2025-05-21",
      "type": "performance_bonus",
      "description": "Tier 4 reward text",
      "kind": "reward",
      "category": "Reward",
      "earner_username": "karleigh",
      "assignee_username": "ian",
      "earned_for_date": "2025-05-21",
      "days_remaining": 2,
      "owed_conversion_points": 50,
      "can_abandon": true
    }
  ],
  "owed_points": {
    "ian": 0,
    "karleigh": 25
  },
  "stats": {
    "total_instances": 5,
    "completed_instances": 2,
    "total_points": 10,
    "completed_points": 4
  }
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
- `days_of_week` (required): Array of integers (0-7), at least one day
  - 0 = Monday, 1 = Tuesday, ..., 6 = Sunday, 7 = Travel (never matches calendar; only when user has Travel Day mode on)

### Update User Preferences

**POST** `/api/user/preferences`

**Request** (allowed fields):

```json
{
  "can_select_morning_cards": true,
  "inverted": false,
  "vacation_mode": false,
  "travel_day_mode": false
}
```

- `vacation_mode`: Treats every day as Sunday for **both** linked users' tasks; synced to spouse; resets both users with tracker reversal.
- `travel_day_mode`: Treats today as Travel (weekday 7) for **this user only**; not synced to spouse; resets only this user's tasks.
- When both are enabled for the same user, `travel_day_mode` takes precedence over `vacation_mode`.

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

### Get Tracker at Reset

**GET** `/api/collaboration/tracker-at-reset`

Returns the collaboration tracker value at the last daily reset boundary (4:00 AM America/Chicago). Used by the test page for debugging.

**Response**:
```json
{
  "status": "success",
  "tracker_value": 5,
  "date": "2026-06-09",
  "source": "history"
}
```

`source` is `"history"` when a tracker history entry exists before the reset boundary, otherwise `"current"`.

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

## Performance rewards and owed points

Bands are computed at the daily reset from yesterday's `task_points_daily` (`points_earned` vs `streak_threshold`). Goal &lt; 3 skips band evaluation. Each earned slot becomes a bonus item (`{earner}_{earned_for_date}` and `{earner}_{earned_for_date}_2` for the second 2× slot).

Reset is **lazy** (first site visit per day, not a cron). Expiry and creation run only in `check_and_reset_daily_tasks`; the task list API does not expire items. Skipped days, late reset, missed-reset reward catch-up (1 vs 2+ missed days), and missed daily tasks are documented in [DAILY_RESET_BEHAVIOR.md](DAILY_RESET_BEHAVIOR.md).

### Get tier settings

**GET** `/api/performance-tier-settings`

**Response**:
```json
{
  "status": "success",
  "username": "ian",
  "tiers": [
    {
      "band_index": 0,
      "label": "Below goal",
      "kind": "consequence",
      "reward_slots": [
        {
          "item_text": "Consequence text",
          "owed_conversion_points": 10,
          "assign_to": "self"
        }
      ]
    },
    {
      "band_index": 4,
      "label": "2× goal",
      "kind": "reward",
      "reward_slots": [
        { "item_text": "First reward", "owed_conversion_points": 5, "assign_to": "self" },
        { "item_text": "Second reward", "owed_conversion_points": 3, "assign_to": "spouse" }
      ]
    }
  ]
}
```

Tier settings are stored **per user** (`performance_tier_settings/{username}`). When you earn a band, your configured text applies; `assign_to` is relative to you (`self` = you complete it, `spouse` = your partner completes it). Your spouse maintains a separate settings doc for their own rewards/consequences. Bands 0–3 have one slot; band 4 has two (second may be empty text to skip).

### Save tier settings

**PUT** `/api/performance-tier-settings`

**Request**:
```json
{
  "tiers": [ /* five tier objects, same shape as GET */ ]
}
```

### Band preview (today's goals)

**GET** `/api/performance-tier-settings/preview`

Returns dynamic cutoffs (G, steps to 2G) per user for the couple.

### Complete bonus item

**PUT** `/api/performance-bonus/<item_id>/complete`

Assignee only. Marks `completed`; no owed points.

### Abandon bonus item

**PUT** `/api/performance-bonus/<item_id>/abandon`

Assignee only. Immediately credits `owed_conversion_points` to assignee's `owed_points_balance` (same as 3rd-night expiry) and marks `expired`.

### Get owed points

**GET** `/api/owed-points`

**Response**:
```json
{
  "status": "success",
  "balances": {
    "ian": 0,
    "karleigh": 25
  },
  "min_roll_points": {
    "ian": 0,
    "karleigh": 10
  }
}
```

`min_roll_points[user]` = `(balances[user] // 10) * 5` (0 when owed &lt; 10; e.g. 30 owed → 15 pt minimum per roll).

## Dice rolls

Configuration is stored per couple in `dice_configurations`. Each die (`die_1`, `die_2`, …) includes:

- `point_value` (int ≥ 0) — contribution when rolled
- `face_count` (2–20) — sides of the die (random face 1…N when rolled)
- `face_rules` (object) — keys `"1"` … `"face_count"`; text shown when that face is rolled
- `for_usernames` (string[]) — one username (that person only) or both couple members
- `max_rolls` (1–10, capped at `face_count`) — how many times this die may be included in one roll action; each roll uses a distinct face on that die
- `title` — display label

Missing fields on read default to `point_value: 1`, `face_count: 6`, `for_usernames: all couple members`, `max_rolls: 1`.

### Get dice config

**GET** `/api/dice-rolls/config`

**Response** (excerpt):
```json
{
  "status": "success",
  "dice_configs": { "die_1": { "point_value": 2, "face_count": 6, "for_usernames": ["ian"], "...": "..." } },
  "couple_usernames": ["ian", "karleigh"],
  "saved_dice_selection": [],
  "can_roll": true
}
```

### Save dice config

**POST** `/api/dice-rolls/config` — body `{ "dice_configs": { ... } }`

### Import dice config (partial)

**POST** `/api/dice-rolls/config/import` — each die key present is full-replaced.

### Roll dice

**POST** `/api/dice-rolls/roll`

**Request** — explicit selection (no random die pick). Either form:

```json
{ "selected_dice": { "0": 2, "1": 1 } }
```

or

```json
{ "selected_dice": [0, 0, 1] }
```

Indices refer to sorted `die_N` keys. Count per die must not exceed that die's `max_rolls`. Server rejects dice the roller is not allowed to use (`for_usernames`).

**Scoring**: `sum(point_value of rolled dice) - min(point_value)` (0 if fewer than 2 dice rolled). Face values per die are chosen without replacement (no duplicate faces on the same die in one roll). Selection count for a die cannot exceed `face_count`.

**Minimum roll**: When the roller owes at least 10 points, each roll must score at least `(owed // 10) * 5` points (e.g. 30 owed → 15 minimum). Rolls below that minimum are rejected before debiting owed balance.

**Debit**: Subtracts `min(points_scored, roller's owed balance)` from `owed_points_balance/{username}`; ledger id `dice_roll_{roll_id}`.

**Response** (excerpt):
```json
{
  "status": "success",
  "roll_id": "uuid",
  "reroll_used": false,
  "roll_instances": [
    {
      "instance_index": 0,
      "die_index": 0,
      "title": "Chore",
      "point_value": 2,
      "face_value": 3,
      "face_rule": "Do the dishes",
      "rerollable": true
    }
  ],
  "points_scored": 5,
  "points_subtracted": 5,
  "owed_balance_before": 10,
  "owed_balance_after": 5
}
```

Each successful roll is persisted in Firestore `dice_roll_sessions/{roll_id}` (`username`, `couple_id`, `created_at`, `roll_instances`, point summary fields, `reroll_used`). Only the roller’s **two newest** sessions are kept per user (older docs pruned on save).

`rerollable` on an instance: session `reroll_used` is false and at least one **other** face is available on that die (not only the current face; same uniqueness rule as the initial roll).

### Roll history

**GET** `/api/dice-rolls/history`

Returns the current user’s last **2** saved sessions (newest first), read-only.

**Response** (excerpt):
```json
{
  "status": "success",
  "sessions": [
    {
      "roll_id": "uuid",
      "created_at": "2026-05-23T12:00:00",
      "roll_instances": [ "..." ],
      "points_scored": 5,
      "points_subtracted": 5,
      "owed_balance_after": 5,
      "reroll_used": false
    }
  ]
}
```

### Reroll one instance

**POST** `/api/dice-rolls/roll/<roll_id>/reroll`

**Request**:
```json
{ "instance_index": 0 }
```

- Only the roller (`username` on the session) may reroll.
- **One** reroll per session (`reroll_used` must be false).
- New `face_value` is chosen from faces not used by other instances of the same die (current face excluded from the “used” set for this calculation).
- **Does not** change owed balance or re-run debit; `points_scored` / `points_subtracted` unchanged.

**Response**: Same shape as roll response (updated `roll_instances`, all `rerollable: false`, `reroll_used: true`).

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

