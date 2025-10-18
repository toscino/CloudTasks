#!/usr/bin/env python3
"""
Quick test to check what tasks exist in Firestore
"""
import os
from google.cloud import firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_tasks():
    print("Checking tasks in Firestore...")
    
    # Initialize Firestore client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
    db = firestore.Client(project=project_id)
    
    # Get all tasks
    tasks_docs = db.collection('tasks').stream()
    
    tasks = []
    for doc in tasks_docs:
        task_data = doc.to_dict()
        task_data['id'] = doc.id
        tasks.append(task_data)
    
    print(f"Total tasks found: {len(tasks)}")
    
    # Group by username
    by_user = {}
    for task in tasks:
        username = task.get('username', 'unknown')
        if username not in by_user:
            by_user[username] = []
        by_user[username].append(task)
    
    print("\nTasks by user:")
    for username, user_tasks in by_user.items():
        print(f"  {username}: {len(user_tasks)} tasks")
        for task in user_tasks:
            print(f"    - {task.get('description', 'No description')} (completed: {task.get('completed', False)})")

if __name__ == "__main__":
    check_tasks()
