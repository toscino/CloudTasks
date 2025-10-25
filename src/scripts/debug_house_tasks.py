#!/usr/bin/env python3
import sys
sys.path.append('src')
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
import os

# Get username from command line argument
if len(sys.argv) > 1:
    username = sys.argv[1]
else:
    print("Error: Username required as argument")
    print("Usage: python debug_house_tasks.py <username>")
    sys.exit(1)

project_id = os.environ['GOOGLE_CLOUD_PROJECT']
db = firestore.Client(project=project_id)

# Check House tasks specifically
house_query = db.collection('tasks').where(
    filter=firestore.And([
        FieldFilter('username', '==', username),
        FieldFilter('completed', '==', False),
        FieldFilter('category', '==', 'House')
    ])
)
house_tasks = list(house_query.stream())

print(f'House tasks found: {len(house_tasks)}')
for task in house_tasks[:5]:
    data = task.to_dict()
    presented_at = data.get('presented_at')
    has_presented_at_field = 'presented_at' in data
    print(f'  Task {task.id}: has_presented_at_field = {has_presented_at_field}, presented_at = {presented_at}')

# Test different query approaches
print(f'\nTesting different query approaches:')

# Approach 1: Query without presented_at filter
query1 = db.collection('tasks').where(
    filter=firestore.And([
        FieldFilter('username', '==', username),
        FieldFilter('completed', '==', False),
        FieldFilter('category', '==', 'House')
    ])
)
tasks1 = list(query1.stream())
print(f'Query without presented_at filter: {len(tasks1)} tasks')

# Approach 2: Query with saved == False (which should be the same as unpresented)
query2 = db.collection('tasks').where(
    filter=firestore.And([
        FieldFilter('username', '==', username),
        FieldFilter('completed', '==', False),
        FieldFilter('saved', '==', False),
        FieldFilter('category', '==', 'House')
    ])
)
tasks2 = list(query2.stream())
print(f'Query with saved == False: {len(tasks2)} tasks')