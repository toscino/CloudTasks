import os
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from dotenv import load_dotenv
from datetime import datetime, timedelta
from src.core.task_master import TaskMaster
from src.auth.auth_service import get_username_from_secret_key, get_spouse_username, get_user_info, get_auth_status
from src.utils.background_tasks import ensure_minimums
from src.utils.error_handlers import create_error_response, create_success_response, ratelimit_handler
from src.services.task_service import TaskService
from src.services.reward_service import RewardService
from src.services.goal_service import GoalService
from src.services.statistics_service import StatisticsService
from src.utils.logger import logger

# Load environment variables
load_dotenv()

# Set OpenAI API key from environment
import os
if not os.getenv('OPENAI_API_KEY'):
    logger.warning("OPENAI_API_KEY not found in environment variables")


# TODO: PERFORMANCE OPTIMIZATION
# Currently using client-side filtering for flexible testing
# Future: Create Firestore composite indexes and switch to direct queries
# See README.md "Performance Optimization Notes" section for details

def create_app():
    """Application factory pattern"""
    app = Flask(__name__, template_folder='templates')
    
    # Configure sessions
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-flask-secret-key-change-in-production')
    
    # Enable CORS for all routes
    CORS(app)
    
    # Initialize rate limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["1000 per hour", "100 per minute"],
        storage_uri="memory://"  # Use in-memory storage for simplicity
    )
    
    # Initialize Firestore client with explicit project ID
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'crucial-haiku-473123-r7')
    db = firestore.Client(project=project_id)
    
    # Initialize TaskMaster
    task_master = TaskMaster(db)
    
    # Initialize Services
    task_service = TaskService(db, task_master)
    reward_service = RewardService(db, task_master)
    goal_service = GoalService(db)
    statistics_service = StatisticsService(db, task_master)
    
    
    # Error handler for rate limit exceeded
    @app.errorhandler(429)
    def handle_ratelimit(e):
        return ratelimit_handler(e)
    
    @app.route('/')
    def index():
        """Main task display page"""
        # Ensure minimum content is available for any user accessing the site
        try:
            username = get_user_info()
            ensure_minimums(task_master, username, check_tasks=True, check_rewards=True, check_challenges=True)
        except Exception as e:
            # Don't fail the page load if ensure_minimums fails
            logger.debug(f"Background ensure_minimums failed on index load: {e}")
        
        return render_template('tasks.html')
    
    @app.route('/test')
    def test_interface():
        """Test interface for task creation"""
        return render_template('test.html')
    
    @app.route('/simple-test')
    def simple_test():
        """Simple test endpoint without authentication"""
        logger.info("Simple test endpoint called")
        return "Simple test works!"
    
    @app.route('/about')
    def about():
        """About page with app information"""
        return render_template('about.html')
    
    @app.route('/api/login', methods=['POST'])
    def login():
        """Login endpoint for session-based authentication"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            secret_key = data.get('secret_key')
            
            if not secret_key:
                return jsonify({'error': 'Secret key is required'}), 400
            
            # Determine username server-side from secret key
            username = get_username_from_secret_key(secret_key)
            
            # Store authentication in session
            session['authenticated_user'] = username
            session['is_authenticated'] = True
            
            # Ensure minimum content is available for the user (non-blocking)
            ensure_minimums(task_master, username, check_tasks=True, check_rewards=True, check_challenges=True)
            
            return jsonify({
                'status': 'success',
                'message': 'Login successful',
                'username': username,
                'authenticated': True
            })
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Login failed: {str(e)}'
            }), 500
    
    @app.route('/api/logout', methods=['POST'])
    def logout():
        """Logout endpoint to clear session"""
        try:
            session.clear()
            return jsonify({
                'status': 'success',
                'message': 'Logged out successfully'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Logout failed: {str(e)}'
            }), 500

    @app.route('/api/user', methods=['GET'])
    def get_current_user():
        """Get current authenticated user information"""
        try:
            is_authenticated, username = get_auth_status()
            
            return jsonify({
                'status': 'success',
                'username': username,
                'authenticated': is_authenticated,
                'session_based': 'authenticated_user' in session
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to get user info: {str(e)}'
            }), 500


    @app.route('/api/test', methods=['GET'])
    def test_firestore():
        """Test Firestore connection"""
        try:
            # Test Firestore connection by reading a document
            doc_ref = db.collection('test').document('connection')
            doc = doc_ref.get()
            
            if doc.exists:
                return jsonify({
                    'status': 'success',
                    'message': 'Firestore connection successful',
                    'data': doc.to_dict()
                })
            else:
                # Create a test document if it doesn't exist
                doc_ref.set({
                    'message': 'Hello from Firestore!',
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                return jsonify({
                    'status': 'success',
                    'message': 'Test document created in Firestore'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Firestore connection failed: {str(e)}'
            }), 500
    
    @app.route('/api/debug/locks', methods=['GET'])
    def check_generation_locks():
        """Check generation locks for debugging"""
        try:
            username = get_user_info()
            if not username:
                return jsonify({
                    'status': 'error',
                    'message': 'Authentication required'
                }), 401
            
            # Check all possible locks for this user
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
                        is_expired = age_seconds > 300  # 5 minutes
                        
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
            
            return jsonify({
                'status': 'success',
                'username': username,
                'locks': locks_info,
                'note': 'Locks expire after 5 minutes (300 seconds)'
            })
            
        except Exception as e:
            logger.error(f"Failed to check generation locks: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to check locks: {str(e)}'
            }), 500
    
    @app.route('/api/debug/reset-queue', methods=['POST'])
    def reset_task_queue():
        """Reset task queue by clearing presented_at timestamps for testing"""
        try:
            username = get_user_info()
            if not username:
                return jsonify({
                    'status': 'error',
                    'message': 'Authentication required'
                }), 401
            
            # Get all incomplete tasks for the user
            tasks_query = db.collection('tasks').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('completed', '==', False)
                ])
            )
            tasks_docs = tasks_query.stream()
            
            reset_count = 0
            total_tasks = 0
            for doc in tasks_docs:
                task_data = doc.to_dict()
                total_tasks += 1
                presented_at = task_data.get('presented_at')
                logger.debug(f"Task {doc.id}: presented_at={presented_at}")
                if presented_at:
                    # Clear the presented_at timestamp to put task back in queue
                    logger.debug(f"Resetting task {doc.id}: {presented_at}")
                    doc.reference.update({'presented_at': firestore.DELETE_FIELD})
                    reset_count += 1
            
            logger.info(f"Reset queue: {total_tasks} total tasks, {reset_count} had presented_at timestamps")
            
            # Wait a moment for Firestore to propagate the changes
            import time
            time.sleep(1)
            
            # Force a new task session by calling the task service
            result = task_service.get_tasks(username)
            
            return jsonify({
                'status': 'success',
                'message': f'Reset {reset_count} tasks back to queue and triggered new session',
                'reset_count': reset_count,
                'new_session_tasks': len(result.get('tasks', [])),
                'username': username
            })
            
        except Exception as e:
            logger.error(f"Failed to reset task queue: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to reset queue: {str(e)}'
            }), 500
    
    @app.route('/api/debug/time-weights', methods=['GET'])
    def check_time_and_weights():
        """Check current time, time period, and weights for debugging"""
        try:
            username = get_user_info()
            if not username:
                return jsonify({
                    'status': 'error',
                    'message': 'Authentication required'
                }), 401
            
            # Get current time info (Central timezone - Iowa/Chicago)
            from datetime import datetime
            import pytz
            local_tz = pytz.timezone('US/Central')
            current_time = datetime.now(local_tz)
            current_hour = current_time.hour
            current_weekday = current_time.weekday()  # 0=Monday, 6=Sunday
            
            # Determine time period
            if current_weekday >= 5:  # Saturday=5, Sunday=6
                time_period = "weekend"
            elif 6 <= current_hour < 8:
                time_period = "morning"
            elif 8 <= current_hour < 15:  # 3pm = 15:00
                time_period = "workday"
            else:
                time_period = "evening"
            
            # Get weights for this user and time period
            weights = task_master._get_time_based_weights(username)
            
            return jsonify({
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
            logger.error(f"Failed to check time and weights: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to check time and weights: {str(e)}'
            }), 500
    
    
    # Task Management Routes
    @app.route('/api/tasks', methods=['GET'])
    @limiter.limit("50 per minute")  # Limit reads to prevent excessive queries
    def get_tasks():
        """Get active task session (4 tasks) for current user"""
        username = get_user_info()
        
        # Ensure minimum content is available (non-blocking background task)
        ensure_minimums(task_master, username, check_tasks=True, check_rewards=True, check_challenges=True)
        
        result = task_service.get_tasks(username)
        
        # Log API interaction
        logger.api_interaction('/api/tasks', 'GET', username, 200 if result['status'] == 'success' else 500, 
                              f"Returned {len(result.get('tasks', []))} tasks")
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    
    @app.route('/api/tasks/statistics', methods=['GET'])
    @limiter.limit("20 per minute")  # Limit reads to prevent excessive queries
    def get_task_statistics():
        """Get task statistics including counts by category"""
        username = get_user_info()
        result = task_service.get_task_statistics(username)
        
        # Log API interaction
        logger.api_interaction('/api/tasks/statistics', 'GET', username, 200 if result['status'] == 'success' else 500, 
                              f"Returned task statistics")
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    
    @app.route('/api/tasks', methods=['POST'])
    @limiter.limit("20 per minute")  # Limit writes to prevent spam
    def create_task():
        """Create a new task"""
        data = request.get_json()
        username = get_user_info()
        result = task_service.create_task(data, username)
        
        # Log API interaction
        status_code = 200
        if 'error' in result:
            status_code = 400
        elif result['status'] == 'error':
            status_code = 500
        
        logger.api_interaction('/api/tasks', 'POST', username, status_code, 
                              f"Created task: {data.get('description', 'Unknown')[:50]}...")
        
        if 'error' in result:
            return jsonify(result), 400
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    @app.route('/api/tasks/<task_id>/complete', methods=['PUT'])
    @limiter.limit("30 per minute")  # Limit updates
    def complete_task(task_id):
        """Mark a task as completed and refresh the task session"""
        username = get_user_info()
        result = task_service.complete_task(task_id, username)
        
        # Log API interaction
        status_code = 200
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
        
        reward_earned = result.get('reward_earned', False)
        logger.api_interaction('/api/tasks/complete', 'PUT', username, status_code, 
                              f"Completed task {task_id}, reward earned: {reward_earned}")
        
        if result['status'] == 'error':
            return jsonify(result), status_code
        return jsonify(result)
    
    @app.route('/api/tasks/<task_id>/save', methods=['PUT'])
    @limiter.limit("30 per minute")  # Limit updates
    def save_task(task_id):
        """Toggle save status for a task"""
        username = get_user_info()
        result = task_service.save_task(task_id, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
            return jsonify(result), status_code
        return jsonify(result)
    
    # Reward Management Routes
    @app.route('/api/rewards', methods=['GET'])
    @limiter.limit("50 per minute")  # Limit reads to prevent excessive queries
    def get_rewards():
        """Get all rewards for current user (max 4)"""
        username = get_user_info()
        result = reward_service.get_rewards(username)
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    @app.route('/api/rewards', methods=['POST'])
    @limiter.limit("20 per minute")  # Limit writes to prevent spam
    def create_reward():
        """Create a new reward"""
        data = request.get_json()
        username = get_user_info()
        result = reward_service.create_reward(data, username)
        
        if 'error' in result:
            return jsonify(result), 400
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    @app.route('/api/rewards/<reward_id>/complete', methods=['PUT'])
    @limiter.limit("30 per minute")  # Limit updates
    def complete_reward(reward_id):
        """Mark a reward as completed"""
        username = get_user_info()
        result = reward_service.complete_reward(reward_id, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
            return jsonify(result), status_code
        return jsonify(result)
    
    @app.route('/api/rewards/<reward_id>/save', methods=['PUT'])
    @limiter.limit("30 per minute")  # Limit updates
    def save_reward(reward_id):
        """Toggle save status for a reward"""
        username = get_user_info()
        result = reward_service.save_reward(reward_id, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
            return jsonify(result), status_code
        return jsonify(result)
    
    @app.route('/api/reward-options/<option_id>/select', methods=['POST'])
    @limiter.limit("10 per minute")  # Limit reward selections
    def select_reward_option(option_id):
        """Select a reward option and mark it as selected"""
        try:
            username = get_user_info()
            
            # Use RewardMaster to select the reward option
            selected_option = task_master.reward_master.select_reward_option(username, option_id)
            
            if selected_option:
                return jsonify({
                    'status': 'success',
                    'message': 'Reward option selected successfully',
                    'selected_option': selected_option
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to select reward option'
                }), 400
                
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to select reward option: {str(e)}'
            }), 500
    
    @app.route('/api/earned-rewards', methods=['GET'])
    @limiter.limit("20 per minute")  # Limit reads
    def get_pending_rewards():
        """Get pending earned rewards for current user"""
        username = get_user_info()
        result = reward_service.get_pending_rewards(username)
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    @app.route('/api/earned-rewards/<reward_id>/generate-options', methods=['POST'])
    @limiter.limit("10 per minute")  # Limit reward option generation
    def generate_reward_options(reward_id):
        """Generate reward options for a specific earned reward"""
        username = get_user_info()
        result = reward_service.generate_reward_options(reward_id, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
            elif 'already been processed' in result['message'].lower():
                status_code = 400
            return jsonify(result), status_code
        return jsonify(result)
    
    @app.route('/api/earned-rewards/<reward_id>/select-option', methods=['POST'])
    @limiter.limit("10 per minute")  # Limit reward selections
    def select_reward_option_from_earned(reward_id):
        """Select a reward option for a specific earned reward"""
        data = request.get_json()
        if not data or not data.get('option_id'):
            return jsonify({'error': 'Option ID is required'}), 400
        
        username = get_user_info()
        option_id = data['option_id']
        result = reward_service.select_reward_option(reward_id, option_id, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
            elif 'already been processed' in result['message'].lower():
                status_code = 400
            elif 'failed to select' in result['message'].lower():
                status_code = 400
            return jsonify(result), status_code
        return jsonify(result)
    
    
    # Goals Management Routes
    @app.route('/rewards')
    def rewards_page():
        """Rewards management page"""
        return render_template('reward_claim.html')

    
    @app.route('/goals')
    def goals_page():
        """Goals management page"""
        return render_template('goals.html')
    
    @app.route('/rewards-owed')
    def rewards_owed_page():
        """Rewards owed management page"""
        return render_template('rewards_owed.html')
    
    
    @app.route('/api/goals', methods=['GET'])
    @limiter.limit("50 per minute")  # Limit reads
    def get_goals():
        """Get all goals for current user organized by category"""
        username = get_user_info()
        result = goal_service.get_goals(username)
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    @app.route('/api/goals', methods=['POST'])
    @limiter.limit("20 per minute")  # Limit writes
    def create_goal():
        """Create a new goal"""
        data = request.get_json()
        username = get_user_info()
        result = goal_service.create_goal(data, username)
        
        if 'error' in result:
            return jsonify(result), 400
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    @app.route('/api/goals/<goal_id>', methods=['PUT'])
    @limiter.limit("30 per minute")  # Limit updates
    def update_goal(goal_id):
        """Update an existing goal"""
        data = request.get_json()
        username = get_user_info()
        result = goal_service.update_goal(goal_id, data, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
            return jsonify(result), status_code
        return jsonify(result)
    
    @app.route('/api/goals/<goal_id>', methods=['DELETE'])
    @limiter.limit("30 per minute")  # Limit deletes
    def delete_goal(goal_id):
        """Delete a goal"""
        username = get_user_info()
        result = goal_service.delete_goal(goal_id, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
            return jsonify(result), status_code
        return jsonify(result)
    
    @app.route('/api/goals/categories', methods=['GET'])
    def get_categories():
        """Get available goal categories"""
        result = goal_service.get_categories()
        return jsonify(result)
    
    @app.route('/api/reward-goals/test', methods=['GET'])
    def test_reward_goals():
        """Test endpoint to check if reward goals API is reachable"""
        return jsonify({
            'status': 'success',
            'message': 'Reward goals API is working',
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/rewards-owed', methods=['GET'])
    @limiter.limit("50 per minute")  # Limit reads
    def get_rewards_owed():
        """Get pending rewards owed for current user"""
        username = get_user_info()
        result = goal_service.get_rewards_owed(username)
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    @app.route('/api/rewards-owed/<goal_id>/complete', methods=['POST'])
    @limiter.limit("10 per minute")  # Limit completions
    def complete_reward_owed(goal_id):
        """Complete a reward owed"""
        username = get_user_info()
        result = goal_service.complete_reward_owed(goal_id, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower():
                status_code = 404
            elif 'unauthorized' in result['message'].lower():
                status_code = 403
            elif 'already completed' in result['message'].lower():
                status_code = 400
            return jsonify(result), status_code
        return jsonify(result)
    
    @app.route('/api/challenges', methods=['GET'])
    @limiter.limit("50 per minute")  # Limit reads
    def get_challenges():
        """Get active challenges for current user, with background pregeneration"""
        username = get_user_info()
        
        # Ensure minimum content is available (non-blocking background task)
        ensure_minimums(task_master, username, check_tasks=True, check_rewards=True, check_challenges=True)
        
        result = statistics_service.get_challenges(username)
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    
    
    @app.route('/api/challenges/<task_id>/complete', methods=['POST'])
    @limiter.limit("10 per minute")  # Limit completions
    def complete_challenge(task_id):
        """Complete a challenge and mark associated reward goal as completed"""
        username = get_user_info()
        result = statistics_service.complete_challenge(task_id, username)
        
        if result['status'] == 'error':
            status_code = 500
            if 'not found' in result['message'].lower() or 'unauthorized' in result['message'].lower():
                status_code = 404
            return jsonify(result), status_code
        return jsonify(result)
    
    @app.route('/api/weekly-points', methods=['GET'])
    @limiter.limit("50 per minute")  # Limit reads
    def get_weekly_points():
        """Get weekly difficulty points for current user"""
        username = get_user_info()
        result = statistics_service.get_weekly_points(username)
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    @app.route('/api/reward-comparison', methods=['GET'])
    @limiter.limit("50 per minute")  # Limit reads
    def get_reward_comparison():
        """Get pending rewards comparison between spouses"""
        username = get_user_info()
        spouse_username = get_spouse_username(username)
        result = statistics_service.get_reward_comparison(username, spouse_username)
        
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result)
    
    return app
