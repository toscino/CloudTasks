#!/usr/bin/env python3
"""
Migration script to standardize presented_at field in all tasks.

This script adds presented_at: null to all tasks that don't have this field,
ensuring consistent database filtering for unpresented tasks.
"""

import os
import sys
import logging
from datetime import datetime
from google.cloud import firestore

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_presented_at_field(dry_run=True, limit=None):
    """
    Add presented_at: null to tasks that don't have this field.
    
    Args:
        dry_run (bool): If True, only count tasks that would be updated
        limit (int): Limit number of tasks to process (for testing)
    """
    try:
        # Initialize Firestore client
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'cloudtasks-app-473120')
        db = firestore.Client(project=project_id)
        
        logger.info(f"Starting presented_at standardization {'(DRY RUN)' if dry_run else '(LIVE RUN)'}")
        logger.info(f"Project: {project_id}")
        
        # Get all tasks
        tasks_ref = db.collection('tasks')
        tasks_query = tasks_ref.limit(limit) if limit else tasks_ref
        
        tasks_to_update = []
        total_tasks = 0
        
        # Scan all tasks
        for doc in tasks_query.stream():
            total_tasks += 1
            task_data = doc.to_dict()
            
            # Check if presented_at field is missing
            if 'presented_at' not in task_data:
                tasks_to_update.append({
                    'id': doc.id,
                    'username': task_data.get('username', 'unknown'),
                    'description': task_data.get('description', 'No description')[:50]
                })
        
        logger.info(f"Scanned {total_tasks} total tasks")
        logger.info(f"Found {len(tasks_to_update)} tasks missing presented_at field")
        
        if not tasks_to_update:
            logger.info("[SUCCESS] All tasks already have presented_at field!")
            return
        
        # Show sample of tasks to be updated
        logger.info("\n Sample tasks to be updated:")
        for i, task in enumerate(tasks_to_update[:10]):
            logger.info(f"  {i+1}. {task['username']}: {task['description']}... (ID: {task['id'][:8]}...)")
        
        if len(tasks_to_update) > 10:
            logger.info(f"  ... and {len(tasks_to_update) - 10} more tasks")
        
        if dry_run:
            logger.info(f"\n DRY RUN: Would update {len(tasks_to_update)} tasks")
            logger.info("Run with dry_run=False to perform actual migration")
            return
        
        # Perform the migration
        logger.info(f"\n🚀 Starting migration of {len(tasks_to_update)} tasks...")
        updated_count = 0
        error_count = 0
        
        for i, task in enumerate(tasks_to_update):
            try:
                doc_ref = db.collection('tasks').document(task['id'])
                doc_ref.update({
                    'presented_at': None,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                updated_count += 1
                
                if (i + 1) % 50 == 0:
                    logger.info(f"Progress: {i + 1}/{len(tasks_to_update)} tasks updated")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error updating task {task['id']}: {e}")
        
        logger.info(f"\n[SUCCESS] Migration completed!")
        logger.info(f"  - Successfully updated: {updated_count} tasks")
        logger.info(f"  - Errors: {error_count} tasks")
        logger.info(f"  - Total processed: {len(tasks_to_update)} tasks")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

def main():
    """Main function with command line argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Standardize presented_at field in tasks')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Perform a dry run (default: True)')
    parser.add_argument('--live', action='store_true', 
                       help='Perform live migration (overrides --dry-run)')
    parser.add_argument('--limit', type=int,
                       help='Limit number of tasks to process (for testing)')
    
    args = parser.parse_args()
    
    # Determine if this is a dry run
    dry_run = not args.live
    
    if dry_run:
        logger.info(" Running in DRY RUN mode - no changes will be made")
    else:
        logger.info("🚀 Running in LIVE mode - changes will be made to database")
        response = input("Are you sure you want to modify the database? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Migration cancelled by user")
            return
    
    migrate_presented_at_field(dry_run=dry_run, limit=args.limit)

if __name__ == '__main__':
    main()
