"""
Optional one-off cleanup of deprecated Firestore collections (reward/challenge/morning card).

Run only after confirming you no longer need historical data:
  .venv\\Scripts\\python.exe -m src.scripts.cleanup_legacy_firestore --dry-run
  .venv\\Scripts\\python.exe -m src.scripts.cleanup_legacy_firestore --execute
"""
import argparse
from google.cloud import firestore

LEGACY_COLLECTIONS = [
    "reward_goals",
    "reward_tasks",
    "earned_rewards",
    "rewards",
    "morning_card_templates",
    "morning_card_selections",
]


def delete_collection(db, name: str, dry_run: bool) -> int:
    count = 0
    for doc in db.collection(name).stream():
        count += 1
        if not dry_run:
            doc.reference.delete()
    return count


def main():
    parser = argparse.ArgumentParser(description="Delete legacy Firestore collections")
    parser.add_argument("--dry-run", action="store_true", help="Count documents only")
    parser.add_argument("--execute", action="store_true", help="Actually delete documents")
    args = parser.parse_args()
    if not args.dry_run and not args.execute:
        parser.error("Specify --dry-run or --execute")
    dry_run = args.dry_run or not args.execute

    db = firestore.Client()
    for name in LEGACY_COLLECTIONS:
        n = delete_collection(db, name, dry_run)
        action = "would delete" if dry_run else "deleted"
        print(f"{name}: {action} {n} document(s)")


if __name__ == "__main__":
    main()
