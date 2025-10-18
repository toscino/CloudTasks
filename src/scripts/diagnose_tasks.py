#!/usr/bin/env python3
"""
Diagnostic script to see what tasks actually exist in the database
Usage: python diagnose_tasks.py [username]
"""
import os
import sys
from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud.firestore import FieldFilter

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def diagnose_tasks(username=None):
    """Diagnose all tasks in the database for a user"""
    print("=" * 80)
    print("TASK DIAGNOSTIC")
    print("=" * 80)
    
    # Initialize Firestore client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'cloudtasks-app-473120')
    db = firestore.Client(project=project_id)
    
    if username:
        print(f"Diagnosing tasks for: {username}")
    else:
        print("Diagnosing tasks for all users")
    
    # Query ALL tasks for this user (not just incomplete ones)
    if username:
        all_tasks_query = db.collection('tasks').where('username', '==', username)
    else:
        all_tasks_query = db.collection('tasks').stream()
    
    all_tasks_docs = list(all_tasks_query.stream())
    
    print(f"\nFound {len(all_tasks_docs)} total tasks in database")
    
    # Categorize tasks
    completed_tasks = []
    incomplete_tasks = []
    saved_tasks = []
    presented_tasks = []
    unpresented_tasks = []
    expired_tasks = []
    
    current_time = datetime.now()
    
    print(f"\nAnalyzing each task...")
    print("-" * 80)
    
    for doc in all_tasks_docs:
        task_data = doc.to_dict()
        task_id = doc.id
        
        # Basic info
        completed = task_data.get('completed', False)
        saved = task_data.get('saved', False)
        presented_at = task_data.get('presented_at')
        created_at = task_data.get('created_at')
        category = task_data.get('category', 'Unknown')
        description = task_data.get('description', 'No description')[:50]
        
        print(f"Task {task_id[:12]}...")
        print(f"  Description: {description}")
        print(f"  Category: {category}")
        print(f"  Completed: {completed}")
        print(f"  Saved: {saved}")
        print(f"  Presented_at: {presented_at}")
        
        if completed:
            completed_tasks.append(doc)
            print(f"  Status: COMPLETED")
        else:
            incomplete_tasks.append(doc)
            
            if saved:
                saved_tasks.append(doc)
                print(f"  Status: SAVED (incomplete)")
            elif presented_at:
                presented_tasks.append(doc)
                
                # Check if expired
                if hasattr(presented_at, 'timestamp'):
                    presented_datetime = datetime.fromtimestamp(presented_at.timestamp())
                else:
                    presented_datetime = presented_at
                
                age_hours = (current_time - presented_datetime).total_seconds() / 3600
                is_expired = current_time - presented_datetime >= timedelta(hours=2)
                
                if is_expired:
                    expired_tasks.append(doc)
                    print(f"  Status: EXPIRED (age: {age_hours:.1f}h)")
                else:
                    print(f"  Status: ACTIVE PRESENTED (age: {age_hours:.1f}h)")
            else:
                unpresented_tasks.append(doc)
                print(f"  Status: UNPRESENTED (available)")
        
        print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tasks in database: {len(all_tasks_docs)}")
    print(f"Completed tasks: {len(completed_tasks)}")
    print(f"Incomplete tasks: {len(incomplete_tasks)}")
    print(f"  ├─ Saved tasks: {len(saved_tasks)}")
    print(f"  ├─ Presented tasks: {len(presented_tasks)}")
    print(f"  │   ├─ Active (< 2h): {len(presented_tasks) - len(expired_tasks)}")
    print(f"  │   └─ Expired (≥ 2h): {len(expired_tasks)}")
    print(f"  └─ Unpresented tasks: {len(unpresented_tasks)}")
    
    if expired_tasks:
        print(f"\n🚨 FOUND {len(expired_tasks)} EXPIRED TASKS:")
        for doc in expired_tasks:
            task_data = doc.to_dict()
            print(f"  - {doc.id}: {task_data.get('description', 'No description')[:50]}")
    
    return {
        'total': len(all_tasks_docs),
        'completed': len(completed_tasks),
        'incomplete': len(incomplete_tasks),
        'saved': len(saved_tasks),
        'presented': len(presented_tasks),
        'expired': len(expired_tasks),
        'unpresented': len(unpresented_tasks)
    }

def main():
    """Main function to handle command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Diagnose tasks in the database')
    parser.add_argument('username', nargs='?', help='Username to diagnose (optional, diagnoses all users if not provided)')
    
    args = parser.parse_args()
    
    try:
        result = diagnose_tasks(args.username)
        print(f"\nDiagnostic complete!")
        
    except Exception as e:
        print(f"Error during diagnosis: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
