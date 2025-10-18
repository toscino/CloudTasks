#!/usr/bin/env python3
"""
Test script to generate 10 rewards and 10 challenges based on those rewards.
Uses high-level services from the CloudTasks application.
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
from src.core.reward_generator import RewardGenerator
from src.core.task_generator import TaskGenerator
from src.utils.logger import logger

def main():
    """Main function to generate rewards and challenges"""
    print("=" * 60)
    print("REWARD AND CHALLENGE GENERATION TEST")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    print()
    
    # Initialize Firestore client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
    db = firestore.Client(project=project_id)
    print(f"Connected to Firestore project: {project_id}")
    
    # Initialize generators
    reward_generator = RewardGenerator(db, cheapmode=False)  # Use cheaper model for testing
    task_generator = TaskGenerator(db, cheapmode=False)      # Use cheaper model for testing
    
    # Test user (you can change this)
    test_user = "Ian"
    print(f"Generating for user: {test_user}")
    print()
    
    # Step 1: Generate 10 rewards
    print("STEP 1: GENERATING 10 REWARDS")
    print("-" * 40)
    
    try:
        rewards = reward_generator.generate_reward_options_for_user(
            username=test_user,
            context="Testing reward generation for challenge creation",
            count=10,
            upload_to_firestore=False  # Don't save to database, just generate
        )
        
        print(f"✅ Successfully generated {len(rewards)} rewards")
        print()
        
        # Display the generated rewards
        for i, reward in enumerate(rewards, 1):
            print(f"Reward {i}:")
            print(f"  Description: {reward['description']}")
            print(f"  Themes: {', '.join(reward['themes'])}")
            print(f"  Display: {reward['display']}")
            print()
            
    except Exception as e:
        print(f"❌ Error generating rewards: {e}")
        return
    
    # Step 2: Generate 10 challenges based on the rewards
    print("STEP 2: GENERATING 10 CHALLENGES BASED ON REWARDS")
    print("-" * 50)
    
    try:
        # Create task inputs based on the generated rewards
        task_inputs = []
        for i, reward in enumerate(rewards[:10]):  # Use first 10 rewards
            # Create a challenge task input based on the reward
            task_input = {
                "target": "Spouse",  # Challenges are for the spouse to complete
                "difficulty": (i % 10) + 1,  # Vary difficulty from 1-10
                "base_idea": reward['description'],
                "type": "reward",  # Mark as reward type
                "themes": reward['themes'],
                "ID": f"reward_{i+1}"  # Track which reward this challenge is based on
            }
            task_inputs.append(task_input)
        
        # Set the user for task generation
        task_generator.user = "Karleigh"
        
        # Generate challenges using AI
        challenges = task_generator.generate_tasks(
            context="Generate challenging tasks based on these reward ideas",
            tasks=task_inputs,
            user="Karleigh"
        )
        
        print(f"✅ Successfully generated {len(challenges)} challenges")
        print()
        
        # Display the generated challenges
        for i, challenge in enumerate(challenges, 1):
            print(f"Challenge {i} (ID: {challenge.get('ID', 'N/A')}, based on reward: '{rewards[i-1]['description'][:50]}...'):")
            print(f"  Description: {challenge['description']}")
            print(f"  Target: {challenge['target']}")
            print(f"  Difficulty: {challenge['difficulty']}")
            print(f"  Duration: {challenge['duration']} minutes")
            print()
            
    except Exception as e:
        print(f"❌ Error generating challenges: {e}")
        return
    
    # Summary
    print("=" * 60)
    print("GENERATION SUMMARY")
    print("=" * 60)
    print(f"✅ Generated {len(rewards)} rewards")
    print(f"✅ Generated {len(challenges)} challenges")
    print(f"Completed at: {datetime.now()}")
    print()
    print("Note: Rewards and challenges were generated in simulation mode")
    print("(not saved to the database)")
    
    # Show the relationship between rewards and challenges
    print("\nREWARD-TO-CHALLENGE MAPPING:")
    print("-" * 30)
    for i in range(min(len(rewards), len(challenges))):
        reward_desc = rewards[i]['description'][:40] + "..." if len(rewards[i]['description']) > 40 else rewards[i]['description']
        challenge_desc = challenges[i]['description'][:40] + "..." if len(challenges[i]['description']) > 40 else challenges[i]['description']
        print(f"{i+1:2d}. Reward: {reward_desc}")
        print(f"    Challenge: {challenge_desc}")
        print()

if __name__ == "__main__":
    main()
