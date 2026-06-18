# Daily reset behavior (lazy / on visit)

The app does **not** run a scheduled cron at 4:00 AM Central. The daily reset runs when server code calls `DailyTaskService.check_and_reset_daily_tasks`, mainly when someone loads the tasks page (`GET /api/tasks` → `get_todays_instances`). Manual test endpoints in `app.py` can also trigger it.

## Reset period (4am–4am Chicago)

A "day" is a **reset period**, not a calendar midnight day. `get_reset_day()` in `src/utils/reset_period.py` defines the active period:

- **Before 4:00 AM Central** → still yesterday's reset day (midnight–3:59 AM counts as the previous day).
- **4:00 AM and later** → today's reset day.

All instance queries, daily points keys, collaboration scoring, and reset gating use this same boundary.

## Flow

```mermaid
sequenceDiagram
    participant User
    participant API as GET_api_tasks
    participant Reset as check_and_reset_daily_tasks
    participant Perf as PerformanceRewardService
    participant Daily as _reset_user_daily_tasks

    User->>API: Open tasks page
    API->>Reset: get_todays_instances
    alt Already reset for reset_day
        Reset-->>API: Already reset today
    else First visit this reset period
        Reset->>Perf: process_missed_reset_rewards(earner, reset_day)
        Reset->>Perf: expire_due_items(reset_day)
        Reset->>Daily: _reset_user (+ spouse)
        Daily->>Perf: create_item_for_yesterday or easiest_for_earned_day
    end
```

## Gate rules

Implemented in `src/services/daily_task_service.py` (`check_and_reset_daily_tasks`):

- At most **one reset per user per reset day** (`daily_task_resets.last_reset_date == get_reset_day()`).
- If `last_reset_date` already matches the current reset day → skip.
- Otherwise → run full reset for **`reset_day`** only.

Performance bonus **expiry** is **not** driven by the frontend. It runs only inside this reset path: `PerformanceRewardService.expire_due_items(reset_day)` uses reset calendar days (`created_at_reset_date + 2`), not rolling 48 hours from wall clock.

## Late reset same day (e.g. 1pm instead of 4am)

Fine as long as it is still the **first** reset that reset day:

| Piece | Behavior |
|--------|----------|
| Performance bonus **expiry** | `expire_due_items(reset_day)` — expire when `reset_day >= created_at_reset_date + 2` |
| Performance bonus **create** | `create_item_for_yesterday` — only **yesterday** (`reset_day - 1`), doc id `{earner}_{earned_for_date}` |
| Daily task instances | Created for **reset_day** only; existing instances for that day are deleted and recreated |
| Task points lock | `lock_daily_threshold_for_date` — **yesterday** only |

A 1pm Tuesday reset is "Tuesday's reset": expire what is due through Tuesday, create Tuesday's daily instances, create bonuses from Monday's points.

## Skipped day (no one opens the app)

Example: reset runs Sunday; **no visit Monday**; first visit **Tuesday 1pm**.

### Performance bonuses — tiered catch-up

Missed resets are inferred from `daily_task_resets.last_reset_date`: every reset day `M` where `last_reset_date < M < reset_day` is a missed reset day. Earn day for reset `M` is `M - 1`.

| Missed resets | Example | Earn day with real work | Gap / empty earn days |
|---------------|---------|-------------------------|------------------------|
| **1** | Tasks Mon, skip Tue, open Wed | **Full credit** — pending bonus item(s); `created_at_reset_date =` missed day `M` (not today), so **1 list day** left on Wed | **Easiest** — band 0 owed to ledger only (e.g. Tue when opening Wed) |
| **2+** | Tasks Mon, skip Tue & Wed, open Thu | **Owed points only** — band math, ledger, no list row | **Easiest** for other gap earn days |

**Normal day** (`gap_count == 0`): `create_item_for_yesterday` only (unchanged).

**Expiry:** On the next reset, `expire_due_items(reset_day)` still uses `created_at_reset_date + 2`. Catch-up full items use the missed reset day as `created_at_reset_date`, so a late check-in does not restart a 2-day list window.

**Task list:** `get_pending_bonus_items` only reads `status == pending`; it does not expire or convert. Items stay visible until a reset runs `expire_due_items`.

### Daily tasks

`_reset_user_daily_tasks` only deletes/creates instances for **`reset_day`**. It does **not** backfill missed days.

Monday's daily task pool never existed: no template instances for that date. `TaskMaster` only selects instances where `date == reset_day`.

### Other single-day reset effects

Per reset, only **reset_day** is cleared/rebuilt for:

- `task_points_daily` tally (`clear_daily_points_for_reset`)
- `threshold_tracking` for that day

## Summary

| Scenario | Bonuses expire | Bonuses created | Daily task instances |
|----------|----------------|-----------------|----------------------|
| Reset 1pm same day | On that day's reset | Yesterday only | Today only |
| Skip 1+ days, then open | All due on first reset (calendar rule) | Tiered catch-up (see above) | **Only** today; skipped days **lost** |

## Pre-4am missed reset

If someone opens **Tuesday 3:00 AM** and **Monday's reset never ran**:

- `reset_day` is still **Monday** → runs Monday's reset, creates Monday instances, locks/creates bonus for Sunday.

## Travel

Reset always uses **America/Chicago** (home timezone), regardless of physical location. This keeps the couple on one shared day.

`travel_day_mode` only changes which task templates apply (weekday 7 = Travel). It does **not** change when the day flips. `vacation_mode` treats every day as Sunday templates for both users.

## Not implemented

- No loop that backfills `daily_task_instances` for missed calendar days.
- No cron — reset remains lazy on first visit each reset period.
- No per-user or device timezone for reset (home Chicago anchor only).
