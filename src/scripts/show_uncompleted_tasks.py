#!/usr/bin/env python3
"""
Display uncompleted tasks for a specific user
Usage: python show_uncompleted_tasks.py [username]
"""
import os
import sys
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

def format_timestamp(timestamp):
    """Format Firestore timestamp for display"""
    if timestamp is None:
        return "Never"
    
    # Convert Firestore timestamp to datetime if needed
    if hasattr(timestamp, 'timestamp'):
        dt = datetime.fromtimestamp(timestamp.timestamp())
    else:
        dt = timestamp
    
    return dt.strftime("%Y-%m-%d %H:%M")

def show_uncompleted_tasks(username=None):
    """Display uncompleted tasks for a user"""
    print("=" * 60)
    print("UNCOMPLETED TASKS VIEWER")
    print("=" * 60)
    
    # Initialize Firestore client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
    db = firestore.Client(project=project_id)
    
    # If no username provided, show all users
    if username:
        print(f"Showing uncompleted tasks for: {username}")
        tasks_query = db.collection('tasks').where(
            filter=firestore.And([
                FieldFilter('username', '==', username),
                FieldFilter('completed', '==', False)
            ])
        )
    else:
        print("Showing uncompleted tasks for all users")
        tasks_query = db.collection('tasks').where('completed', '==', False)
    
    tasks_docs = tasks_query.stream()
    
    tasks = []
    for doc in tasks_docs:
        task_data = doc.to_dict()
        task_data['id'] = doc.id
        tasks.append(task_data)
    
    if not tasks:
        print(f"\n✅ No uncompleted tasks found!")
        return
    
    print(f"\n📋 Found {len(tasks)} uncompleted task(s)")
    print("-" * 60)
    
    # Group by category
    categories = {}
    for task in tasks:
        category = task.get('category', 'Unknown')
        if category not in categories:
            categories[category] = []
        categories[category].append(task)
    
    # Display tasks by category
    for category, category_tasks in sorted(categories.items()):
        print(f"\n🏷️  {category.upper()} ({len(category_tasks)} tasks)")
        print("-" * 40)
        
        for i, task in enumerate(category_tasks, 1):
            description = task.get('description', 'No description')
            difficulty = task.get('difficulty', 'Unknown')
            duration = task.get('duration', 'Unknown')
            created_at = format_timestamp(task.get('created_at'))
            presented_at = format_timestamp(task.get('presented_at'))
            saved = task.get('saved', False)
            
            # Status indicators
            status_indicators = []
            if saved:
                status_indicators.append("💾 SAVED")
            if task.get('presented_at'):
                status_indicators.append("📱 PRESENTED")
            
            status_text = f" [{', '.join(status_indicators)}]" if status_indicators else ""
            
            print(f"  {i}. {description}")
            print(f"     Difficulty: {difficulty} | Duration: {duration}min | Created: {created_at}")
            if presented_at != "Never":
                print(f"     Presented: {presented_at}")
            if status_text:
                print(f"     Status: {status_text}")
            print()
    
    # Summary by user (if showing all users)
    if not username:
        print("\n📊 SUMMARY BY USER")
        print("-" * 30)
        by_user = {}
        for task in tasks:
            user = task.get('username', 'unknown')
            if user not in by_user:
                by_user[user] = []
            by_user[user].append(task)
        
        for user, user_tasks in sorted(by_user.items()):
            print(f"  {user}: {len(user_tasks)} uncompleted tasks")

def main():
    """Main function"""
    username = None
    if len(sys.argv) > 1:
        username = sys.argv[1]
    
    try:
        show_uncompleted_tasks(username)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
