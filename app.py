import os
from flask import render_template, session, request
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
from src.services.user_service import UserService
from src.services.performance_reward_service import PerformanceRewardService
from src.services.dice_roll_service import DiceRollService
from src.services.task_points_service import TaskPointsService
from src.utils.config import get_timezone
from src.utils.reset_period import get_reset_day

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
daily_task_service = DailyTaskService(app_manager)
task_points_service = TaskPointsService(app_manager, daily_task_service)
task_master = TaskMaster(db, task_points_service, daily_task_service)
task_service = TaskService(app_manager, task_master)
goal_service = GoalService(app_manager)
statistics_service = StatisticsService(app_manager, task_master)
collaboration_service = CollaborationService(app_manager)
user_service = UserService(app_manager)
performance_reward_service = PerformanceRewardService(app_manager)
dice_roll_service = DiceRollService(app_manager, performance_reward_service)

# Store services on app_manager for easy access
app_manager.collaboration_service = collaboration_service
app_manager.user_service = user_service
app_manager.task_points_service = task_points_service
app_manager.performance_reward_service = performance_reward_service

# Error handler for rate limit exceeded
@app.errorhandler(429)
def handle_ratelimit(e):
    return ratelimit_handler(e)

# Page routes
app_manager.page("tasks.html", root=True)
app_manager.page("stats.html")
app_manager.page("test.html")
app_manager.page("settings.html")
app_manager.page("goals.html")
app_manager.page("daily_tasks.html")
app_manager.page("performance_tiers.html")
app_manager.page("dice-rolls.html")
app_manager.page("dice_manage.html")

# flask-base only auto-populates nav for auth-gated pages; set explicitly for public pages
app_manager._pages = [
    {"route": "/", "title": "📋 Tasks", "permission": None},
    {"route": "/stats", "title": "📊 Stats", "permission": None},
    {"route": "/dice-rolls", "title": "🎲 Dice Rolls", "permission": None},
    {"route": "/dice-rolls/manage", "title": "⚙️ Manage Dice", "permission": None},
    {"route": "/daily-tasks", "title": "📅 Daily Tasks", "permission": None},
    {"route": "/performance-tiers", "title": "🎁 Performance Tiers", "permission": None},
    {"route": "/goals", "title": "🎯 Goals", "permission": None},
    {"route": "/test", "title": "🧪 Test", "permission": None},
    {"route": "/settings", "title": "⚙️ Settings", "permission": None},
]

@app_manager.route('/dice-rolls/manage')
def dice_manage_page():
    """Dice configuration (rules per die, import/export)."""
    return render_template('dice_manage.html')


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
    reset_day = get_reset_day()
    instances_query = db.collection('daily_task_instances').where(
        filter=FieldFilter('username', '==', username)
    ).where(filter=FieldFilter('date', '==', reset_day.isoformat()))
    
    deleted_count = 0
    for instance in instances_query.stream():
        instance.reference.delete()
        deleted_count += 1
    
    reset_query = db.collection('daily_task_resets').where(
        filter=FieldFilter('username', '==', username)
    ).where(filter=FieldFilter('last_reset_date', '==', reset_day.isoformat()))
    for reset_doc in reset_query.stream():
        reset_doc.reference.delete()
    
    result = daily_task_service.check_and_reset_daily_tasks(username)
    return app_manager.jsonify({
        'status': 'success',
        'message': f'Daily tasks reset successfully - deleted {deleted_count} instances',
        'result': result
    })


# Task Points Routes (standalone tracker)
@app_manager.route('/api/task-points/balance', ['GET'], limit="50 per minute")
@with_error_handling
def get_task_points_balance():
    """Get joint balance, today's points per person, streaks"""
    username = get_user_info(app_manager)
    return task_points_service.get_balance_summary(username)


@app_manager.route('/api/task-points/today', ['GET'], limit="100 per minute")
@with_error_handling
def get_task_points_today():
    """Fast today points and thresholds for user and spouse (nav indicator)."""
    username = get_user_info(app_manager)
    return task_points_service.get_today_summary(username)


@app_manager.route('/api/task-points/spend', ['POST'], limit="20 per minute")
@with_error_handling
def spend_task_points():
    """Subtract points from joint balance (manual spending)"""
    username = get_user_info(app_manager)
    data = app_manager.get_json() or {}
    amount = data.get('amount')
    description = data.get('description', '')
    if amount is None:
        return app_manager.jsonify({'status': 'error', 'message': 'amount is required'}), 400
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return app_manager.jsonify({'status': 'error', 'message': 'amount must be an integer'}), 400
    return task_points_service.spend_points(username, amount, description)


@app_manager.route('/api/task-points/config', ['GET'], limit="50 per minute")
@with_error_handling
def get_task_points_config():
    """Get computed daily_goal_today (and spouse if linked)"""
    username = get_user_info(app_manager)
    return app_manager.jsonify({
        'status': 'success',
        'config': task_points_service.get_config(username)
    })


@app_manager.route('/api/task-points/config', ['PUT'], limit="20 per minute")
@with_error_handling
def update_task_points_config():
    """Deprecated: daily goal is computed from tasks; PUT returns current config only"""
    username = get_user_info(app_manager)
    return task_points_service.update_config(username)


@app_manager.route('/api/task-points/spending-history', ['GET'], limit="20 per minute")
@with_error_handling
def get_task_points_spending_history():
    """Get recent spending records"""
    username = get_user_info(app_manager)
    limit_param = request.args.get('limit', 20, type=int)
    limit_param = min(max(limit_param, 1), 100)
    return task_points_service.get_spending_history(username, limit_param)


@app_manager.route('/api/task-points/daily-history', ['GET'], limit="30 per minute")
@with_error_handling
def get_task_points_daily_history():
    """Get per-day points and streak status for calendar (last N days)"""
    username = get_user_info(app_manager)
    num_days = request.args.get('days', 90, type=int)
    num_days = min(max(num_days, 1), 365)
    return task_points_service.get_daily_history(username, num_days)


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


def _created_at_sort_key(created_at):
    """Return a comparable value for created_at for sorting (newer = larger)."""
    if created_at is None:
        return 0
    if hasattr(created_at, 'timestamp'):
        return created_at.timestamp()
    return 0


@app_manager.route('/api/collaboration/history', ['GET'], limit="20 per minute")
def get_collaboration_history():
    """Get last 7 days of tracker history"""
    username = get_user_info(app_manager)
    today = get_reset_day()
    seven_days_ago = today - timedelta(days=7)
    
    history_query = db.collection('tracker_history').where(
        'date', '>=', seven_days_ago.isoformat()
    ).order_by('date', direction=firestore.Query.DESCENDING)
    
    history = []
    for doc in history_query.stream():
        data = doc.to_dict()
        created_at = data.get('created_at')
        history.append({
            'date': data['date'],
            'ian_points': data['user_points'],
            'karleigh_points': data['spouse_points'],
            'ian_adjustment': data.get('user_movement', data.get('user_adjustment', 0)),
            'karleigh_adjustment': data.get('spouse_movement', data.get('spouse_adjustment', 0)),
            'old_tracker': data['old_value'],
            'new_tracker': data['new_value'],
            '_created_at': created_at,
        })
    
    history.sort(key=lambda x: (x['date'], _created_at_sort_key(x['_created_at'])), reverse=True)
    for item in history:
        del item['_created_at']
    
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
        created_at = data.get('created_at')
        history.append({
            'date': data['date'],
            'is_test': data.get('is_test', False),
            'user_points': data.get('user_points', 0),
            'spouse_points': data.get('spouse_points', 0),
            'user_adjustment': data.get('user_movement', data.get('user_adjustment', 0)),
            'spouse_adjustment': data.get('spouse_movement', data.get('spouse_adjustment', 0)),
            'old_tracker': data.get('old_value', 0),
            'new_tracker': data.get('new_value', 0),
            '_created_at': created_at,
        })
    
    history.sort(key=lambda x: (x['date'], _created_at_sort_key(x['_created_at'])), reverse=True)
    for item in history:
        del item['_created_at']
    
    return app_manager.jsonify({'status': 'success', 'history': history, 'count': len(history)})

@app_manager.route('/api/collaboration/reset-history', ['POST'], limit="5 per minute")
@with_error_handling
def reset_tracker_history():
    """Reset tracker history for testing"""
    username = get_user_info(app_manager)
    return collaboration_service.reset_tracker_history()

@app_manager.route('/api/collaboration/tracker-at-reset', ['GET'], limit="20 per minute")
@with_error_handling
def get_tracker_at_reset():
    """Get the collaboration tracker value at daily reset boundary (4am Chicago)"""
    username = get_user_info(app_manager)
    return collaboration_service.get_tracker_at_reset()

@app_manager.route('/api/collaboration/progress-day', ['POST'], limit="5 per minute")
@with_error_handling
def progress_day_testing():
    """Manually trigger daily reset for testing"""
    username = get_user_info(app_manager)
    result = daily_task_service.check_and_reset_daily_tasks(username)
    return result

# Performance reward routes
@app_manager.route('/api/performance-tier-settings', ['GET'], limit="50 per minute")
@with_error_handling
def get_performance_tier_settings():
    username = get_user_info(app_manager)
    return performance_reward_service.get_tier_settings(username)


@app_manager.route('/api/performance-tier-settings', ['PUT'], limit="20 per minute")
@with_error_handling
def save_performance_tier_settings():
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    if not data or 'tiers' not in data:
        return app_manager.jsonify({'status': 'error', 'message': 'tiers array is required'}), 400
    return performance_reward_service.save_tier_settings(username, data['tiers'])


@app_manager.route('/api/performance-tier-settings/preview', ['GET'], limit="50 per minute")
@with_error_handling
def preview_performance_bands():
    username = get_user_info(app_manager)
    return performance_reward_service.get_band_preview(username)


@app_manager.route('/api/performance-bonus/<item_id>/complete', ['PUT'], limit="30 per minute")
@with_error_handling
def complete_performance_bonus(item_id):
    username = get_user_info(app_manager)
    return performance_reward_service.complete_bonus_item(item_id, username)


@app_manager.route('/api/performance-bonus/<item_id>/abandon', ['PUT'], limit="20 per minute")
@with_error_handling
def abandon_performance_bonus(item_id):
    username = get_user_info(app_manager)
    return performance_reward_service.abandon_bonus_item(item_id, username)


@app_manager.route('/api/owed-points', ['GET'], limit="50 per minute")
@with_error_handling
def get_owed_points():
    username = get_user_info(app_manager)
    return performance_reward_service.get_owed_points(username)


@app_manager.route('/api/performance-bonus/test', ['POST'], limit="10 per minute")
@with_error_handling
def create_test_performance_bonus():
    """Add a random pending bonus item for the current user (testing)."""
    username = get_user_info(app_manager)
    return performance_reward_service.create_test_bonus_item(username)


@app_manager.route('/api/owed-points/clear', ['POST'], limit="10 per minute")
@with_error_handling
def clear_owed_points():
    """Clear owed-point balances for the couple (testing)."""
    username = get_user_info(app_manager)
    return performance_reward_service.clear_owed_points(username)

# Dice Roll API Routes
@app_manager.route('/api/dice-rolls/config', ['GET'], limit="50 per minute")
@with_error_handling
def get_dice_roll_config():
    """Get dice configuration for couple (includes saved_dice_selection, can_roll, can_save_selection when authenticated)"""
    username = get_user_info(app_manager)
    couple_id = dice_roll_service.get_couple_id(username)
    if not couple_id:
        return app_manager.jsonify({'status': 'error', 'message': 'Could not determine couple_id'}), 400
    return dice_roll_service.get_dice_configuration(couple_id, username)

@app_manager.route('/api/dice-rolls/config', ['POST'], limit="20 per minute")
@with_error_handling
def save_dice_roll_config():
    """Save dice configuration for couple"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    if not data or 'dice_configs' not in data:
        return app_manager.jsonify({'status': 'error', 'message': 'dice_configs is required'}), 400
    couple_id = dice_roll_service.get_couple_id(username)
    if not couple_id:
        return app_manager.jsonify({'status': 'error', 'message': 'Could not determine couple_id'}), 400
    return dice_roll_service.save_dice_configuration(couple_id, data, username)

@app_manager.route('/api/dice-rolls/selection', ['POST'], limit="20 per minute")
@with_error_handling
def save_dice_roll_selection():
    """Save which dice are selected (non–morning-card person only)"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    if not data or 'saved_dice_selection' not in data:
        return app_manager.jsonify({'status': 'error', 'message': 'saved_dice_selection is required'}), 400
    return dice_roll_service.save_saved_dice_selection(username, data['saved_dice_selection'])

@app_manager.route('/api/dice-rolls/config/import', ['POST'], limit="20 per minute")
@with_error_handling
def import_dice_roll_config():
    """Import (partial) dice configuration; each die present is full-replaced"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    if not data:
        return app_manager.jsonify({'status': 'error', 'message': 'Request body required'}), 400
    couple_id = dice_roll_service.get_couple_id(username)
    if not couple_id:
        return app_manager.jsonify({'status': 'error', 'message': 'Could not determine couple_id'}), 400
    return dice_roll_service.import_dice_configuration(couple_id, data, username)

@app_manager.route('/api/dice-rolls/roll', ['POST'], limit="20 per minute")
@with_error_handling
def roll_dice():
    """Roll dice (only users with can_select_morning_cards can call)"""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    if not data:
        return app_manager.jsonify({
            'status': 'error',
            'message': 'Request body required'
        }), 400
    
    selected_dice = data.get('selected_dice')
    if selected_dice is None:
        return app_manager.jsonify({
            'status': 'error',
            'message': 'selected_dice is required',
        }), 400
    return dice_roll_service.roll_dice(username, selected_dice)

@app_manager.route('/api/dice-rolls/history', ['GET'], limit="50 per minute")
@with_error_handling
def get_dice_roll_history():
    """Last two saved roll sessions for the current user."""
    username = get_user_info(app_manager)
    return dice_roll_service.get_roll_history(username, limit=2)

@app_manager.route('/api/dice-rolls/roll/<roll_id>/reroll', ['POST'], limit="20 per minute")
@with_error_handling
def reroll_dice_instance(roll_id):
    """Reroll one die instance once for a saved roll session."""
    username = get_user_info(app_manager)
    data = app_manager.get_json()
    if not data or 'instance_index' not in data:
        return app_manager.jsonify({
            'status': 'error',
            'message': 'instance_index is required',
        }), 400
    try:
        instance_index = int(data['instance_index'])
    except (TypeError, ValueError):
        return app_manager.jsonify({
            'status': 'error',
            'message': 'instance_index must be an integer',
        }), 400
    return dice_roll_service.reroll_one_instance(username, roll_id, instance_index)

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
