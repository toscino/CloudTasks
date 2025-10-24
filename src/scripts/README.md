# Scripts Directory

This directory contains utility scripts for database maintenance, debugging, and diagnostics.

## Available Scripts

### Diagnostic Scripts

#### `check_all_users.py`
**Purpose**: Check all users and their task counts in the database  
**Usage**: `python src/scripts/check_all_users.py`  
**Output**: Lists all users with their task counts

#### `check_task_selection.py [username]`
**Purpose**: Check task selection logic for a specific user  
**Usage**: `python src/scripts/check_task_selection.py Ian`  
**Output**: Analyzes task selection distribution and categories

#### `check_tasks.py`
**Purpose**: Check tasks in the database  
**Usage**: `python src/scripts/check_tasks.py`

#### `check_challenge_queue.py`
**Purpose**: Check challenge queue status  
**Usage**: `python src/scripts/check_challenge_queue.py`

#### `check_reward_state.py`
**Purpose**: Check reward state  
**Usage**: `python src/scripts/check_reward_state.py`

#### `diagnose_tasks.py [username]`
**Purpose**: Diagnostic tool for task issues  
**Usage**: `python src/scripts/diagnose_tasks.py Ian`

#### `show_uncompleted_tasks.py [username]`
**Purpose**: Display uncompleted tasks for a user  
**Usage**: `python src/scripts/show_uncompleted_tasks.py Ian`  
**Output**: Shows incomplete tasks grouped by category

### Maintenance Scripts

#### `cleanup_all_challenges.py`
**Purpose**: Clean up all challenges  
**Usage**: `python src/scripts/cleanup_all_challenges.py`  
**Warning**: Irreversible operation

#### `cleanup_expired_tasks.py`
**Purpose**: Clean up expired tasks  
**Usage**: `python src/scripts/cleanup_expired_tasks.py`

#### `clear_locks.py`
**Purpose**: Clear generation locks  
**Usage**: `python src/scripts/clear_locks.py`  
**Warning**: May interfere with ongoing operations

#### `standardize_presented_at.py`
**Purpose**: Standardize presented_at timestamps  
**Usage**: `python src/scripts/standardize_presented_at.py`

## Running Scripts

All scripts should be run from the project root directory:

```bash
# From project root
python src/scripts/script_name.py
```

## Configuration

Scripts use the same configuration as the main application:
- Environment variables from `.env` file
- Firestore project from `GOOGLE_CLOUD_PROJECT` environment variable
- Default project: `cloudtasks-app-473120` (fallback)

## Common Use Cases

### Check a user's tasks
```bash
python src/scripts/show_uncompleted_tasks.py Ian
```

### Diagnose task issues
```bash
python src/scripts/diagnose_tasks.py Ian
```

### Check task selection logic
```bash
python src/scripts/check_task_selection.py Karleigh
```

### View all users
```bash
python src/scripts/check_all_users.py
```

## Notes

- Scripts are maintained separately from main application
- Some scripts may modify database state (use with caution)
- Diagnostic scripts are safe to run (read-only)
- Maintenance scripts should be reviewed before execution

