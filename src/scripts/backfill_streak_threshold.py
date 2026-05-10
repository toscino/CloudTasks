"""
One-time backfill: set streak_threshold on existing task_points_daily documents
so past days keep their current interpretation when you change the threshold later.

Run from project root: python -m src.scripts.backfill_streak_threshold

Uses each user's current task_points_config (points_threshold) for their couple.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from google.cloud import firestore

DEFAULT_POINTS_THRESHOLD = 200


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip()


def get_couple_id(db, username: str) -> str:
    user_ref = db.collection('users').document(username)
    doc = user_ref.get()
    if not doc.exists:
        return username
    spouse = doc.to_dict().get('spouse_username')
    if not spouse:
        return username
    return '_'.join(sorted([username, spouse]))


def get_threshold_for_user(db, username: str) -> int:
    couple_id = get_couple_id(db, username)
    config_ref = db.collection('task_points_config').document(couple_id)
    config_doc = config_ref.get()
    if not config_doc.exists:
        return DEFAULT_POINTS_THRESHOLD
    data = config_doc.to_dict()
    val = data.get('points_threshold') or data.get('tier_unlock_points') or data.get('streak_threshold')
    if val is not None and val >= 0:
        return int(val)
    return DEFAULT_POINTS_THRESHOLD


def main():
    load_env()
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        print('GOOGLE_CLOUD_PROJECT not set')
        sys.exit(1)
    db = firestore.Client(project=project_id)
    col = db.collection('task_points_daily')
    updated = 0
    skipped = 0
    for doc in col.stream():
        data = doc.to_dict()
        if data.get('streak_threshold') is not None:
            skipped += 1
            continue
        username = data.get('username')
        if not username:
            skipped += 1
            continue
        threshold = get_threshold_for_user(db, username)
        doc.reference.update({'streak_threshold': threshold})
        updated += 1
        if updated % 100 == 0:
            print(f'Updated {updated} docs...')
    print(f'Done. Updated {updated} docs, skipped {skipped} (already had streak_threshold or no username).')


if __name__ == '__main__':
    main()
