#!/usr/bin/env python3
"""Check the current state of reward tasks and goals in the database"""

import os
from google.cloud import firestore
from google.cloud.firestore import FieldFilter

def check_reward_state():
    try:
        # Set up Firestore
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'service-account-key.json'
        db = firestore.Client()
        print("Connected to Firestore successfully")
        
        # Get username from command line argument
        import sys
        if len(sys.argv) > 1:
            username = sys.argv[1]
        else:
            print("Error: Username required as argument")
            print("Usage: python check_reward_state.py <username>")
            sys.exit(1)
        
        print("=== REWARD GOALS ===")
        goals = list(db.collection('reward_goals').where(
            filter=firestore.And([
                FieldFilter('username', '==', username),
                FieldFilter('status', '==', 'pending')
            ])
        ).stream())
        print(f'Found {len(goals)} pending reward goals for {username}')
        for goal in goals:
            data = goal.to_dict()
            print(f'  Goal ID: {goal.id}')
            print(f'  Description: {data.get("description", "No description")[:80]}...')
            print()
        
        print("=== REWARD TASKS ===")
        tasks = list(db.collection('reward_tasks').where('username', '==', username).stream())
        print(f'Found {len(tasks)} total reward tasks for {username}')
        
        pending_tasks = []
        for task in tasks:
            data = task.to_dict()
            status = data.get('status', 'unknown')
            print(f'  Task ID: {task.id}')
            print(f'  Status: {status}')
            print(f'  Goal ID: {data.get("reward_goal_id", "None")}')
            print(f'  Description: {data.get("description", "No description")[:80]}...')
            print()
            
            if status == 'pending':
                pending_tasks.append(task)
        
        print(f"=== SUMMARY ===")
        print(f"Pending goals: {len(goals)}")
        print(f"Pending tasks: {len(pending_tasks)}")
        print(f"Total tasks: {len(tasks)}")
        
        # Check which goals have tasks
        goal_ids = {goal.id for goal in goals}
        task_goal_ids = {task.to_dict().get('reward_goal_id') for task in pending_tasks if task.to_dict().get('reward_goal_id')}
        
        goals_with_tasks = goal_ids & task_goal_ids
        goals_without_tasks = goal_ids - task_goal_ids
        
        print(f"Goals with tasks: {len(goals_with_tasks)}")
        print(f"Goals without tasks: {len(goals_without_tasks)}")
        
        if goals_without_tasks:
            print("Goals needing tasks:")
            for goal_id in goals_without_tasks:
                print(f"  - {goal_id}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_reward_state()
