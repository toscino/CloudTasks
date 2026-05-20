# CloudTasks

Task management app for Google App Engine with Firestore, spouse collaboration, daily routines, morning cards, and task points.

## Setup

1. **Install dependencies**

   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   Uses [flask-base 0.3.1](https://github.com/toscino/flaskbase) (wheel in `requirements.txt`).

2. **Google Cloud**

   - Create a project in [Google Cloud Console](https://console.cloud.google.com/)
   - Enable Firestore
   - Create a service account and download credentials (or use Application Default Credentials locally)
   - Set `GOOGLE_CLOUD_PROJECT` in `.env`

3. **Run locally**

   ```powershell
   .venv\Scripts\python.exe app.py --run
   ```

   Open `http://127.0.0.1:8080/` (demo user works without a key).

4. **Deploy**

   ```powershell
   .venv\Scripts\python.exe app.py --deploy
   # or
   gcloud app deploy app.yaml
   gcloud app deploy config/production.yaml
   ```

   Deploy config details: [docs/CONFIG_GUIDE.md](docs/CONFIG_GUIDE.md).

### Artifact Registry cleanup

Each deploy adds a large image to `gae-standard`. Without cleanup, storage cost grows (~$0.10/GB/month). Root `.gcloudignore` keeps dev-only files out of uploads. Setup Automic Cleanup to delete old images

## Features

- **Tasks** — Main Interface, swipe to complete, categories, goals linkage
- **Daily tasks** — Task Setup and Init, reocurring weekly tasks, Some Randomization Possible
- **Goals** — Personal goals; Not Used, Want better Integrtion with Tasks
- **Task points** — Tracked But Not Well Used
- **Morning cards** — Alternate System for Daily Selection, Probably needs Removed
- **Dice rolls** — Alternate System for Partner Interactions, Should be Migrated to its own App
- **Stats** — Weekly and collaboration metrics
- **Auth** — Session-based login via flask-base (demo + named users)

## Pages

| Route | Template |
|-------|----------|
| `/` | tasks.html |
| `/stats` | stats.html |
| `/goals` | goals.html |
| `/daily-tasks` | daily_tasks.html |
| `/rewards-owed` | rewards_owed.html |
| `/morning-cards` | morning_cards.html |
| `/morning-cards/manage` | morning_cards_manage.html |
| `/dice-rolls` | dice-rolls.html |
| `/settings` | settings.html |
| `/test` | test.html |

## API overview

Routes are defined in `app.py`. Main groups:

| Area | Examples |
|------|----------|
| Tasks | `GET/POST /api/tasks`, complete/save/abandon |
| Goals | `GET/POST /api/goals`, categories |
| Daily tasks | `/api/daily-tasks`, today instances, reset |
| Task points | balance, spend, config, history |
| Collaboration | tracker, today's points, history |
| Rewards owed | `GET /api/rewards-owed`, complete by goal id |
| Morning cards | CRUD, today select/unlock, import |
| Dice rolls | credits, config, roll, import |
| User | settings, spouse link/unlink, preferences |
| Debug | locks, queue reset (dev/test) |

## Authentication

Built on **flask-base** session auth:

- No key → demo user `test_user`
- Valid `secret_key` (query or `POST /api/login`) → mapped user
- Unknown key → falls back to demo user
- Data is isolated by `username` in Firestore

Environment variables (`.env` or App Engine config):

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
FLASK_SECRET=your-flask-secret-key
ADMIN_KEY=your-admin-key
FLASK_BASE_KEY_PREFIX=CT_KEY_
USER1_SECRET_KEY=...
USER2_SECRET_KEY=...
USER3_SECRET_KEY=...
```

Example: `http://127.0.0.1:8080/?secret_key=<USER1_SECRET_KEY>`


## Project structure

```
app.py                 # Flask app and routes
config/                # development.yaml, production.yaml, cleanup policy
src/
  core/task_master.py  # Task queue and generation
  services/            # Task, goal, daily, points, collaboration, etc.
  models/              # Task and goal models
  auth/                # Auth helpers
templates/             # HTML pages
tests/                 # pytest suites
scripts/               # GAE image prune and Artifact Registry policy
docs/                  # CONFIG_GUIDE, frontend notes, etc.
```

## Performance note

Queries currently use single-field Firestore ordering and filter incomplete tasks in Python for flexibility during development. For production scale, add composite indexes and query filters in Firestore (see comment in `app.py`).

## Terminology

- **Tasks** — Regular work (Work, Kids, Spouse, House, Self, General)
- **Goals** — Longer-term targets; can tie to tasks
- **Rewards owed** — Rewards your spouse chose for you to fulfill
- **Daily tasks** — Repeating items with per-day instances
- **Task points** — Currency earned from tasks and spent on configured rewards
