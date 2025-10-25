# Hardcoded Values Audit

## Summary
Found multiple instances of hardcoded values throughout the codebase that should be configurable.

## Critical Issues

### 1. Hardcoded Usernames

#### Location: `src/services/collaboration_service.py`
**Lines**: 228, 232, 258, 266, 410, 418, 443
```python
user_points = self._get_daily_points_for_date('Ian', date)
spouse_points = self._get_daily_points_for_date('Karleigh', date)
```
**Fix**: Use dynamic username from parameters

#### Location: `src/auth/auth_service.py`
**Lines**: 18, 20
```python
if not secret_key:
    return 'Ian'  # Default fallback
```
**Fix**: Return None or empty string instead of hardcoded username

#### Location: `src/core/task_generator.py`
**Lines**: 68-71, 125, 157
```python
if user == "Ian":
    examples_key = "karleigh"
elif user == "Karleigh":
    examples_key = "ian"
```
**Fix**: Use config mapping instead of hardcoded names

#### Location: `src/services/morning_card_service.py`
**Lines**: 211-215
```python
if username != 'Karleigh':
    return {'status': 'error', 'message': 'Only Karleigh can select morning cards'}
```
**Fix**: Move to config or make configurable

### 2. Hardcoded Google Cloud Project IDs

#### Location: Multiple Scripts
**Files**: 
- `src/scripts/check_all_users.py` (line 22)
- `src/scripts/check_task_selection.py` (line 22)
- `src/scripts/cleanup_expired_tasks.py` (line 23)
- `src/scripts/standardize_presented_at.py` (line 35)
- `src/scripts/diagnose_tasks.py` (line 22)
- `src/scripts/delete_old_tasks.py` (line 30)
- `src/scripts/debug_house_tasks.py` (lines 7-8)

**Pattern**: 
```python
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'cloudtasks-app-473120')
```

**Fix**: Use single source of truth from config
- Already handled in `src/utils/config.py`
- Update scripts to use config

#### Location: `app.py`
**Line**: 58
```python
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
```

**Issue**: Different fallback than scripts!
**Fix**: Use same fallback or better yet, use config utility

#### Location: `run.bat`
**Line**: 15
```batch
set GOOGLE_CLOUD_PROJECT=crucial-haiku-473123-r7
```

**Issue**: Third different project ID!
**Fix**: Standardize on one, or make sure .env is always present

### 3. Hardcoded Spouse Mapping

#### Location: `src/utils/config.py`
**Lines**: 37-38
```python
SPOUSE_MAPPING = {
    'Ian': 'Karleigh',
    'Karleigh': 'Ian',
}
```

**Issue**: This is actually good! It's configuration.

#### Location: `src/auth/auth_service.py`
**Lines**: 30-31
```python
SPOUSE_MAPPING = {
    'Ian': 'Karleigh',
    'Karleigh': 'Ian',
}
```

**Issue**: Duplicate! Should import from config.py

#### Location: `src/core/task_master.py`
**Lines**: 22, 28
```python
"Ian": {
    # ... config
}
"Karleigh": {
    # ... config
}
```

**Issue**: Hardcoded user-specific configs
**Fix**: Make generic or configurable

### 4. Hardcoded AI Prompt Content

#### Location: `src/core/AITaskPrompt.py`
**Lines**: 5, 35, 39, 50, 60, 61, 85-87, 91, 113-115, 141, 293, 304, 307, 308, 309, 312

**Issue**: Contains specific personal preferences and preferences for Ian and Karleigh
**Fix**: Extract to config file or make generic

### 5. Hardcoded Default Usernames in Scripts

#### Location: `src/scripts/check_task_selection.py`
**Line**: 121
```python
parser.add_argument('username', nargs='?', default='Karleigh', ...)
```

**Location**: `src/scripts/check_reward_state.py`
**Line**: 15
```python
username = 'Karleigh'
```

**Fix**: No default or use environment variable

## Recommendations

### High Priority
1. ✅ Create `src/utils/config.py` (already done)
2. Fix duplicate spouse mapping in `auth_service.py`
3. Standardize Google Cloud project ID (all scripts use same fallback)
4. Remove hardcoded usernames from `collaboration_service.py`
5. Make AI prompt configurable (or accept as hardcoded for personal use)

### Medium Priority
6. Remove default username from scripts
7. Make morning card restriction configurable
8. Centralize project ID configuration

### Low Priority
9. Clean up run.bat hardcoded values
10. Document which hardcoded values are intentional

## Implementation Plan

### Phase 1: Critical Fixes
1. Import spouse mapping from config.py in auth_service.py
2. Standardize project ID fallback across all scripts
3. Use dynamic usernames in collaboration_service.py

### Phase 2: Script Improvements
4. Remove hardcoded default usernames
5. Update scripts to use config utilities

### Phase 3: Configuration
6. Document intentional hardcoded values
7. Create configuration guide

## Files to Update

### High Priority
- `src/auth/auth_service.py` - Remove duplicate spouse mapping
- `src/services/collaboration_service.py` - Remove hardcoded usernames
- `src/core/task_generator.py` - Use config for username mapping
- `src/services/morning_card_service.py` - Make restriction configurable
- All scripts - Standardize project ID fallback

### Medium Priority
- `src/scripts/check_task_selection.py` - Remove default username
- `src/scripts/check_reward_state.py` - Remove hardcoded username
- `run.bat` - Update project ID reference

### Low Priority
- `src/core/AITaskPrompt.py` - Document intentional hardcoding
- `src/core/task_master.py` - Document user-specific configs

