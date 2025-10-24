#!/usr/bin/env python3
"""
Check Challenge Queue - Comprehensive health analysis of challenge system
"""
import sys
import os
from datetime import datetime, timedelta
import pytz

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from google.cloud import firestore
from google.cloud.firestore import FieldFilter


def check_challenge_queue(username=None):
    """Comprehensive health check of challenge queue and reward goal relationships"""
    
    # Initialize Firestore
    db = firestore.Client()
    local_tz = pytz.timezone('US/Central')
    current_time = datetime.now(local_tz)
    
    print("=" * 80)
    print(" CHALLENGE SYSTEM HEALTH DIAGNOSTIC")
    print("=" * 80)
    print(f"Current time: {current_time}")
    print(f"Username filter: {username if username else 'ALL USERS'}")
    print()
    
    # Get all reward goals
    print("1.  REWARD GOALS ANALYSIS")
    print("-" * 40)
    
    if username:
        goals_query = db.collection('reward_goals').where('username', '==', username)
    else:
        goals_query = db.collection('reward_goals')
    
    goals_docs = list(goals_query.stream())
    
    goals_by_status = {}
    goals_by_user = {}
    
    for goal_doc in goals_docs:
        goal_data = goal_doc.to_dict()
        status = goal_data.get('status', 'unknown')
        goal_username = goal_data.get('username', 'unknown')
        
        goals_by_status[status] = goals_by_status.get(status, 0) + 1
        goals_by_user[goal_username] = goals_by_user.get(goal_username, 0) + 1
    
    print(f"Total reward goals: {len(goals_docs)}")
    print("By status:")
    for status, count in goals_by_status.items():
        print(f"  {status}: {count}")
    
    print("By user:")
    for user, count in goals_by_user.items():
        print(f"  {user}: {count}")
    
    # Show active reward goals details
    active_goals = [doc for doc in goals_docs if doc.to_dict().get('status') == 'pending']
    print(f"\nActive (pending) reward goals: {len(active_goals)}")
    
    for goal_doc in active_goals[:5]:  # Show first 5
        goal_data = goal_doc.to_dict()
        created_at = goal_data.get('created_at')
        if created_at and hasattr(created_at, 'timestamp'):
            created_time = datetime.fromtimestamp(created_at.timestamp(), tz=local_tz)
            age_hours = (current_time - created_time).total_seconds() / 3600
        else:
            age_hours = "unknown"
        
        print(f"  Goal {goal_doc.id}: {goal_data.get('reward_description', 'No description')[:50]}... (age: {age_hours:.1f}h)")
    
    if len(active_goals) > 5:
        print(f"  ... and {len(active_goals) - 5} more")
    
    print()
    
    # Get all challenges (reward_tasks)
    print("2.  CHALLENGE QUEUE ANALYSIS")
    print("-" * 40)
    
    if username:
        challenges_query = db.collection('reward_tasks').where('username', '==', username)
    else:
        challenges_query = db.collection('reward_tasks')
    
    challenges_docs = list(challenges_query.stream())
    
    challenges_by_status = {}
    challenges_by_user = {}
    expired_challenges = []
    active_challenges = []
    challenges_by_goal = {}
    
    for challenge_doc in challenges_docs:
        challenge_data = challenge_doc.to_dict()
        status = challenge_data.get('status', 'unknown')
        challenge_username = challenge_data.get('username', 'unknown')
        goal_id = challenge_data.get('reward_goal_id', 'unknown')
        
        challenges_by_status[status] = challenges_by_status.get(status, 0) + 1
        challenges_by_user[challenge_username] = challenges_by_user.get(challenge_username, 0) + 1
        
        if status == 'pending':
            presented_at = challenge_data.get('presented_at')
            
            if presented_at is not None:
                # Challenge has been presented - check if expired (12 hours after being presented)
                if hasattr(presented_at, 'timestamp'):
                    presented_time = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                else:
                    presented_time = presented_at
                
                # Check if challenge is expired (12 hours after being presented)
                if current_time - presented_time >= timedelta(hours=12):
                    expired_challenges.append(challenge_doc)
                else:
                    active_challenges.append(challenge_doc)
                    if goal_id not in challenges_by_goal:
                        challenges_by_goal[goal_id] = []
                    challenges_by_goal[goal_id].append(challenge_doc)
            else:
                # Unpresented challenge - always active/available
                active_challenges.append(challenge_doc)
                if goal_id not in challenges_by_goal:
                    challenges_by_goal[goal_id] = []
                challenges_by_goal[goal_id].append(challenge_doc)
    
    print(f"Total challenges: {len(challenges_docs)}")
    print("By status:")
    for status, count in challenges_by_status.items():
        print(f"  {status}: {count}")
    
    print("By user:")
    for user, count in challenges_by_user.items():
        print(f"  {user}: {count}")
    
    print(f"\nActive (non-expired) challenges: {len(active_challenges)}")
    print(f"Expired challenges: {len(expired_challenges)}")
    
    # Show expired challenges details
    if expired_challenges:
        print("\nExpired challenges:")
        for challenge_doc in expired_challenges[:5]:
            challenge_data = challenge_doc.to_dict()
            presented_at = challenge_data.get('presented_at')
            
            if presented_at and hasattr(presented_at, 'timestamp'):
                presented_time = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                age_hours = (current_time - presented_time).total_seconds() / 3600
            else:
                age_hours = "unknown"
            
            print(f"  Challenge {challenge_doc.id}: {challenge_data.get('description', 'No description')[:50]}... (presented {age_hours:.1f}h ago, expired)")
        
        if len(expired_challenges) > 5:
            print(f"  ... and {len(expired_challenges) - 5} more")
    
    # Show active challenges details
    if active_challenges:
        print("\nActive challenges:")
        for challenge_doc in active_challenges[:5]:
            challenge_data = challenge_doc.to_dict()
            presented_at = challenge_data.get('presented_at')
            created_at = challenge_data.get('created_at')
            
            if created_at and hasattr(created_at, 'timestamp'):
                created_time = datetime.fromtimestamp(created_at.timestamp(), tz=local_tz)
                age = (current_time - created_time).total_seconds() / 3600
            else:
                age = "unknown"
            
            if presented_at and hasattr(presented_at, 'timestamp'):
                presented_time = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                time_since_presented = (current_time - presented_time).total_seconds() / 3600
                time_left = 12 - time_since_presented
                status = f"Presented {time_since_presented:.1f}h ago, expires in {time_left:.1f}h"
            else:
                status = "Unpresented (available)"
            
            print(f"  Challenge {challenge_doc.id}: {challenge_data.get('description', 'No description')[:50]}...")
            print(f"    Age: {age:.1f}h, Status: {status}, Goal: {challenge_data.get('reward_goal_id', 'unknown')}")
        
        if len(active_challenges) > 5:
            print(f"  ... and {len(active_challenges) - 5} more")
    
    print()
    
    # Analyze challenge-goal relationships
    print("3.  CHALLENGE-GOAL RELATIONSHIP ANALYSIS")
    print("-" * 40)
    
    print(f"Active goals with challenges: {len(challenges_by_goal)}")
    
    for goal_id, goal_challenges in challenges_by_goal.items():
        # Find the goal document
        goal_doc = next((doc for doc in active_goals if doc.id == goal_id), None)
        if goal_doc:
            goal_data = goal_doc.to_dict()
            goal_desc = goal_data.get('reward_description', 'No description')[:40]
        else:
            goal_desc = "GOAL NOT FOUND"
        
        print(f"  Goal {goal_id}: {goal_desc}...")
        print(f"    Active challenges: {len(goal_challenges)}")
        
        # Show challenge details for this goal
        for challenge_doc in goal_challenges[:2]:  # Show first 2 challenges per goal
            challenge_data = challenge_doc.to_dict()
            presented_at = challenge_data.get('presented_at')
            
            if presented_at and hasattr(presented_at, 'timestamp'):
                presented_time = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                time_since_presented = (current_time - presented_time).total_seconds() / 3600
                time_left = 12 - time_since_presented
                status = f"presented {time_since_presented:.1f}h ago, expires in {time_left:.1f}h"
            else:
                status = "unpresented (available)"
            
            print(f"      - {challenge_data.get('description', 'No description')[:60]}... ({status})")
        
        if len(goal_challenges) > 2:
            print(f"      ... and {len(goal_challenges) - 2} more")
        print()
    
    # Find goals without challenges
    active_goal_ids = {doc.id for doc in active_goals}
    goals_with_challenges = set(challenges_by_goal.keys())
    goals_without_challenges = active_goal_ids - goals_with_challenges
    
    if goals_without_challenges:
        print("Goals without active challenges:")
        for goal_id in goals_without_challenges:
            goal_doc = next((doc for doc in active_goals if doc.id == goal_id), None)
            if goal_doc:
                goal_data = goal_doc.to_dict()
                goal_desc = goal_data.get('reward_description', 'No description')[:50]
                print(f"  Goal {goal_id}: {goal_desc}...")
    
    print()
    
    # Health Analysis
    print("4. CHALLENGE SYSTEM HEALTH ANALYSIS")
    print("-" * 40)
    
    total_active_goals = len(active_goals)
    total_active_challenges = len(active_challenges)
    total_unpresented_challenges = len([c for c in active_challenges if c.to_dict().get('presented_at') is None])
    total_presented_challenges = len([c for c in active_challenges if c.to_dict().get('presented_at') is not None])
    min_unpresented_challenges_needed = total_active_goals * 2  # MIN_CHALLENGES_PER_GOAL = 2 (unpresented only)
    
    print(f" CHALLENGE INVENTORY:")
    print(f"   Active reward goals: {total_active_goals}")
    print(f"   Total active challenges: {total_active_challenges}")
    print(f"   - Unpresented (available): {total_unpresented_challenges}")
    print(f"   - Presented (expiring): {total_presented_challenges}")
    print(f"   Minimum unpresented challenges needed: {min_unpresented_challenges_needed}")
    print(f"   Unpresented challenge deficit: {max(0, min_unpresented_challenges_needed - total_unpresented_challenges)}")
    
    # Calculate health scores
    health_issues = []
    health_score = 100
    
    # Check unpresented challenge availability
    if total_unpresented_challenges < min_unpresented_challenges_needed:
        deficit = min_unpresented_challenges_needed - total_unpresented_challenges
        health_issues.append(f"Unpresented challenge deficit: {deficit} below minimum")
        health_score -= min(30, deficit * 10)
    
    # Check for expired challenges
    if expired_challenges:
        health_issues.append(f"{len(expired_challenges)} expired challenges not cleaned up")
        health_score -= min(25, len(expired_challenges) * 5)
    
    # Check for goals without challenges
    if goals_without_challenges:
        health_issues.append(f"{len(goals_without_challenges)} goals have no challenges")
        health_score -= min(20, len(goals_without_challenges) * 10)
    
    # Check for stale challenges (very old unpresented)
    stale_challenges = []
    for challenge_doc in active_challenges:
        challenge_data = challenge_doc.to_dict()
        if challenge_data.get('presented_at') is None:  # Unpresented
            created_at = challenge_data.get('created_at')
            if created_at and hasattr(created_at, 'timestamp'):
                created_time = datetime.fromtimestamp(created_at.timestamp(), tz=local_tz)
                age_hours = (current_time - created_time).total_seconds() / 3600
                if age_hours > 24:  # More than 24 hours old and still unpresented
                    stale_challenges.append((challenge_doc.id, age_hours))
    
    if stale_challenges:
        health_issues.append(f"{len(stale_challenges)} stale challenges (unpresented >24h)")
        health_score -= min(15, len(stale_challenges) * 3)
    
    # Check challenge distribution
    challenges_per_goal = {}
    for goal_id, goal_challenges in challenges_by_goal.items():
        challenges_per_goal[goal_id] = len(goal_challenges)
    
    if challenges_per_goal:
        min_per_goal = min(challenges_per_goal.values())
        max_per_goal = max(challenges_per_goal.values())
        if max_per_goal - min_per_goal > 2:  # Uneven distribution
            health_issues.append(f"Uneven challenge distribution: {min_per_goal}-{max_per_goal} per goal")
            health_score -= 10
    
    # Display health score and status
    print(f"\n SYSTEM HEALTH SCORE: {max(0, health_score)}/100")
    
    if health_score >= 90:
        print("   [SUCCESS] EXCELLENT - System is healthy and functioning optimally")
    elif health_score >= 75:
        print("   🟡 GOOD - System is mostly healthy with minor issues")
    elif health_score >= 50:
        print("   🟠 WARNING - System has several issues that need attention")
    else:
        print("   🔴 CRITICAL - System has serious issues requiring immediate action")
    
    # Display health issues
    if health_issues:
        print(f"\n  HEALTH ISSUES DETECTED:")
        for i, issue in enumerate(health_issues, 1):
            print(f"   {i}. {issue}")
    else:
        print(f"\n[SUCCESS] No health issues detected - system is running smoothly!")
    
    # Recommendations
    print(f"\n RECOMMENDATIONS:")
    if total_unpresented_challenges < min_unpresented_challenges_needed:
        print(f"   • Generate {min_unpresented_challenges_needed - total_unpresented_challenges} more unpresented challenges")
    if expired_challenges:
        print(f"   • Clean up {len(expired_challenges)} expired challenges")
    if goals_without_challenges:
        print(f"   • Generate challenges for {len(goals_without_challenges)} goals without challenges")
    if stale_challenges:
        print(f"   • Investigate {len(stale_challenges)} stale challenges (may indicate generation issues)")
    if not health_issues:
        print(f"   • System is healthy - no action needed")
    
    # Detailed stale challenge analysis
    if stale_challenges:
        print(f"\n STALE CHALLENGE DETAILS:")
        for challenge_id, age_hours in stale_challenges[:5]:  # Show first 5
            print(f"   Challenge {challenge_id}: unpresented for {age_hours:.1f} hours")
        if len(stale_challenges) > 5:
            print(f"   ... and {len(stale_challenges) - 5} more")
    
    print("\n" + "=" * 80)


def quick_health_check(username=None):
    """Quick health check - just the essential metrics"""
    db = firestore.Client()
    local_tz = pytz.timezone('US/Central')
    current_time = datetime.now(local_tz)
    
    # Get active goals
    if username:
        goals_query = db.collection('reward_goals').where('username', '==', username)
    else:
        goals_query = db.collection('reward_goals')
    goals_docs = list(goals_query.stream())
    active_goals = [doc for doc in goals_docs if doc.to_dict().get('status') == 'pending']
    
    # Get active challenges
    if username:
        challenges_query = db.collection('reward_tasks').where('username', '==', username)
    else:
        challenges_query = db.collection('reward_tasks')
    challenges_docs = list(challenges_query.stream())
    
    active_challenges = 0
    expired_challenges = 0
    unpresented_challenges = 0
    
    for challenge_doc in challenges_docs:
        challenge_data = challenge_doc.to_dict()
        if challenge_data.get('status') == 'pending':
            presented_at = challenge_data.get('presented_at')
            
            if presented_at is not None:
                if hasattr(presented_at, 'timestamp'):
                    presented_time = datetime.fromtimestamp(presented_at.timestamp(), tz=local_tz)
                else:
                    presented_time = presented_at
                
                if current_time - presented_time < timedelta(hours=12):
                    active_challenges += 1
                else:
                    expired_challenges += 1
            else:
                unpresented_challenges += 1
                active_challenges += 1
    
    min_unpresented_needed = len(active_goals) * 2
    health_score = 100
    
    if unpresented_challenges < min_unpresented_needed:
        health_score -= min(30, (min_unpresented_needed - unpresented_challenges) * 10)
    if expired_challenges > 0:
        health_score -= min(25, expired_challenges * 5)
    
    print(f" Challenge Health: {health_score}/100")
    print(f"   Goals: {len(active_goals)} | Total: {active_challenges} | Unpresented: {unpresented_challenges}/{min_unpresented_needed} | Expired: {expired_challenges}")
    
    if health_score >= 90:
        print("   [SUCCESS] HEALTHY")
    elif health_score >= 75:
        print("   🟡 GOOD")
    elif health_score >= 50:
        print("   🟠 WARNING")
    else:
        print("   🔴 CRITICAL")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Check challenge queue status and health")
    parser.add_argument("--username", help="Filter by specific username")
    parser.add_argument("--quick", action="store_true", help="Show quick health check only")
    
    args = parser.parse_args()
    
    try:
        if args.quick:
            quick_health_check(args.username)
        else:
            check_challenge_queue(args.username)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
