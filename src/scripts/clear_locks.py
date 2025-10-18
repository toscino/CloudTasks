#!/usr/bin/env python3
"""
Clear stuck generation locks
"""
from google.cloud import firestore

def clear_all_locks():
    """Clear all generation locks"""
    db = firestore.Client()
    
    # Check what locks exist
    locks_query = db.collection('generation_locks')
    locks_docs = list(locks_query.stream())
    print(f'Found {len(locks_docs)} locks:')
    
    for doc in locks_docs:
        data = doc.to_dict()
        print(f'  Lock ID: {doc.id}, Data: {data}')
    
    # Clear all locks
    for doc in locks_docs:
        doc.reference.delete()
        print(f'Deleted lock: {doc.id}')
    
    print('All locks cleared!')

if __name__ == '__main__':
    clear_all_locks()
