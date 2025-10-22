# Disable Challenges Add Daily Tasks

## Overview
Disable the challenges/rewards system without deleting code, then add a new daily tasks feature where users can define recurring tasks with point values that reset at 2am daily. Remove weekly points and reward comparison displays.

## Phase 1: Disable Challenges/Rewards System ✅ COMPLETED

### 1.1 Backend - Remove Challenge Generation Calls
- **File:** `src/utils/background_tasks.py`
  - Remove `check_challenges` parameter from `ensure_minimums()` calls
  - Comment out challenge generation thread logic (keep function intact)

- **Files to update calls:** `app.py`
  - Line 77, 121, 390, 751: Change `ensure_minimums()` calls to `check_challenges=False` or remove parameter

### 1.2 Frontend - Hide Challenges UI
- **File:** `templates/tasks.html`
  - Remove/hide the "Challenges" section (lines 246-253)
  - Remove/hide weekly points stats card (lines 226-240)
  - Remove/hide pending rewards comparison card (lines 232-239)
  - Remove JavaScript functions: `fetchAndDisplayRewards()`, `completeChallenge()`, `loadWeeklyPoints()`, `loadPendingRewards()`
  - Keep all challenge-related code commented/preserved for future use

### 1.3 Navigation - Remove Challenge Pages
- **File:** `templates/base.html` (need to check this)
  - Remove links to rewards-owed page if present in navigation

## Phase 2: Create Daily Tasks System

### 2.1 Backend - Daily Tasks Service
- **New File:** `src/services/daily_task_service.py`
  - Create `DailyTaskService` class with methods:
    - `get_daily_tasks(username)` - Get all daily task templates for user
    - `create_daily_task(data, username)` - Create new daily task template
    - `update_daily_task(task_id, data, username)` - Update daily task template
    - `delete_daily_task(task_id, username)` - Delete daily task template
    - `get_todays_instances(username)` - Get today's task instances (after 2am)
    - `complete_daily_task(instance_id, username)` - Mark daily instance complete
    - `check_and_reset_daily_tasks(username)` - Check if reset needed (lazy reset)

- **Database Schema:**
  - Collection: `daily_task_templates` - stores user-defined daily tasks
    - `username`, `description`, `points`, `days_of_week`, `created_at`, `updated_at`
  - Collection: `daily_task_instances` - stores daily task completions
    - `username`, `template_id`, `description`, `points`, `date`, `completed`, `completed_at`, `created_at`
  - Collection: `daily_task_resets` - tracks last reset per user
    - `username`, `last_reset_date`, `last_reset_at`

### 2.2 Backend - API Endpoints
- **File:** `app.py`
  - Add daily task routes:
    - `GET /api/daily-tasks` - Get daily task templates
    - `POST /api/daily-tasks` - Create daily task template
    - `PUT /api/daily-tasks/<id>` - Update daily task template
    - `DELETE /api/daily-tasks/<id>` - Delete daily task template
    - `GET /api/daily-tasks/today` - Get today's task instances
    - `PUT /api/daily-tasks/today/<id>/complete` - Complete today's instance

### 2.3 Frontend - Daily Tasks Page
- **New File:** `templates/daily_tasks.html`
  - Based on `goals.html` structure but simplified
  - Form to add daily tasks with:
    - Description (textarea)
    - Points (number input)
    - Days of week toggles (checkboxes: Mon, Tue, Wed, Thu, Fri, Sat, Sun)
  - List of all daily task templates with edit/delete
  - Display today's instances with completion checkboxes
  - Show total points earned today
  - No categories or priority (simplified from goals)

### 2.4 Frontend - Main Page Updates
- **File:** `templates/tasks.html`
  - Replace weekly points with daily points display
  - Show "Daily Tasks: X/Y completed" or similar
  - Remove challenges section entirely
  - Keep only regular tasks section

### 2.5 Navigation Updates
- **File:** `templates/base.html`
  - Add "Daily Tasks" link to navigation
  - Remove rewards-owed and challenges links

### 2.6 Background Job - Daily Reset
- **New File:** `src/utils/daily_reset.py`
  - Create function to check if daily tasks need reset (first login after 2am)
  - Called when user accesses daily tasks page or logs in
  - Creates new instances for all templates if last reset was before 2am today
  - Archives/deletes previous day's instances

## Phase 3: Testing & Cleanup

### 3.1 Test Daily Tasks Flow
- Create daily task templates
- Complete instances
- Verify 2am reset logic
- Test point calculations

### 3.2 Verify Challenges Hidden
- Confirm no UI references to challenges
- Verify background generation disabled
- Confirm all challenge code preserved (commented)

## Implementation Notes

### Key Concepts
- **Daily Task Templates**: User-defined recurring tasks (e.g., "Make bed - 2 points")
- **Days of Week**: Simple checkboxes for Mon/Tue/Wed/Thu/Fri/Sat/Sun (e.g., "Every day except Wednesday" or "Only Tuesday/Thursday")
- **Daily Task Instances**: Daily occurrences of templates created on first access after 2am Central time
- **Point System**: Each daily task has a point value, points reset daily
- **Lazy Reset**: Daily tasks reset on first user access after 2am Central time (no scheduler needed)

### Database Design
- **Templates**: Store the recurring task definitions
- **Instances**: Store daily occurrences with completion status
- **Separation**: Daily tasks are completely separate from regular AI-generated tasks

### User Experience
- Users manage templates on a dedicated "Daily Tasks" page
- Main page shows today's daily task progress
- Simple checkbox interface for completing daily tasks
- Points are tracked daily (not weekly like the old system)

## Status
- ✅ Phase 1: COMPLETED - Challenges/rewards system disabled
- ✅ Phase 2: COMPLETED - Daily tasks system implemented
- ✅ Phase 3: COMPLETED - UI improvements and main page integration
