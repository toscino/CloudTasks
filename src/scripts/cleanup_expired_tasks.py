#!/usr/bin/env python3
"""
Cleanup script to remove expired tasks from the database
Usage: python cleanup_expired_tasks.py [username]
If no username provided, cleans up for all users
"""
import os
import sys
from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud.firestore import FieldFilter

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def cleanup_expired_tasks(username=None):
    """Remove expired tasks from the database"""
    print("=" * 60)
    print("EXPIRED TASKS CLEANUP")
    print("=" * 60)
    
    # Initialize Firestore client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'cloudtasks-app-473120')
    db = firestore.Client(project=project_id)
    
    if username:
        print(f"Cleaning up expired tasks for: {username}")
        tasks_query = db.collection('tasks').where(
            filter=firestore.And([
                FieldFilter('username', '==', username),
                FieldFilter('completed', '==', False)
            ])
        )
    else:
        print("Cleaning up expired tasks for all users")
        tasks_query = db.collection('tasks').where('completed', '==', False)
    
    tasks_docs = tasks_query.stream()
    
    total_tasks = 0
    expired_tasks = 0
    saved_tasks = 0
    active_tasks = 0
    deleted_tasks = 0
    
    current_time = datetime.now()
    
    print(f"\nScanning tasks...")
    
    for doc in tasks_docs:
        task_data = doc.to_dict()
        task_id = doc.id
        total_tasks += 1
        
        # Check if task is saved
        if task_data.get('saved', False):
            saved_tasks += 1
            print(f"  ✓ Task {task_id}: SAVED (skipping)")
            continue
        
        # Check if task has presented_at timestamp
        presented_at = task_data.get('presented_at')
        if not presented_at:
            active_tasks += 1
            print(f"  ✓ Task {task_id}: UNPRESENTED (active)")
            continue
        
        # Convert Firestore timestamp to datetime if needed
        if hasattr(presented_at, 'timestamp'):
            presented_datetime = datetime.fromtimestamp(presented_at.timestamp())
        else:
            presented_datetime = presented_at
        
        # Check if task is expired (older than 2 hours)
        age_hours = (current_time - presented_datetime).total_seconds() / 3600
        is_expired = current_time - presented_datetime >= timedelta(hours=2)
        
        if is_expired:
            expired_tasks += 1
            print(f"  ✗ Task {task_id}: EXPIRED (age: {age_hours:.1f}h) - DELETING")
            
            try:
                doc.reference.delete()
                deleted_tasks += 1
                print(f"    → Deleted successfully")
            except Exception as e:
                print(f"    → ERROR deleting: {e}")
        else:
            active_tasks += 1
            print(f"  ✓ Task {task_id}: ACTIVE (age: {age_hours:.1f}h)")
    
    print(f"\n" + "=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"Total tasks scanned: {total_tasks}")
    print(f"Saved tasks (preserved): {saved_tasks}")
    print(f"Active tasks (preserved): {active_tasks}")
    print(f"Expired tasks found: {expired_tasks}")
    print(f"Tasks deleted: {deleted_tasks}")
    
    if deleted_tasks > 0:
        print(f"\n[SUCCESS] Cleanup completed! Removed {deleted_tasks} expired tasks.")
    else:
        print(f"\n[SUCCESS] No expired tasks found. Database is clean!")
    
    return {
        'total_scanned': total_tasks,
        'saved_tasks': saved_tasks,
        'active_tasks': active_tasks,
        'expired_tasks': expired_tasks,
        'deleted_tasks': deleted_tasks
    }

def main():
    """Main function to handle command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up expired tasks from the database')
    parser.add_argument('username', nargs='?', help='Username to clean up (optional, cleans all users if not provided)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN MODE - No tasks will actually be deleted")
        print("=" * 60)
    
    try:
        result = cleanup_expired_tasks(args.username)
        
        if args.dry_run:
            print(f"\n DRY RUN: Would delete {result['expired_tasks']} expired tasks")
            print("Run without --dry-run to actually perform the cleanup")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
