#!/usr/bin/env python3
"""
Standalone test script for AI task generation
Tests TaskGenerator without needing the full app or storing in Firestore
Now includes upload functionality to store generated tasks
"""
import os
import json
from dotenv import load_dotenv
from src.core.task_generator import TaskGenerator
from google.cloud import firestore
from datetime import datetime

# Load environment variables
load_dotenv()


def test_ai_task_generation_with_upload(username, category="Self", count=2, upload=False):
    """Test AI task generation with optional Firestore upload"""
    
    # Check if OpenAI API key is available
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ ERROR: OPENAI_API_KEY not found in environment variables")
        print("Please set OPENAI_API_KEY in your .env file")
        return False
    
    # Check Firestore credentials if uploading
    if upload:
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS') and not os.getenv('GOOGLE_CLOUD_PROJECT'):
            print("❌ ERROR: Firestore credentials not found for upload")
            print("Please set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_CLOUD_PROJECT")
            return False
    
    mode = "with Firestore upload" if upload else "simulation only"
    print(f"🧪 Testing AI Task Generation for {username} ({mode})")
    print("=" * 60)
    print(f"Username: {username}")
    print(f"Category: {category}")
    print(f"Count: {count}")
    print(f"Upload to Firestore: {'Yes' if upload else 'No'}")
    print()
    
    try:
        # Initialize TaskGenerator with database connection for goals
        # Initialize Firestore client for goals fetching (even in simulation mode)
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
        db = firestore.Client(project=project_id)
        generator = TaskGenerator(db)
        
        # Generate tasks using the new method (includes goals integration)
        ai_tasks = generator.generate_tasks_for_category(username, category, count, upload_to_firestore=upload)
        
        if ai_tasks:
            print(f"✅ Successfully generated {len(ai_tasks)} AI tasks for {username} in {category}:")
            print("-" * 50)
            
            for i, task in enumerate(ai_tasks, 1):
                print(f"{i}. {task['description']}")
                print(f"   Difficulty: {task['difficulty']}, Duration: {task['duration']}min, Category: {task['category']}")
                print()
            
            # Tasks are already uploaded to Firestore by generate_tasks_for_category
            if upload:
                print(f"\n📊 Upload Summary:")
                print(f"   Category: {category}")
                print(f"   Tasks uploaded: {len(ai_tasks)}")
                print(f"   User: {username}")
            else:
                print("ℹ️  Tasks were generated but not stored in Firestore - this was just a simulation.")
        else:
            print("❌ No tasks generated")
            return False
        
        print("✅ AI task generation test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error during AI task generation test: {e}")
        return False

def upload_json_tasks_file(username, json_file_path):
    """Upload tasks from a JSON file to Firestore"""
    try:
        # Read JSON file
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        if 'tasks' not in data or not isinstance(data['tasks'], list):
            print("❌ JSON file must contain a 'tasks' array")
            return False
        
        tasks = data['tasks']
        print(f"📁 Found {len(tasks)} tasks in {json_file_path}")
        
        # Initialize Firestore client
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
        db = firestore.Client(project=project_id)
        
        uploaded_count = 0
        
        for i, task in enumerate(tasks):
            try:
                # Validate task structure
                if not isinstance(task, dict) or 'description' not in task:
                    print(f"⚠️  Skipping task {i+1}: missing description")
                    continue
                
                # Create task data with defaults
                task_data = {
                    'username': username,
                    'description': task['description'].strip(),
                    'category': task.get('category', 'Self'),
                    'difficulty': task.get('difficulty', 3),
                    'duration': task.get('duration', 10),
                    'completed': False,
                    'saved': task.get('saved', False),
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }
                
                # Validate category
                valid_categories = ['Work', 'Kids', 'Spouse', 'House', 'Self']
                if task_data['category'] not in valid_categories:
                    print(f"⚠️  Skipping task {i+1}: invalid category '{task_data['category']}'")
                    continue
                
                # Add to Firestore
                doc_ref = db.collection('tasks').add(task_data)
                task_data['id'] = doc_ref[1].id
                uploaded_count += 1
                print(f"✅ Uploaded: {task_data['description']}")
                
            except Exception as e:
                print(f"❌ Error uploading task {i+1}: {e}")
                continue
        
        print(f"\n🎉 Successfully uploaded {uploaded_count} tasks from {json_file_path}")
        return uploaded_count > 0
        
    except FileNotFoundError:
        print(f"❌ File not found: {json_file_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def test_all_categories(username, upload=False):
    """Test AI task generation for all categories with optional upload"""
    
    categories = ["Work", "Kids", "Spouse", "House", "Self"]
    mode = "with Firestore upload" if upload else "simulation only"
    
    print(f"🧪 Testing AI Task Generation for All Categories - {username} ({mode})")
    print("=" * 60)
    
    total_uploaded = 0
    
    for category in categories:
        print(f"\n📂 Testing {category} category:")
        print("-" * 30)
        
        success = test_ai_task_generation_with_upload(username, category, count=1, upload=upload)
        if not success:
            print(f"❌ Failed to generate tasks for {category}")
            return False
        
        if upload:
            total_uploaded += 1
    
    if upload:
        print(f"\n🎉 All categories test completed! Uploaded {total_uploaded} tasks total.")
    else:
        print("\n✅ All categories test completed!")
    return True

if __name__ == "__main__":
    print("🧪 AI Task Generation Test Tool")
    print("=" * 40)
    print("Choose user:")
    print("1. Ian")
    print("2. Karleigh")
    
    user_choice = input("Enter choice (1 or 2): ").strip()
    
    if user_choice == "1":
        username = "Ian"
    elif user_choice == "2":
        username = "Karleigh"
    else:
        print("Invalid choice. Using Ian...")
        username = "Ian"
    
    print(f"\nSelected user: {username}")
    print("\nChoose test mode:")
    print("1. Test all categories (simulation only)")
    print("2. Test single category (simulation only)")
    print("3. Test all categories (with Firestore upload)")
    print("4. Test single category (with Firestore upload)")
    print("5. Upload tasks from JSON file")
    
    choice = input("Enter choice (1-5): ").strip()
    
    if choice == "1":
        test_all_categories(username, upload=False)
    elif choice == "2":
        print("\nChoose category:")
        print("1. Work")
        print("2. Kids") 
        print("3. Spouse")
        print("4. House")
        print("5. Self")
        
        cat_choice = input("Enter choice (1-5): ").strip()
        category_map = {"1": "Work", "2": "Kids", "3": "Spouse", "4": "House", "5": "Self"}
        category = category_map.get(cat_choice, "Self")
        
        count = input("Enter number of tasks to generate (default 2): ").strip()
        count = int(count) if count.isdigit() else 2
        
        test_ai_task_generation_with_upload(username, category, count, upload=False)
    elif choice == "3":
        print("\n⚠️  WARNING: This will upload tasks to Firestore!")
        confirm = input("Are you sure? (y/N): ").strip().lower()
        if confirm == 'y':
            test_all_categories(username, upload=True)
        else:
            print("Upload cancelled.")
    elif choice == "4":
        print("\nChoose category:")
        print("1. Work")
        print("2. Kids") 
        print("3. Spouse")
        print("4. House")
        print("5. Self")
        
        cat_choice = input("Enter choice (1-5): ").strip()
        category_map = {"1": "Work", "2": "Kids", "3": "Spouse", "4": "House", "5": "Self"}
        category = category_map.get(cat_choice, "Self")
        
        count = input("Enter number of tasks to generate (default 2): ").strip()
        count = int(count) if count.isdigit() else 2
        
        print(f"\n⚠️  WARNING: This will upload {count} {category} task(s) to Firestore!")
        confirm = input("Are you sure? (y/N): ").strip().lower()
        if confirm == 'y':
            test_ai_task_generation_with_upload(username, category, count, upload=True)
        else:
            print("Upload cancelled.")
    elif choice == "5":
        json_file = input("Enter path to JSON file: ").strip()
        if json_file:
            print(f"\n⚠️  WARNING: This will upload tasks from {json_file} to Firestore!")
            confirm = input("Are you sure? (y/N): ").strip().lower()
            if confirm == 'y':
                upload_json_tasks_file(username, json_file)
            else:
                print("Upload cancelled.")
        else:
            print("No file specified.")
    else:
        print("Invalid choice. Running all categories test (simulation only)...")
        test_all_categories(username, upload=False)
