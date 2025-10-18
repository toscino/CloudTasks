#!/usr/bin/env python3
"""
Check task selection logic for a specific user
Usage: python check_task_selection.py [username]
"""
import os
import sys
from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud.firestore import FieldFilter

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def check_task_selection(username):
    """Check task selection logic for a user"""
    print("=" * 80)
    print(f"TASK SELECTION ANALYSIS FOR {username.upper()}")
    print("=" * 80)
    
    # Initialize Firestore client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'cloudtasks-app-473120')
    db = firestore.Client(project=project_id)
    
    # Get all incomplete tasks for user
    tasks_query = db.collection('tasks').where(
        filter=firestore.And([
            FieldFilter('username', '==', username),
            FieldFilter('completed', '==', False)
        ])
    )
    tasks_docs = tasks_query.stream()
    
    # Categorize tasks
    tasks_by_category = {
        'Work': [],
        'Kids': [],
        'Spouse': [],
        'House': [],
        'Self': []
    }
    
    presented_tasks = []
    unpresented_tasks = []
    
    for doc in tasks_docs:
        task_data = doc.to_dict()
        task_data['id'] = doc.id
        category = task_data.get('category', 'Self')
        presented_at = task_data.get('presented_at')
        
        if category in tasks_by_category:
            tasks_by_category[category].append(task_data)
        
        if presented_at:
            presented_tasks.append(task_data)
        else:
            unpresented_tasks.append(task_data)
    
    print(f"Total incomplete tasks: {sum(len(tasks) for tasks in tasks_by_category.values())}")
    print(f"Presented tasks: {len(presented_tasks)}")
    print(f"Unpresented tasks: {len(unpresented_tasks)}")
    
    print(f"\nTasks by category:")
    for category, tasks in tasks_by_category.items():
        unpresented_in_category = [t for t in tasks if not t.get('presented_at')]
        presented_in_category = [t for t in tasks if t.get('presented_at')]
        
        print(f"  {category}: {len(tasks)} total")
        print(f"    |- Unpresented: {len(unpresented_in_category)}")
        print(f"    `- Presented: {len(presented_in_category)}")
        
        if len(unpresented_in_category) < 5:
            print(f"    WARNING: BELOW MINIMUM (5 required)")
    
    print(f"\nCurrent active session tasks:")
    for task in presented_tasks:
        category = task.get('category', 'Unknown')
        desc = task.get('description', 'No description')[:50]
        presented_at = task.get('presented_at')
        
        if hasattr(presented_at, 'timestamp'):
            presented_datetime = datetime.fromtimestamp(presented_at.timestamp())
        else:
            presented_datetime = presented_at
        
        age_hours = (datetime.now() - presented_datetime).total_seconds() / 3600
        print(f"  {category}: {desc} (age: {age_hours:.1f}h)")
    
    # Check if any categories are below minimum
    below_minimum = []
    for category, tasks in tasks_by_category.items():
        unpresented_count = len([t for t in tasks if not t.get('presented_at')])
        if unpresented_count < 5:
            below_minimum.append((category, unpresented_count))
    
    if below_minimum:
        print(f"\n🚨 Categories below minimum (5 tasks required):")
        for category, count in below_minimum:
            print(f"  {category}: {count} tasks (needs {5-count} more)")
    else:
        print(f"\n✅ All categories have sufficient tasks")
    
    # Show some sample unpresented tasks from each category
    print(f"\nSample unpresented tasks by category:")
    for category, tasks in tasks_by_category.items():
        unpresented = [t for t in tasks if not t.get('presented_at')]
        if unpresented:
            print(f"\n{category} ({len(unpresented)} available):")
            for i, task in enumerate(unpresented[:3]):  # Show first 3
                desc = task.get('description', 'No description')[:60]
                print(f"  {i+1}. {desc}")
            if len(unpresented) > 3:
                print(f"  ... and {len(unpresented)-3} more")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check task selection logic for a user')
    parser.add_argument('username', nargs='?', default='Karleigh', help='Username to check (default: Karleigh)')
    
    args = parser.parse_args()
    
    try:
        check_task_selection(args.username)
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
