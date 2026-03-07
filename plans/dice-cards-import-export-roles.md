# Dice and Cards: Import/Export, 3-Dice Limit, Role-Based Selection

## Dice import semantics (clarification)

**Do not merge a single die on import.** If anything is given for a die (e.g. die_1), treat that as the **entire** definition for that die. Replace that die fully with the imported object. If face 4 (or any face) is empty in the import, it is meant to be empty — we do not fill in missing keys from the current config. So:

- Payload can contain one or more of `die_1`..`die_4` (and optionally `generic_base_rule`, `full_roll_rule`).
- For each die key present: **full replace** that die with the payload for that die. Empty fields in the payload (e.g. empty face_4) are stored as empty.
- Only dice (and optional top-level rules) present in the payload are updated; other dice are left unchanged.
- No per-die merging: the payload for a die is the complete definition of that die.

---

## Current state (reference)

- **Cards**: Firestore `morning_card_templates`; managed on `templates/morning_cards_manage.html`. APIs in `app.py`, logic in `src/services/morning_card_service.py`.
- **Dice**: One doc per couple in `dice_configurations`; GET/POST `/api/dice-rolls/config`; `DiceRollService.get_dice_configuration`, `save_dice_configuration`.
- **Roles**: `users.can_select_morning_cards` — when true, user can select dice and roll; when false, view-only. Exposed as `window.authState.canSelectMorningCards`.

---

## Phase 1: Import/Export for cards and dice

- **Cards export**: Button on manage page; GET `/api/morning-cards`, serialize templates to JSON, download.
- **Cards import**: Textarea + button; validate array (id = update if exists + permission, else error; no id = create). Backend: `POST /api/morning-cards/import`.
- **Dice export**: Button; GET `/api/dice-rolls/config`, download JSON.
- **Dice import**: Textarea + button; validate shape. For each die present in payload: **full replace** that die (no merging; empty = empty). Optional `generic_base_rule`/`full_roll_rule` replace if provided. Backend: extend POST config or add import endpoint that loads current config, replaces only the die objects (and optional rules) present in payload, normalizes and saves.

---

## Phase 2: Only allow three dice (gray out 4th)

- In `templates/dice-rolls.html`: when 3 checkboxes are checked, disable the unchecked one(s) and add grayed-out class. Remove the logic that unchecks the 4th and shows an alert.

---

## Phase 3: Role-based dice (non–morning-card saves selection; morning-card rolls)

- **Data**: `dice_configurations/{couple_id}.saved_dice_selection` — array of 0–3 indices, default `[]`.
- **Backend**: GET config returns `saved_dice_selection`. New `POST /api/dice-rolls/selection` (allowed only when `can_select_morning_cards === false`). Roll uses `saved_dice_selection` when user has `can_select_morning_cards === true`; empty = base roll.
- **Frontend**: If can save selection: show checkboxes (max 3), "Save selection" button, hide/disable Roll. If can roll: show checkboxes read-only from `saved_dice_selection`, "Roll Dice" uses saved selection.
