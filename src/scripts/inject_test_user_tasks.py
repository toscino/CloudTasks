#!/usr/bin/env python3
"""
Script to inject AI-generated tasks for test_user into the database
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import the core modules
from google.cloud import firestore
from src.core.task_generator import TaskGenerator
from src.utils.logger import logger

def inject_tasks_for_test_user():
    """Inject AI-generated tasks for test_user"""
    print("=" * 60)
    print("INJECTING AI TASKS FOR TEST_USER")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    print()
    
    # Check if OpenAI API key is available
    if not os.getenv('OPENAI_API_KEY'):
        print("ERROR: OPENAI_API_KEY not found in environment variables")
        print("Please set OPENAI_API_KEY in your .env file")
        return False
    
    # Initialize Firestore client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
    db = firestore.Client(project=project_id)
    print(f"Connected to Firestore project: {project_id}")
    
    # Initialize TaskGenerator
    task_generator = TaskGenerator(db, cheapmode=False)
    
    # Test user
    test_user = "test_user"
    print(f"Generating tasks for user: {test_user}")
    print()
    
    # Define categories and number of tasks per category
    categories = ["Work", "Kids", "Spouse", "House", "Self"]
    tasks_per_category = 3  # Generate 3 tasks per category
    
    total_tasks_created = 0
    
    for category in categories:
        print(f"Generating {tasks_per_category} tasks for {category} category:")
        print("-" * 40)
        
        try:
            # Generate tasks for this category
            generated_tasks = task_generator.generate_tasks_for_category(
                username=test_user,
                category=category,
                count=tasks_per_category,
                upload_to_firestore=True
            )
            
            if generated_tasks:
                print(f"Successfully generated {len(generated_tasks)} {category} tasks:")
                for i, task in enumerate(generated_tasks, 1):
                    print(f"   {i}. {task['description']}")
                    print(f"      Difficulty: {task['difficulty']}, Duration: {task['duration']}min")
                total_tasks_created += len(generated_tasks)
            else:
                print(f"Failed to generate tasks for {category}")
                
        except Exception as e:
            print(f"Error generating {category} tasks: {e}")
            logger.error(f"Error generating {category} tasks for {test_user}: {e}")
        
        print()
    
    print("=" * 60)
    print("INJECTION SUMMARY")
    print("=" * 60)
    print(f"Total tasks created: {total_tasks_created}")
    print(f"User: {test_user}")
    print(f"Categories: {', '.join(categories)}")
    print(f"Tasks per category: {tasks_per_category}")
    print(f"Completed at: {datetime.now()}")
    
    if total_tasks_created > 0:
        print("\nTask injection completed successfully!")
        print(f"{total_tasks_created} AI-generated tasks have been added to the database for {test_user}")
    else:
        print("\nNo tasks were created. Check the logs for errors.")
        return False
    
    return True

def verify_tasks_in_database():
    """Verify that tasks were created for test_user"""
    print("\n" + "=" * 60)
    print("VERIFYING TASKS IN DATABASE")
    print("=" * 60)
    
    try:
        # Initialize Firestore client
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
        db = firestore.Client(project=project_id)
        
        # Query tasks for test_user
        tasks_query = db.collection('tasks').where('username', '==', 'test_user')
        tasks_docs = tasks_query.stream()
        
        tasks = []
        for doc in tasks_docs:
            task_data = doc.to_dict()
            task_data['id'] = doc.id
            tasks.append(task_data)
        
        print(f"Found {len(tasks)} tasks for test_user")
        
        if tasks:
            # Group by category
            by_category = {}
            for task in tasks:
                category = task.get('category', 'Unknown')
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(task)
            
            print("\nTasks by category:")
            for category, category_tasks in by_category.items():
                print(f"  {category}: {len(category_tasks)} tasks")
                for task in category_tasks:
                    completed_status = "DONE" if task.get('completed', False) else "PENDING"
                    print(f"    {completed_status} {task.get('description', 'No description')}")
                    print(f"       Difficulty: {task.get('difficulty', 'N/A')}, Duration: {task.get('duration', 'N/A')}min")
        else:
            print("No tasks found for test_user")
            
    except Exception as e:
        print(f"Error verifying tasks: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("AI Task Injection Tool for test_user")
    print("=" * 40)
    
    # Inject tasks
    success = inject_tasks_for_test_user()
    
    if success:
        # Verify tasks were created
        verify_tasks_in_database()
    else:
        print("\nTask injection failed. Please check the error messages above.")
