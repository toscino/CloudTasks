# Remove Hardcoded Usernames from Morning Cards

## Overview
Replace hardcoded `ian_rules` and `karleigh_rules` fields with dynamic `user_rules` map/dictionary that supports any usernames. Remove all hardcoded username references from templates.

## Hardcoded References Found

### 1. `templates/morning_cards_manage.html`
- Lines 211-227: Hardcoded "Ian's Rules" and "Karleigh's Rules" section headers
- Lines 213, 217, 223, 226: Hardcoded function calls `addRule('ian')` and `addRule('karleigh')`
- Lines 248-249: Variables `ianRuleCount` and `karleighRuleCount`
- Lines 309-310: Card tag display using `card.ian_rules` and `card.karleigh_rules`
- Lines 336-347: Collection logic for `ianRules` and `karleighRules` arrays

### 2. `templates/morning_cards.html`
- Lines 290, 296: Hardcoded "Ian's Rules" and "Karleigh's Rules" headers in live summary
- Lines 335, 341: Hardcoded headers in final summary cards
- Lines 291, 297, 336, 342: Element IDs `live-ian-rules`, `live-karleigh-rules`, `summary-ian-rules`, `summary-karleigh-rules`
- Lines 459-460: Preview text using `card.ian_rules` and `card.karleigh_rules`
- Lines 516-521: Rule aggregation using `card.ian_rules` and `card.karleigh_rules`
- Lines 628-642: Display logic using `currentSelection.ian_rules` and `currentSelection.karleigh_rules`

### 3. `templates/base.html`
- Lines 648-649: Hardcoded check `window.authState.currentUsername === 'Karleigh'` for morning card indicator

### 4. `templates/test.html` (Collaboration Tracker Testing)
- Line 133: "Ian's Points" label
- Line 138: "Karleigh's Points" label
- Lines 569-572: Table headers "Ian Pts", "K Pts", "Ian Δ", "K Δ"
- Line 614: Confirmation message with hardcoded names
- Lines 641-642: Result message with hardcoded names

## Data Structure Change

### Before (hardcoded):
```javascript
{
  card_text: "Card description",
  ian_rules: ["rule1", "rule2"],
  karleigh_rules: ["rule3"]
}
```

### After (dynamic):
```javascript
{
  card_text: "Card description",
  user_rules: {
    "Ian": ["rule1", "rule2"],
    "Karleigh": ["rule3"]
  }
}
```

## Implementation Plan

### Backend Changes - `src/services/morning_card_service.py`

**In `create_template` method (lines 50-51, 55-62, 69-70):**
- Remove separate `ian_rules` and `karleigh_rules` field handling
- Accept `user_rules` as a map/dict from request data
- Validate that `user_rules` is a dict with username keys and array values
- Store as `user_rules: { "username": ["rule1", ...] }`

**In `update_template` method (lines 111-120):**
- Replace `ian_rules` and `karleigh_rules` handling with `user_rules` dict validation

**In `select_cards` method (lines 190-191, 294-295, 300-301, 319-320, 334-335):**
- Change from separate `ian_rules`/`karleigh_rules` arrays
- Aggregate all `user_rules` dicts from selected cards
- Merge rules by username: `{"Ian": [...], "Karleigh": [...]}`

**In `get_current_selection` method:**
- Return `user_rules` dict (automatic - just stored structure)

**In `unlock_selection` method (lines 423-424):**
- Reset to `user_rules: {}` instead of separate arrays
- Note: This only resets the daily selection document, NOT the templates
- Templates are permanent and stored separately in `morning_card_templates` collection

### Frontend Changes - `templates/morning_cards_manage.html`

**UI structure:**
- Replace hardcoded sections with dynamic username-based sections
- Add button to "Add User Rules Section"
- For each user section, show:
  - Username label (or input for new username)
  - List of rules for that user
  - Add/remove rule buttons

**JavaScript changes:**
- Remove `ianRuleCount`, `karleighRuleCount` variables
- Use dynamic structure: `userRuleCounts = {}` keyed by username
- Update `addCard()` to collect `user_rules` object
- Update `renderCards()` to iterate over `user_rules` keys
- Update `addRule(username)` to accept any username

### Frontend Changes - `templates/morning_cards.html`

**Display structure:**
- Remove hardcoded "Ian's Rules" and "Karleigh's Rules" headers
- Dynamically create sections for each username in `user_rules`
- Filter to show only current user + spouse (if linked)

**JavaScript changes:**
- Get spouse username from auth state or API
- Filter `card.user_rules` to only show relevant usernames
- Iterate over filtered usernames to display rules
- Update aggregation logic to merge `user_rules` objects

### Frontend Changes - `templates/base.html`

**Morning card indicator (lines 648-649):**
- Remove `window.authState.currentUsername === 'Karleigh'` check
- Replace with permission check using `window.authState.canSelectMorningCards`
- Fetch from user settings API if not in auth state

### Frontend Changes - `templates/test.html`

**UI labels:**
- Replace "Ian's Points" → "Your Points" or fetch from auth state
- Replace "Karleigh's Points" → "Spouse's Points" or fetch spouse username
- Update table headers to use dynamic usernames or generic labels
- Update confirmation/result messages to use auth state usernames

## Migration Script

After implementing the new structure, create a migration script:

**New File:** `src/scripts/migrate_morning_card_rules.py`

```python
"""
Migrate morning card templates from ian_rules/karleigh_rules to user_rules format.
"""
def migrate_morning_cards():
    # Get all templates
    templates = db.collection('morning_card_templates').stream()
    
    for template in templates:
        template_data = template.to_dict()
        
        # Check if already migrated
        if 'user_rules' in template_data:
            continue
        
        # Migrate old format to new format
        user_rules = {}
        if 'ian_rules' in template_data:
            user_rules['Ian'] = template_data['ian_rules']
        if 'karleigh_rules' in template_data:
            user_rules['Karleigh'] = template_data['karleigh_rules']
        
        # Update document
        db.collection('morning_card_templates').document(template.id).update({
            'user_rules': user_rules
        })
        
        print(f"Migrated template {template.id}")

# Also migrate daily selections
def migrate_daily_selections():
    # Get all daily selections
    selections = db.collection('morning_card_selections').stream()
    
    for selection in selections:
        selection_data = selection.to_dict()
        
        # Check if already migrated
        if 'user_rules' in selection_data:
            continue
        
        # Migrate old format to new format
        user_rules = {}
        if 'ian_rules' in selection_data:
            user_rules['Ian'] = selection_data['ian_rules']
        if 'karleigh_rules' in selection_data:
            user_rules['Karleigh'] = selection_data['karleigh_rules']
        
        # Update document
        db.collection('morning_card_selections').document(selection.id).update({
            'user_rules': user_rules
        })
        
        print(f"Migrated selection {selection.id}")
```

## Implementation Notes

- Migration script will be created after backend/frontend changes are complete
- Script migrates both `morning_card_templates` and `morning_card_selections` collections
- Old fields (`ian_rules`/`karleigh_rules`) can be left in place for safety or removed after verification
- `user_rules` is a map/dict where keys are usernames, values are arrays of strings
- Empty rules for a user can be omitted from the map
- Frontend gets spouse username from auth system or API call
- For test page, fetch usernames dynamically from auth state/API

