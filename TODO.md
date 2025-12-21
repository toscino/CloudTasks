# CloudTasks Project TODO List

## Deployment
- [ ] **Publish flask_base to GitHub** - Put flask_base package on GitHub so it can be installed via `git+https://github.com/...` in requirements.txt instead of bundling locally. This will make deployments cleaner and allow versioning.

## Performance Optimizations

### Database Query Optimizations
- [x] **Optimize task separation in TaskMaster** - Convert Python filtering to database queries for presented vs unpresented tasks
- [x] **Optimize saved/unsaved task separation** - Convert Python filtering to database queries using `saved` field filter
- [x] **Optimize active goal filtering in TaskGenerator** - Convert Python filtering to database queries using `status` field filter
- [x] **Optimize task session retrieval** - Check presented tasks first and return early if 4+ active tasks found, only query unpresented tasks when needed
- [x] **Fix unpresented tasks parameter usage** - `create_new_task_session` now properly uses provided unpresented tasks instead of ignoring them and re-fetching from database
- [x] **Optimize unsaved task fetching** - Only fetch unsaved tasks when actually needed (when saved tasks < 4), avoiding unnecessary database queries
- [x] **Remove redundant saved task filtering** - `complete_task` no longer filters saved tasks since `create_new_task_session` fetches them fresh from database
- [x] **Simplify create_new_task_session interface** - Removed unpresented_tasks parameter, method now handles all task fetching internally
- [x] **Optimize saved task early return** - `create_new_task_session` returns immediately if 4+ saved tasks available, skipping unpresented task queries
- [x] **Eliminate intermediate unsaved_tasks variable** - Directly filter for unpresented tasks in query loop, removing unnecessary intermediate list
- [x] **Standardize `presented_at` field handling** - Always use `null` instead of missing field for unpresented tasks
  - ✅ Updated `TaskModel.to_firestore_dict()` to include `presented_at: null`
  - ✅ Updated `TaskGenerator.generate_tasks_for_category()` to include `presented_at: null`
  - ✅ Created and ran migration script to add `presented_at: null` to all 70 existing tasks
  - ✅ Unpresented task query now uses pure database filtering with `FieldFilter('presented_at', '==', None)`

### Firestore Composite Indexes Required
- [x] **tasks(completed, username, presented_at)** - Created but not usable due to Firestore != None limitation
- [x] **tasks(completed, username, completed_at)** - For optimized statistics queries (✅ CREATED)
- [x] **reward_tasks(status, username, expires_at)** - For optimized reward task expiration filtering (✅ CREATED)
- [ ] **rewards(username, completed, saved, created_at)** - Not needed (function only used for testing)
- [ ] **goals(username, category, status)** - For active goal filtering in task generation
- [ ] **reward_goals(username, status)** - For pending reward goal queries
- [ ] **earned_rewards(username, status)** - For pending earned reward queries
- [ ] **reward_options(username, used)** - For unused reward option queries
  
- [ ] **Optimize database filters** - Convert Python filtering to database-level filtering where possible for better performance
  - Move filtering logic from Python loops to Firestore queries
  - Reduce data transfer and processing overhead
  - Examples: task expiration checks, category filtering, status filtering

### Specific Query Optimizations Identified

#### High Priority (Significant Performance Impact)
- [x] **Reward Service (`src/services/reward_service.py`)** - Lines 23-37
  - **Note**: Function only used for testing, reverted to simple implementation
  - **Impact**: No optimization needed for test-only function

- [x] **Statistics Service (`src/services/statistics_service.py`)** - Lines 69-98
  - ✅ **COMPLETED**: Added `completed_at` timestamp range filters to Firestore query
  - **Impact**: Reduces data transfer from all completed tasks to just this week's tasks (tested: 88→30 tasks)
  - **Index needed**: `tasks(username, completed, completed_at)` (✅ CODE READY)

#### Medium Priority (Moderate Performance Impact)
- [x] **Task Master (`src/core/task_master.py`)** - Lines 188-190
  - ✅ **COMPLETED**: Replaced document fetching with Firestore's built-in count functionality
  - **Impact**: Eliminates data transfer for counting operations (1 read vs potentially thousands)

- [x] **Challenge Master (`src/core/challenge_master.py`)** - Lines 232-250
  - ✅ **COMPLETED**: Added `expires_at >= now` timestamp filter to Firestore query
  - **Impact**: Reduces data transfer by filtering expired tasks at database level
  - **Index needed**: `reward_tasks(username, status, expires_at)` (✅ CODE READY)

#### Low Priority (Minor Performance Impact)
- [ ] **Goal Service (`src/services/goal_service.py`)** - Lines 22-33
  - **Current**: Fetches all goals, groups by category in Python
  - **Note**: Current approach is reasonable since we need all goals anyway
  - **Potential**: Could optimize if we only need goals from specific categories

### Code Quality
- [ ] **Review logging levels** - Ensure debug vs info logs are appropriately set for production
- [ ] **Add more comprehensive error handling** for task generation failures
- [ ] **Consider adding metrics/monitoring** for task generation success rates

## Completed Tasks
- [x] **Fix task counting logic** - `_count_tasks_in_category` now only counts live tasks, not dead ones
- [x] **Add debug logging for task generation** - Improved visibility into ensure_minimums process
- [x] **Identify root cause of Karleigh's missing tasks** - Dead tasks were being counted as live, preventing new task generation
- [x] **Implement expired task deletion** - Expired tasks (>2 hours old) are now automatically deleted when detected, preventing reselection and keeping database clean
- [x] **Optimize task counting logic** - Simplified `_count_tasks_in_category` to skip expiration checks since expired tasks are auto-deleted
- [x] **Fix timezone consistency across app** - Updated all time-based logic to use Central timezone (US/Central) instead of server timezone: task selection, statistics, time-check API, and expired task detection
- [x] **Improve logging format and levels** - Moved caller info to front of log format, cleaned up verbose INFO logs (task generation, session creation, expired task deletion, AI initialization) to DEBUG level while keeping important summary logs as INFO

---
*Last updated: [Current Date]*
*This TODO list tracks ongoing improvements and optimizations for the CloudTasks application.*
