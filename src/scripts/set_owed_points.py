"""
Set owed-point balance for both couple members (testing).

Usage:
  .venv\\Scripts\\python.exe -m src.scripts.set_owed_points --username ian
  .venv\\Scripts\\python.exe -m src.scripts.set_owed_points --username ian --amount 20
"""
import argparse
from google.cloud import firestore

COL_OWED = "owed_points_balance"


def couple_members(db, username: str) -> list[str]:
    doc = db.collection("users").document(username).get()
    if not doc.exists:
        return [username]
    spouse = (doc.to_dict() or {}).get("spouse_username")
    if spouse:
        return sorted([username, spouse])
    return [username]


def main():
    parser = argparse.ArgumentParser(description="Set owed points for a couple")
    parser.add_argument(
        "--username",
        required=True,
        help="Either couple member (spouse is resolved from users collection)",
    )
    parser.add_argument(
        "--amount",
        type=int,
        default=20,
        help="Balance to set for each person (default: 20)",
    )
    args = parser.parse_args()

    if args.amount < 0:
        parser.error("--amount must be >= 0")

    db = firestore.Client()
    users = couple_members(db, args.username.strip())
    for u in users:
        db.collection(COL_OWED).document(u).set({
            "username": u,
            "balance": args.amount,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
        print(f"Set {u} owed balance to {args.amount}")


if __name__ == "__main__":
    main()
