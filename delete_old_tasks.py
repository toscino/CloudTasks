#!/usr/bin/env python3
"""
Delete all tasks that don't have the presented_at field (old tasks)
"""
import os
import sys
import logging
from google.cloud import firestore

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def delete_old_tasks(dry_run=True, username=None):
    """
    Delete tasks that don't have the presented_at field.
    
    Args:
        dry_run (bool): If True, only count tasks that would be deleted
        username (str): If specified, only delete tasks for this user
    """
    try:
        # Initialize Firestore client
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'cloudtasks-app-473120')
        db = firestore.Client(project=project_id)
        
        logger.info(f"Starting old task deletion {'(DRY RUN)' if dry_run else '(LIVE RUN)'}")
        logger.info(f"Project: {project_id}")
        if username:
            logger.info(f"Username filter: {username}")
        
        # Get all tasks
        tasks_ref = db.collection('tasks')
        if username:
            tasks_query = tasks_ref.where('username', '==', username)
        else:
            tasks_query = tasks_ref
        
        tasks_to_delete = []
        total_tasks = 0
        
        # Scan all tasks
        for doc in tasks_query.stream():
            total_tasks += 1
            task_data = doc.to_dict()
            
            # Check if presented_at field is missing
            if 'presented_at' not in task_data:
                tasks_to_delete.append({
                    'id': doc.id,
                    'username': task_data.get('username', 'unknown'),
                    'description': task_data.get('description', 'No description')[:50],
                    'category': task_data.get('category', 'Unknown'),
                    'completed': task_data.get('completed', False)
                })
        
        logger.info(f"Scanned {total_tasks} total tasks")
        logger.info(f"Found {len(tasks_to_delete)} old tasks without presented_at field")
        
        if not tasks_to_delete:
            logger.info("✅ No old tasks found!")
            return
        
        # Show sample of tasks to be deleted
        logger.info("\n📋 Tasks to be deleted:")
        for i, task in enumerate(tasks_to_delete):
            status = "COMPLETED" if task['completed'] else "INCOMPLETE"
            logger.info(f"  {i+1}. {task['username']} [{task['category']}] [{status}]: {task['description']}... (ID: {task['id'][:8]}...)")
        
        if dry_run:
            logger.info(f"\n🔍 DRY RUN: Would delete {len(tasks_to_delete)} old tasks")
            logger.info("Run with dry_run=False to perform actual deletion")
            return
        
        # Perform the deletion
        logger.info(f"\n🚀 Starting deletion of {len(tasks_to_delete)} old tasks...")
        deleted_count = 0
        error_count = 0
        
        for i, task in enumerate(tasks_to_delete):
            try:
                doc_ref = db.collection('tasks').document(task['id'])
                doc_ref.delete()
                deleted_count += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i + 1}/{len(tasks_to_delete)} tasks deleted")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error deleting task {task['id']}: {e}")
        
        logger.info(f"\n✅ Deletion completed!")
        logger.info(f"  - Successfully deleted: {deleted_count} tasks")
        logger.info(f"  - Errors: {error_count} tasks")
        logger.info(f"  - Total processed: {len(tasks_to_delete)} tasks")
        
    except Exception as e:
        logger.error(f"Deletion failed: {e}")
        raise

def main():
    """Main function with command line argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Delete old tasks without presented_at field')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Perform a dry run (default: True)')
    parser.add_argument('--live', action='store_true', 
                       help='Perform live deletion (overrides --dry-run)')
    parser.add_argument('--username', type=str,
                       help='Only delete tasks for this username')
    
    args = parser.parse_args()
    
    # Determine if this is a dry run
    dry_run = not args.live
    
    if dry_run:
        logger.info("🔍 Running in DRY RUN mode - no changes will be made")
    else:
        logger.info("🚀 Running in LIVE mode - changes will be made to database")
        response = input("Are you sure you want to delete old tasks? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Deletion cancelled by user")
            return
    
    delete_old_tasks(dry_run=dry_run, username=args.username)

if __name__ == '__main__':
    main()

