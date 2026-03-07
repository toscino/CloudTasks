# Clothes Cards Decimal Support

## Current Behavior

- **Clothes points** are integers everywhere: create, update, import, and selection sum
- Formula: `final_clothes = 1 (base) + sum(card.clothes_points)` — stored as `total_clothes_points`
- Input has `min="0"` (no negatives)

## Desired Behavior

- Cards can have decimal `clothes_points` (step 0.1), including **negative** values
- Sum is **floored** with a **minimum of 1** (the base): `final_clothes = max(1, floor(1 + total_clothes))`
- A negative total doesn't make sense — the floor is the base (1)

## Files to Modify

### 1. Backend: [src/services/morning_card_service.py](src/services/morning_card_service.py)

| Location | Change |
|----------|--------|
| `create_card_template` (line 111) | `int(...)` → `float(...)` for clothes_points |
| `import_card_templates` (lines 176, 206) | Validation: `float()` instead of `int()`; store as float |
| `update_card_template` (line 291) | `int(...)` → `float(...)` |
| `select_cards` (lines 503, 508, 522-524) | Sum as float; `final_clothes = max(1, math.floor(base_clothes + total_clothes))` |

### 2. Manage UI: [templates/morning_cards_manage.html](templates/morning_cards_manage.html)

| Location | Change |
|----------|--------|
| Clothes input (line 282) | Add `step="0.1"`, remove or lower `min` to allow negatives (e.g. `min="-10"` or similar) |
| `addCard` (line 775) | `parseInt` → `parseFloat` |
| `updateCard` (line 935) | `parseInt` → `parseFloat` |
| Card preview/tags (lines 737-739) | Format decimals cleanly (e.g. `0.5` not `0.50`, `-0.5` for negatives) |

### 3. Selection UI: [templates/morning_cards.html](templates/morning_cards.html)

| Location | Change |
|----------|--------|
| `updateLiveSummary` (lines 564-592) | Sum as float; display `Math.max(1, Math.floor(totalClothes))` |
| Card preview (lines 455-457) | Format decimals cleanly (including negative values) |

## Floor Logic

```python
# Python (select_cards)
raw_sum = 1 + total_clothes  # can be < 1 if cards are negative
final_clothes = max(1, math.floor(raw_sum))
```

```javascript
// JS (updateLiveSummary)
let rawTotal = 1 + sumOfCardClothes;
document.getElementById('live-clothes').textContent = Math.max(1, Math.floor(rawTotal));
```

## Potential Issues

### 1. Backward compatibility
- Existing cards have integer `clothes_points` in Firestore
- `float(card_data.get('clothes_points', 0))` works for both int and float
- No migration needed

### 2. Import validation
- Switch to `float()` for validation and storage; accepts negatives

### 3. Display formatting
- Show `-0.5`, `0.5`, `1`, `1.5` — avoid `1.0` when whole. Handle negative sign in preview.

### 4. Input bounds
- Remove `min="0"` or set `min="-10"` (or similar) to allow penalty cards
- Keep `max="100"` or adjust if needed

## Summary

- Decimals with step 0.1
- Negative clothes cards supported (penalty cards)
- Final sum floored, with minimum of 1 (base)
