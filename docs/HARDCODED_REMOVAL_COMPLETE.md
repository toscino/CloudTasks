# Hardcoded Values Removal - Complete

## Summary

Successfully removed hardcoded usernames and project IDs from the codebase. Implemented database-driven spouse linking with pairing code system.

## Changes Made

### Phase 1: Database Structure ✅
- Created `src/services/user_service.py` with:
  - `get_user_settings()` - fetch or create user settings
  - `generate_pairing_code()` - create 6-char pairing codes
  - `link_with_pairing_code()` - validate and link spouses
  - `remove_spouse()` - unlink spouses
  - `update_preferences()` - update user preferences

### Phase 2: Replace Hardcoded Mappings ✅
- **config.py**: Removed `SPOUSE_MAPPING` dictionary, updated `get_spouse()` to use database lookup
- **auth_service.py**: Updated to handle `None` spouse gracefully
- **collaboration_service.py**: Made tracker dynamic - uses logged-in user and their spouse
- **task_generator.py**: Uses `get_spouse()` instead of hardcoded checks
- **morning_card_service.py**: Checks `can_select_morning_cards` preference instead of hardcoded 'Karleigh'

### Phase 3: No Fallbacks ✅
- Removed all project ID fallbacks from scripts
- Updated `app.py` to require `GOOGLE_CLOUD_PROJECT` environment variable
- Updated `run.bat` to fail if `.env` file not found

### Phase 4: Settings UI ✅
- Created `templates/settings.html` with pairing code interface
- Added `/settings` route to `app.py`
- Added API endpoints:
  - `GET /api/user/settings` - get user settings
  - `POST /api/user/generate-pairing-code` - generate pairing code
  - `POST /api/user/link-with-code` - link with pairing code
  - `DELETE /api/user/spouse` - unlink spouse
  - `POST /api/user/preferences` - update preferences
- Added "⚙️ Settings" link to navigation menu

### Phase 5: Documentation ✅
- Added TODO note to `AITaskPrompt.py` about future migration
- Created this summary document

## Database Collections Created

### `users` collection
Each document contains:
- `username` (string, primary key)
- `spouse_username` (string, nullable)
- `can_select_morning_cards` (boolean, default: false)
- `created_at` (timestamp)
- `updated_at` (timestamp)

### `pairing_codes` collection
Each document contains:
- `code` (string, 6-char alphanumeric, indexed)
- `created_by_username` (string)
- `created_at` (timestamp)
- `expires_at` (timestamp) - 15 minutes from creation
- `used` (boolean, default: false)

## How to Use

### For Existing Users (Ian & Karleigh)

1. **Link as spouses:**
   - Ian opens Settings
   - Ian clicks "Generate Pairing Code"
   - Gets code (e.g., "AB3-X9K")
   - Karleigh opens Settings
   - Karleigh enters code and clicks "Link Spouse"
   - Both are now linked

2. **Set morning card preference:**
   - Karleigh opens Settings
   - Checks "Can select morning cards"
   - Ian leaves it unchecked

### For New Users

1. Link spouse using pairing code
2. Set preferences as needed
3. Collaborate! Tracker uses both users' points (or single user if no spouse)

## Single User Mode

If no spouse is linked (`get_spouse()` returns `None`):
- Collaboration tracker uses only the logged-in user's points
- Task generation skips spouse-specific examples
- No errors - this is a valid state

## Migration Notes

- Existing users need to manually link via pairing code
- No automatic migration from hardcoded mapping
- Morning card permission needs to be set manually
- Collaboration tracker will work with any linked spouse pair

## Files Modified

- `src/services/user_service.py` (NEW)
- `src/utils/config.py`
- `src/auth/auth_service.py`
- `src/services/collaboration_service.py`
- `src/core/task_generator.py`
- `src/services/morning_card_service.py`
- `src/core/AITaskPrompt.py` (added TODO note only)
- `app.py`
- `src/scripts/*.py` (all scripts)
- `run.bat`
- `templates/base.html`
- `templates/settings.html` (NEW)

## Intentionally NOT Changed

- `AITaskPrompt.py` - Personal preferences for Ian/Karleigh (intentional)
- `task_master.py` - TIME_WEIGHTS for Ian/Karleigh (personal time preferences)
- Debug scripts - Username examples in comments/docs

## Environment Variables Required

All scripts and app now require:
- `GOOGLE_CLOUD_PROJECT` - Must be set in `.env` file for local development
- On App Engine, automatically set by GCP

## Testing

1. Run app locally (requires `.env` file)
2. Visit `/settings` page
3. Generate pairing code
4. Link two users
5. Verify collaboration tracker works
6. Test morning card selection permission

## Benefits

- No hardcoded usernames in business logic
- Flexible: Works for any number of user pairs
- Privacy: Pairing code system prevents user discovery
- Configurable: Preferences stored in database
- Single user mode: Works without spouse linked
- Cleaner code: No fake mappings or fallbacks

