#!/usr/bin/env python3
"""
Check all users and their task counts in the database
Usage: python check_all_users.py
"""
import os
import sys
from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud.firestore import FieldFilter

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def check_all_users():
    """Check all users and their task counts"""
    print("=" * 80)
    print("ALL USERS TASK CHECK")
    print("=" * 80)
    
    # Initialize Firestore client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'cloudtasks-app-473120')
    print(f"Using project: {project_id}")
    db = firestore.Client(project=project_id)
    
    # Get all tasks (no username filter)
    print(f"\nScanning all tasks in database...")
    all_tasks_docs = list(db.collection('tasks').stream())
    
    print(f"Found {len(all_tasks_docs)} total tasks across all users")
    
    if len(all_tasks_docs) == 0:
        print("No tasks found in database at all!")
        return
    
    # Group by username
    users = {}
    for doc in all_tasks_docs:
        task_data = doc.to_dict()
        username = task_data.get('username', 'NO_USERNAME')
        
        if username not in users:
            users[username] = {
                'total': 0,
                'completed': 0,
                'incomplete': 0,
                'saved': 0,
                'presented': 0,
                'expired': 0,
                'unpresented': 0,
                'tasks': []
            }
        
        users[username]['total'] += 1
        users[username]['tasks'].append((doc.id, task_data))
        
        completed = task_data.get('completed', False)
        if completed:
            users[username]['completed'] += 1
        else:
            users[username]['incomplete'] += 1
            
            saved = task_data.get('saved', False)
            if saved:
                users[username]['saved'] += 1
            else:
                presented_at = task_data.get('presented_at')
                if presented_at:
                    users[username]['presented'] += 1
                    
                    # Check if expired
                    if hasattr(presented_at, 'timestamp'):
                        presented_datetime = datetime.fromtimestamp(presented_at.timestamp())
                    else:
                        presented_datetime = presented_at
                    
                    current_time = datetime.now()
                    is_expired = current_time - presented_datetime >= timedelta(hours=2)
                    
                    if is_expired:
                        users[username]['expired'] += 1
                else:
                    users[username]['unpresented'] += 1
    
    print(f"\nFound {len(users)} users:")
    print("=" * 80)
    
    for username, stats in users.items():
        print(f"\n👤 USER: {username}")
        print(f"   Total tasks: {stats['total']}")
        print(f"   ├─ Completed: {stats['completed']}")
        print(f"   └─ Incomplete: {stats['incomplete']}")
        print(f"       ├─ Saved: {stats['saved']}")
        print(f"       ├─ Presented: {stats['presented']}")
        print(f"       │   ├─ Active: {stats['presented'] - stats['expired']}")
        print(f"       │   └─ Expired: {stats['expired']}")
        print(f"       └─ Unpresented: {stats['unpresented']}")
        
        # Show some task examples
        if stats['tasks']:
            print(f"   Sample tasks:")
            for task_id, task_data in stats['tasks'][:3]:  # Show first 3
                desc = task_data.get('description', 'No description')[:40]
                completed = task_data.get('completed', False)
                saved = task_data.get('saved', False)
                presented = task_data.get('presented_at') is not None
                print(f"     - {task_id[:12]}...: {desc} (completed:{completed}, saved:{saved}, presented:{presented})")
    
    # Look for users with similar names to "Karleigh"
    print(f"\n🔍 Looking for users similar to 'Karleigh':")
    karleigh_variants = []
    for username in users.keys():
        if 'karleigh' in username.lower() or 'kar' in username.lower():
            karleigh_variants.append(username)
    
    if karleigh_variants:
        print(f"Found similar usernames: {karleigh_variants}")
    else:
        print("No usernames similar to 'Karleigh' found")
    
    return users

def main():
    """Main function"""
    try:
        users = check_all_users()
        
        if users:
            print(f"\n✅ Check complete! Found {len(users)} users with tasks.")
        else:
            print(f"\n⚠️  No users with tasks found.")
        
    except Exception as e:
        print(f"Error during check: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
