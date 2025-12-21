import os
from flask import render_template, session
from flask_cors import CORS
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from flask_base import FlaskApp
from src.core.task_master import TaskMaster
from src.auth.auth_service import get_user_info, get_auth_status
from src.utils.error_handlers import ratelimit_handler, with_error_handling
from src.services.task_service import TaskService
from src.services.goal_service import GoalService
from src.services.statistics_service import StatisticsService
from src.services.daily_task_service import DailyTaskService
from src.services.collaboration_service import CollaborationService
from src.services.morning_card_service import MorningCardService
from src.services.user_service import UserService
from src.utils.config import get_timezone

# Load environment variables
load_dotenv()

# TODO: PERFORMANCE OPTIMIZATION
# Currently using client-side filtering for flexible testing
# Future: Create Firestore composite indexes and switch to direct queries
# See README.md "Performance Optimization Notes" section for details

# Initialize FlaskApp from flask_base (module level for flask_base compatibility)
app_manager = FlaskApp(app_name="CloudTasks", demo_user="test_user")
app_manager.limiter.default_limits = ["1000 per hour", "100 per minute"]
app = app_manager.app

# Enable CORS for all routes (flask_base doesn't include CORS)
CORS(app)


# Initialize Services
db = app_manager.db
task_master = TaskMaster(db)
task_service = TaskService(app_manager, task_master)
goal_service = GoalService(app_manager)
statistics_service = StatisticsService(app_manager, task_master)
daily_task_service = DailyTaskService(app_manager)
collaboration_service = CollaborationService(app_manager)
morning_card_service = MorningCardService(app_manager)
user_service = UserService(app_manager)

# Store services on app_manager for easy access
app_manager.collaboration_service = collaboration_service
app_manager.user_service = user_service

# Error handler for rate limit exceeded
@app.errorhandler(429)
def handle_ratelimit(e):
    return ratelimit_handler(e)

# Page routes
app_manager.page("tasks.html", root=True)
app_manager.page("test.html")
app_manager.page("settings.html")
app_manager.page("goals.html")
app_manager.page("daily_tasks.html")
app_manager.page("rewards_owed.html")
app_manager.page("morning_cards.html")

@app_manager.route('/morning-cards/manage')
def morning_cards_manage_page():
    """Morning cards management page"""
    return render_template('morning_cards_manage.html')

@app_manager.route('/simple-test')
def simple_test():
    """Simple test endpoint without authentication"""
    app_manager.logger.info("Simple test endpoint called")
    return "Simple test works!"

# Auth routes (flask_base handles authentication via ?key= parameter)
@app_manager.route('/api/user', ['GET'], limit="50 per minute")
def get_current_user():
    """Get current authenticated user information"""
    try:
        is_authenticated, username = get_auth_status(app_manager)
        return app_manager.jsonify({
            'status': 'success',
            'username': username,
            'authenticated': is_authenticated
        })
    except Exception as e:
        return app_manager.jsonify({
            'status': 'error',
            'message': f'Failed to get user info: {str(e)}'
        }), 500


# Task Management Routes
@app_manager.route('/api/tasks', ['GET'], limit="50 per minute")
@with_error_handling
def get_tasks():
    """Get active task session (4 tasks) for current user"""
    username = get_user_info(app_manager)
    result = task_service.get_tasks(username)
    app_manager.logger.info(f"GET /api/tasks: {200 if result['status'] == 'success' else 500} - Returned {len(result.get('tasks', []))} tasks", extra={'username': username})
    return result
    
@app_manager.route('/api/tasks/statistics', ['GET'], limit="20 per minute")
@with_error_handling
def get_task_statistics():
    """Get task statistics including counts by category"""
    username = get_user_info(app_manager)
    result = task_service.get_task_statistics(username)
    app_manager.logger.info(f"GET /api/tasks/statistics: {200 if result['status'] == 'success' else 500}", extra={'username': username})
    return result

@app_manager.route('/api/tasks', ['POST'], limit="20 per minute")
@with_error_handling
def create_task():
    """Create a new task"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    result = task_service.create_task(data, username)
    status_code = 200
    if 'error' in result:
        status_code = 400
    elif result['status'] == 'error':
        status_code = 500
    app_manager.logger.info(f"POST /api/tasks: {status_code} - Created task: {data.get('description', 'Unknown')[:50]}...", extra={'username': username})
    return result

@app_manager.route('/api/tasks/<task_id>/complete', ['PUT'], limit="30 per minute")
@with_error_handling
def complete_task(task_id):
    """Mark a task as completed and refresh the task session"""
    username = get_user_info(app_manager)
    result = task_service.complete_task(task_id, username)
    status_code = 200
    if result['status'] == 'error':
        status_code = 500
        if 'not found' in result['message'].lower():
            status_code = 404
        elif 'unauthorized' in result['message'].lower():
            status_code = 403
    app_manager.logger.info(f"PUT /api/tasks/complete: {status_code} - Completed task {task_id}", extra={'username': username})
    return result

@app_manager.route('/api/tasks/<task_id>/save', ['PUT'], limit="30 per minute")
@with_error_handling
def save_task(task_id):
    """Toggle save status for a task"""
    username = get_user_info(app_manager)
    result = task_service.save_task(task_id, username)
    return result

@app_manager.route('/api/tasks/<task_id>/abandon', ['PUT'], limit="20 per minute")
@with_error_handling
def abandon_task(task_id):
    """Abandon a task instance"""
    username = get_user_info(app_manager)
    return daily_task_service.abandon_daily_task(task_id, username)

# Goals Management Routes
@app_manager.route('/api/goals', ['GET'], limit="50 per minute")
@with_error_handling
def get_goals():
    """Get all goals for current user organized by category"""
    username = get_user_info(app_manager)
    return goal_service.get_goals(username)

@app_manager.route('/api/goals', ['POST'], limit="20 per minute")
@with_error_handling
def create_goal():
    """Create a new goal"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    return goal_service.create_goal(data, username)

@app_manager.route('/api/goals/<goal_id>', ['PUT'], limit="30 per minute")
@with_error_handling
def update_goal(goal_id):
    """Update an existing goal"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    return goal_service.update_goal(goal_id, data, username)

@app_manager.route('/api/goals/<goal_id>', ['DELETE'], limit="30 per minute")
@with_error_handling
def delete_goal(goal_id):
    """Delete a goal"""
    username = get_user_info(app_manager)
    return goal_service.delete_goal(goal_id, username)

@app_manager.route('/api/goals/categories', ['GET'], limit="50 per minute")
@with_error_handling
def get_categories():
    """Get available goal categories"""
    return goal_service.get_categories()

@app_manager.route('/api/reward-goals/test', ['GET'])
def test_reward_goals():
    """Test endpoint to check if reward goals API is reachable"""
    return app_manager.jsonify({
        'status': 'success',
        'message': 'Reward goals API is working',
        'timestamp': datetime.now().isoformat()
    })

# Daily Tasks API Routes
@app_manager.route('/api/daily-tasks', ['GET'], limit="50 per minute")
@with_error_handling
def get_daily_tasks():
    """Get all daily task templates for current user"""
    username = get_user_info(app_manager)
    return daily_task_service.get_daily_tasks(username)

@app_manager.route('/api/daily-tasks', ['POST'], limit="20 per minute")
@with_error_handling
def create_daily_task():
    """Create a new daily task template"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    return daily_task_service.create_daily_task(data, username)

@app_manager.route('/api/daily-tasks/<task_id>', ['PUT'], limit="20 per minute")
@with_error_handling
def update_daily_task(task_id):
    """Update an existing daily task template"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    return daily_task_service.update_daily_task(task_id, data, username)

@app_manager.route('/api/daily-tasks/<task_id>', ['DELETE'], limit="20 per minute")
@with_error_handling
def delete_daily_task(task_id):
    """Delete a daily task template"""
    username = get_user_info(app_manager)
    return daily_task_service.delete_daily_task(task_id, username)

@app_manager.route('/api/daily-tasks/today', ['GET'], limit="50 per minute")
@with_error_handling
def get_todays_daily_tasks():
    """Get today's daily task instances"""
    username = get_user_info(app_manager)
    return daily_task_service.get_todays_instances(username)

@app_manager.route('/api/daily-tasks/today/<instance_id>/complete', ['PUT'], limit="20 per minute")
@with_error_handling
def complete_daily_task(instance_id):
    """Complete a daily task instance"""
    username = get_user_info(app_manager)
    return daily_task_service.complete_daily_task(instance_id, username)

@app_manager.route('/api/daily-tasks/today/<instance_id>/abandon', ['PUT'], limit="20 per minute")
@with_error_handling
def abandon_daily_task(instance_id):
    """Abandon a daily task instance"""
    username = get_user_info(app_manager)
    return daily_task_service.abandon_daily_task(instance_id, username)

@app_manager.route('/api/daily-tasks/reset', ['POST'], limit="5 per minute")
def reset_daily_tasks():
    """Reset daily tasks (for testing) - deletes today's instances and recreates them"""
    username = get_user_info(app_manager)
    today_central = datetime.now(pytz.timezone('America/Chicago')).date()
    instances_query = db.collection('daily_task_instances').where(
        filter=FieldFilter('username', '==', username)
    ).where(filter=FieldFilter('date', '==', today_central.isoformat()))
    
    deleted_count = 0
    for instance in instances_query.stream():
        instance.reference.delete()
        deleted_count += 1
    
    reset_query = db.collection('daily_task_resets').where(
        filter=FieldFilter('username', '==', username)
    ).where(filter=FieldFilter('last_reset_date', '==', today_central.isoformat()))
    for reset_doc in reset_query.stream():
        reset_doc.reference.delete()
    
    result = daily_task_service.check_and_reset_daily_tasks(username)
    return app_manager.jsonify({
        'status': 'success',
        'message': f'Daily tasks reset successfully - deleted {deleted_count} instances',
        'result': result
    })

# Collaboration Routes
@app_manager.route('/api/collaboration/tracker', ['GET'], limit="50 per minute")
@with_error_handling
def get_collaboration_tracker():
    """Get current tracker value and user's goals"""
    username = get_user_info(app_manager)
    return collaboration_service.get_tracker_display(username)

@app_manager.route('/api/collaboration/todays-points', ['GET'], limit="50 per minute")
@with_error_handling
def get_todays_points():
    """Get today's total points for current user"""
    username = get_user_info(app_manager)
    return collaboration_service.get_todays_total_points(username)

@app_manager.route('/api/collaboration/history', ['GET'], limit="20 per minute")
def get_collaboration_history():
    """Get last 7 days of tracker history"""
    username = get_user_info(app_manager)
    today = datetime.now(tz=get_timezone()).date()
    seven_days_ago = today - timedelta(days=7)
    
    history_query = db.collection('tracker_history').where(
        'date', '>=', seven_days_ago.isoformat()
    ).order_by('date', direction=firestore.Query.DESCENDING)
    
    history = []
    for doc in history_query.stream():
        data = doc.to_dict()
        history.append({
            'date': data['date'],
            'ian_points': data['user_points'],
            'karleigh_points': data['spouse_points'],
            'ian_adjustment': data['user_adjustment'],
            'karleigh_adjustment': data['spouse_adjustment'],
            'old_tracker': data['old_value'],
            'new_tracker': data['new_value']
        })
    
    return app_manager.jsonify({'status': 'success', 'history': history})

@app_manager.route('/api/collaboration/history/all', ['GET'], limit="20 per minute")
@with_error_handling
def get_all_collaboration_history():
    """Get all tracker history records with test status for debugging"""
    username = get_user_info(app_manager)
    history_query = db.collection('tracker_history').order_by('date', direction=firestore.Query.DESCENDING).limit(500)
    
    history = []
    for doc in history_query.stream():
        data = doc.to_dict()
        history.append({
            'date': data['date'],
            'is_test': data.get('is_test', False),
            'user_points': data.get('user_points', 0),
            'spouse_points': data.get('spouse_points', 0),
            'user_adjustment': data.get('user_adjustment', 0),
            'spouse_adjustment': data.get('spouse_adjustment', 0),
            'old_tracker': data.get('old_value', 0),
            'new_tracker': data.get('new_value', 0)
        })
    
    return app_manager.jsonify({'status': 'success', 'history': history, 'count': len(history)})

@app_manager.route('/api/collaboration/reset-history', ['POST'], limit="5 per minute")
@with_error_handling
def reset_tracker_history():
    """Reset tracker history for testing"""
    username = get_user_info(app_manager)
    return collaboration_service.reset_tracker_history()

@app_manager.route('/api/collaboration/tracker-at-2am', ['GET'], limit="20 per minute")
@with_error_handling
def get_tracker_at_2am():
    """Get the collaboration tracker value at 2am reset time"""
    username = get_user_info(app_manager)
    return collaboration_service.get_tracker_at_2am()

@app_manager.route('/api/collaboration/progress-day', ['POST'], limit="5 per minute")
@with_error_handling
def progress_day_testing():
    """Manually trigger daily reset for testing"""
    username = get_user_info(app_manager)
    result = daily_task_service.check_and_reset_daily_tasks(username)
    return result

# Rewards Owed Routes
@app_manager.route('/api/rewards-owed', ['GET'], limit="50 per minute")
@with_error_handling
def get_rewards_owed():
    """Get pending rewards owed for current user"""
    username = get_user_info(app_manager)
    return goal_service.get_rewards_owed(username)

@app_manager.route('/api/rewards-owed/<goal_id>/complete', ['POST'], limit="10 per minute")
@with_error_handling
def complete_reward_owed(goal_id):
    """Complete a reward owed"""
    username = get_user_info(app_manager)
    return goal_service.complete_reward_owed(goal_id, username)

# Morning Card API Routes
@app_manager.route('/api/morning-cards', ['GET'], limit="50 per minute")
@with_error_handling
def get_morning_cards():
    """Get all morning card templates for current user"""
    username = get_user_info(app_manager)
    return morning_card_service.get_card_templates(username)

@app_manager.route('/api/morning-cards', ['POST'], limit="20 per minute")
@with_error_handling
def create_morning_card():
    """Create a new morning card template"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    data['username'] = username
    return morning_card_service.create_card_template(data)

@app_manager.route('/api/morning-cards/<card_id>', ['PUT'], limit="20 per minute")
@with_error_handling
def update_morning_card(card_id):
    """Update an existing morning card template"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    return morning_card_service.update_card_template(card_id, data, username)

@app_manager.route('/api/morning-cards/<card_id>', ['DELETE'], limit="20 per minute")
@with_error_handling
def delete_morning_card(card_id):
    """Delete a morning card template"""
    username = get_user_info(app_manager)
    return morning_card_service.delete_card_template(card_id, username)

@app_manager.route('/api/morning-cards/today', ['GET'], limit="50 per minute")
@with_error_handling
def get_todays_morning_cards():
    """Get today's morning card selection"""
    return morning_card_service.get_todays_selection()

@app_manager.route('/api/morning-cards/today/select', ['POST'], limit="10 per minute")
@with_error_handling
def select_morning_cards():
    """Lock in card selection (Karleigh only)"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    if not data or 'card_ids' not in data:
        return app_manager.jsonify({
            'status': 'error',
            'message': 'Card IDs are required'
        }), 400
    return morning_card_service.select_cards(data['card_ids'], username)

@app_manager.route('/api/morning-cards/today/unlock', ['POST'], limit="10 per minute")
@with_error_handling
def unlock_morning_cards():
    """Unlock today's card selection for testing"""
    return morning_card_service.unlock_todays_selection()

# User Settings API Endpoints
@app_manager.route('/api/user/settings', ['GET'], limit="50 per minute")
@with_error_handling
def get_user_settings():
    """Get current user settings"""
    username = get_user_info(app_manager)
    result = user_service.get_user_settings(username)
    return app_manager.jsonify({'status': 'success', 'settings': result if isinstance(result, dict) else {}})

@app_manager.route('/api/user/generate-pairing-code', ['POST'], limit="10 per minute")
@with_error_handling
def generate_pairing_code_endpoint():
    """Generate pairing code for spouse linking"""
    username = get_user_info(app_manager)
    result = user_service.generate_pairing_code(username)
    return app_manager.jsonify(result), 200 if result['status'] == 'success' else 400

@app_manager.route('/api/user/link-with-code', ['POST'], limit="10 per minute")
@with_error_handling
def link_with_code_endpoint():
    """Link spouses using pairing code"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    code = data.get('code', '').strip().upper()
    if not code:
        return app_manager.jsonify({'status': 'error', 'message': 'Code is required'}), 400
    result = user_service.link_with_pairing_code(username, code)
    return app_manager.jsonify(result), 200 if result['status'] == 'success' else 400

@app_manager.route('/api/user/spouse', ['DELETE'], limit="10 per minute")
@with_error_handling
def unlink_spouse_endpoint():
    """Unlink spouse"""
    username = get_user_info(app_manager)
    result = user_service.remove_spouse(username)
    return app_manager.jsonify(result), 200 if result['status'] == 'success' else 400

@app_manager.route('/api/user/preferences', ['POST'], limit="20 per minute")
@with_error_handling
def update_preferences_endpoint():
    """Update user preferences"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    result = user_service.update_preferences(username, data)
    return app_manager.jsonify(result), 200 if result['status'] == 'success' else 400

# Debug routes
@app_manager.route('/api/test', ['GET'])
def test_firestore():
    """Test Firestore connection"""
    try:
        doc_ref = db.collection('test').document('connection')
        doc = doc_ref.get()
        if doc.exists:
            return app_manager.jsonify({
                'status': 'success',
                'message': 'Firestore connection successful',
                'data': doc.to_dict()
            })
        else:
            doc_ref.set({
                'message': 'Hello from Firestore!',
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            return app_manager.jsonify({
                'status': 'success',
                'message': 'Test document created in Firestore'
            })
    except Exception as e:
        return app_manager.jsonify({
            'status': 'error',
            'message': f'Firestore connection failed: {str(e)}'
        }), 500

@app_manager.route('/api/debug/locks', ['GET'], limit="20 per minute")
def check_generation_locks():
    """Check generation locks for debugging"""
    try:
        username = get_user_info(app_manager)
        if not username:
            return app_manager.jsonify({
                'status': 'error',
                'message': 'Authentication required'
            }), 401
        
        lock_types = [
            f'task_generation_lock_{username}',
            f'reward_generation_lock_{username}',
            f'reward_task_generation_lock_{username}'
        ]
        
        locks_info = {}
        for lock_type in lock_types:
            lock_ref = db.collection('generation_locks').document(lock_type)
            lock_doc = lock_ref.get()
            
            if lock_doc.exists:
                lock_data = lock_doc.to_dict()
                lock_time = lock_data.get('locked_at')
                
                if lock_time and hasattr(lock_time, 'timestamp'):
                    lock_age = datetime.now() - datetime.fromtimestamp(lock_time.timestamp())
                    age_seconds = lock_age.total_seconds()
                    is_expired = age_seconds > 300
                    
                    locks_info[lock_type] = {
                        'exists': True,
                        'locked_at': lock_time,
                        'age_seconds': round(age_seconds, 2),
                        'is_expired': is_expired,
                        'username': lock_data.get('username'),
                        'type': lock_data.get('type')
                    }
                else:
                    locks_info[lock_type] = {
                        'exists': True,
                        'locked_at': 'Invalid timestamp',
                        'age_seconds': 'Unknown',
                        'is_expired': True,
                        'username': lock_data.get('username'),
                        'type': lock_data.get('type')
                    }
            else:
                locks_info[lock_type] = {
                    'exists': False,
                    'locked_at': None,
                    'age_seconds': 0,
                    'is_expired': False,
                    'username': None,
                    'type': None
                }
        
        return app_manager.jsonify({
            'status': 'success',
            'username': username,
            'locks': locks_info,
            'note': 'Locks expire after 5 minutes (300 seconds)'
        })
    except Exception as e:
        app_manager.logger.error(f"Failed to check generation locks: {e}")
        return app_manager.jsonify({
            'status': 'error',
            'message': f'Failed to check locks: {str(e)}'
        }), 500

@app_manager.route('/api/debug/reset-queue', ['POST'], limit="5 per minute")
def reset_task_queue():
    """Reset task queue by clearing presented_at timestamps for testing"""
    try:
        username = get_user_info(app_manager)
        if not username:
            return app_manager.jsonify({
                'status': 'error',
                'message': 'Authentication required'
            }), 401
        
        tasks_query = db.collection('tasks').where(
            filter=FieldFilter('username', '==', username)
        ).where(filter=FieldFilter('completed', '==', False))
        
        reset_count = 0
        total_tasks = 0
        for doc in tasks_query.stream():
            task_data = doc.to_dict()
            total_tasks += 1
            presented_at = task_data.get('presented_at')
            app_manager.logger.debug(f"Task {doc.id}: presented_at={presented_at}")
            if presented_at:
                app_manager.logger.debug(f"Resetting task {doc.id}: {presented_at}")
                doc.reference.update({'presented_at': firestore.DELETE_FIELD})
                reset_count += 1
        
        app_manager.logger.info(f"Reset queue: {total_tasks} total tasks, {reset_count} had presented_at timestamps")
        
        import time
        time.sleep(1)
        
        result = task_service.get_tasks(username)
        return app_manager.jsonify({
            'status': 'success',
            'message': f'Reset {reset_count} tasks back to queue and triggered new session',
            'reset_count': reset_count,
            'new_session_tasks': len(result.get('tasks', [])),
            'username': username
        })
    except Exception as e:
        app_manager.logger.error(f"Failed to reset task queue: {e}")
        return app_manager.jsonify({
            'status': 'error',
            'message': f'Failed to reset queue: {str(e)}'
        }), 500

@app_manager.route('/api/debug/time-weights', ['GET'], limit="20 per minute")
def check_time_and_weights():
    """Check current time, time period, and weights for debugging"""
    try:
        username = get_user_info(app_manager)
        if not username:
            return app_manager.jsonify({
                'status': 'error',
                'message': 'Authentication required'
            }), 401
        
        local_tz = pytz.timezone('US/Central')
        current_time = datetime.now(local_tz)
        current_hour = current_time.hour
        current_weekday = current_time.weekday()
        
        if current_weekday >= 5:
            time_period = "weekend"
        elif 6 <= current_hour < 8:
            time_period = "morning"
        elif 8 <= current_hour < 15:
            time_period = "workday"
        else:
            time_period = "evening"
        
        weights = task_master._get_time_based_weights(username)
        
        return app_manager.jsonify({
            'status': 'success',
            'username': username,
            'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'current_hour': current_hour,
            'current_weekday': current_weekday,
            'weekday_name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][current_weekday],
            'time_period': time_period,
            'weights': weights,
            'all_time_weights': task_master.TIME_WEIGHTS.get(username, task_master.TIME_WEIGHTS["default"])
        })
    except Exception as e:
        app_manager.logger.error(f"Failed to check time and weights: {e}")
        return app_manager.jsonify({
            'status': 'error',
            'message': f'Failed to check time and weights: {str(e)}'
        }), 500

# For gunicorn/app engine compatibility, app is already defined at module level
if __name__ == '__main__':
    app_manager.run()
