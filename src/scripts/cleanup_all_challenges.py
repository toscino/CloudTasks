#!/usr/bin/env python3
"""
Cleanup All Challenges - Remove all current challenges to start fresh
"""
import sys
import os
from datetime import datetime
import pytz

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from google.cloud import firestore
from google.cloud.firestore import FieldFilter


def cleanup_all_challenges(username=None, dry_run=True):
    """Clean up all challenges for a user or all users"""
    
    # Initialize Firestore
    db = firestore.Client()
    local_tz = pytz.timezone('US/Central')
    current_time = datetime.now(local_tz)
    
    print("=" * 80)
    print("🧹 CHALLENGE CLEANUP TOOL")
    print("=" * 80)
    print(f"Current time: {current_time}")
    print(f"Username filter: {username if username else 'ALL USERS'}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will delete)'}")
    print()
    
    # Get all challenges
    if username:
        challenges_query = db.collection('reward_tasks').where('username', '==', username)
    else:
        challenges_query = db.collection('reward_tasks')
    
    challenges_docs = list(challenges_query.stream())
    
    if not challenges_docs:
        print("✅ No challenges found to clean up!")
        return
    
    print(f"📋 Found {len(challenges_docs)} challenges to clean up")
    print()
    
    # Categorize challenges
    pending_challenges = []
    completed_challenges = []
    other_status_challenges = []
    
    for challenge_doc in challenges_docs:
        challenge_data = challenge_doc.to_dict()
        status = challenge_data.get('status', 'unknown')
        
        if status == 'pending':
            pending_challenges.append(challenge_doc)
        elif status == 'completed':
            completed_challenges.append(challenge_doc)
        else:
            other_status_challenges.append(challenge_doc)
    
    print("📊 CHALLENGE BREAKDOWN:")
    print(f"   Pending challenges: {len(pending_challenges)}")
    print(f"   Completed challenges: {len(completed_challenges)}")
    print(f"   Other status challenges: {len(other_status_challenges)}")
    print()
    
    # Show details of challenges to be deleted
    if pending_challenges:
        print("🔄 PENDING CHALLENGES (will be deleted):")
        for challenge_doc in pending_challenges[:10]:  # Show first 10
            challenge_data = challenge_doc.to_dict()
            presented_at = challenge_data.get('presented_at')
            created_at = challenge_data.get('created_at')
            
            # Calculate age
            if created_at and hasattr(created_at, 'timestamp'):
                created_time = datetime.fromtimestamp(created_at.timestamp(), tz=local_tz)
                age_hours = (current_time - created_time).total_seconds() / 3600
            else:
                age_hours = "unknown"
            
            # Show presentation status
            if presented_at:
                if hasattr(presented_at, 'timestamp'):
                    presented_time = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                    time_since_presented = (current_time - presented_time).total_seconds() / 3600
                    status = f"presented {time_since_presented:.1f}h ago"
                else:
                    status = "presented (unknown time)"
            else:
                status = "unpresented"
            
            print(f"   {challenge_doc.id}: {challenge_data.get('description', 'No description')[:60]}...")
            print(f"     Age: {age_hours:.1f}h, Status: {status}, Goal: {challenge_data.get('reward_goal_id', 'unknown')}")
        
        if len(pending_challenges) > 10:
            print(f"   ... and {len(pending_challenges) - 10} more pending challenges")
        print()
    
    if completed_challenges:
        print("✅ COMPLETED CHALLENGES (will be deleted):")
        for challenge_doc in completed_challenges[:5]:  # Show first 5
            challenge_data = challenge_doc.to_dict()
            completed_at = challenge_data.get('completed_at')
            
            if completed_at and hasattr(completed_at, 'timestamp'):
                completed_time = datetime.fromtimestamp(completed_at.timestamp(), tz=local_tz)
                age_hours = (current_time - completed_time).total_seconds() / 3600
            else:
                age_hours = "unknown"
            
            print(f"   {challenge_doc.id}: {challenge_data.get('description', 'No description')[:60]}...")
            print(f"     Completed {age_hours:.1f}h ago, Goal: {challenge_data.get('reward_goal_id', 'unknown')}")
        
        if len(completed_challenges) > 5:
            print(f"   ... and {len(completed_challenges) - 5} more completed challenges")
        print()
    
    if other_status_challenges:
        print("⚠️  OTHER STATUS CHALLENGES (will be deleted):")
        for challenge_doc in other_status_challenges:
            challenge_data = challenge_doc.to_dict()
            status = challenge_data.get('status', 'unknown')
            print(f"   {challenge_doc.id}: Status='{status}', Goal: {challenge_data.get('reward_goal_id', 'unknown')}")
        print()
    
    # Confirmation and deletion
    if dry_run:
        print("🔍 DRY RUN MODE - No challenges were actually deleted")
        print("💡 To actually delete challenges, run with --live flag")
    else:
        print("⚠️  WARNING: This will permanently delete all challenges!")
        print("💡 Make sure you want to proceed before continuing")
        print()
        
        # Ask for confirmation
        response = input("Type 'DELETE' to confirm deletion: ")
        if response != 'DELETE':
            print("❌ Deletion cancelled")
            return
        
        print("🗑️  Deleting challenges...")
        
        deleted_count = 0
        failed_count = 0
        
        for challenge_doc in challenges_docs:
            try:
                challenge_doc.reference.delete()
                deleted_count += 1
                print(f"   ✅ Deleted {challenge_doc.id}")
            except Exception as e:
                failed_count += 1
                print(f"   ❌ Failed to delete {challenge_doc.id}: {e}")
        
        print()
        print("🎉 CLEANUP COMPLETE!")
        print(f"   Successfully deleted: {deleted_count}")
        print(f"   Failed to delete: {failed_count}")
        
        if failed_count == 0:
            print("   ✅ All challenges cleaned up successfully!")
        else:
            print(f"   ⚠️  {failed_count} challenges could not be deleted")
    
    print("\n" + "=" * 80)


def quick_cleanup(username=None, live=False):
    """Quick cleanup without detailed output"""
    db = firestore.Client()
    
    if username:
        challenges_query = db.collection('reward_tasks').where('username', '==', username)
    else:
        challenges_query = db.collection('reward_tasks')
    
    challenges_docs = list(challenges_query.stream())
    
    if not challenges_docs:
        print("✅ No challenges found")
        return
    
    print(f"🧹 Found {len(challenges_docs)} challenges")
    
    if live:
        response = input(f"Delete all {len(challenges_docs)} challenges? (y/N): ")
        if response.lower() != 'y':
            print("❌ Cancelled")
            return
        
        deleted_count = 0
        for challenge_doc in challenges_docs:
            try:
                challenge_doc.reference.delete()
                deleted_count += 1
            except Exception as e:
                print(f"❌ Failed to delete {challenge_doc.id}: {e}")
        
        print(f"✅ Deleted {deleted_count} challenges")
    else:
        print(f"💡 Run with --live to actually delete them")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up all challenges")
    parser.add_argument("--username", help="Filter by specific username")
    parser.add_argument("--live", action="store_true", help="Actually delete challenges (default is dry run)")
    parser.add_argument("--quick", action="store_true", help="Quick cleanup without detailed output")
    
    args = parser.parse_args()
    
    try:
        if args.quick:
            quick_cleanup(args.username, args.live)
        else:
            cleanup_all_challenges(args.username, not args.live)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
