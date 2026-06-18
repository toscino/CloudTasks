"""
User service - manages user settings and spouse relationships
"""
from datetime import datetime, timedelta, date
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
import random
import string
from src.utils.error_handlers import handle_exception
from src.utils.firestore_helpers import convert_firestore_timestamp
from src.utils.config import get_timezone
from src.utils.reset_period import get_reset_day


class UserService:
    """Service for user settings and spouse linking"""
    
    PAIRING_CODE_LENGTH = 6
    PAIRING_CODE_EXPIRY_MINUTES = 15
    
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
    
    def get_user_settings(self, username: str) -> dict:
        """Get user settings (create default if missing)"""
        try:
            user_ref = self.db.collection('users').document(username)
            user_doc = user_ref.get()
            
            if user_doc.exists:
                settings = user_doc.to_dict()
                settings['username'] = username
                return settings
            
            # Create default settings
            default_settings = {
                'username': username,
                'spouse_username': None,
                'can_select_morning_cards': False,
                'vacation_mode': False,
                'travel_day_mode': False,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            user_ref.set(default_settings)
            self.logger.info(f"Created default settings for user: {username}")
            return default_settings
            
        except Exception as e:
            self.logger.error(f"Failed to get user settings for {username}: {e}")
            return {
                'username': username,
                'spouse_username': None,
                'can_select_morning_cards': False,
                'vacation_mode': False,
                'travel_day_mode': False,
            }
    
    def generate_pairing_code(self, username: str) -> dict:
        """Generate pairing code"""
        try:
            # Generate random 6-character code (3 chars - 3 chars)
            code_parts = []
            for _ in range(2):
                part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
                code_parts.append(part)
            code = '-'.join(code_parts)
            
            # Store in database
            pairing_data = {
                'code': code,
                'created_by_username': username,
                'created_at': firestore.SERVER_TIMESTAMP,
                'expires_at_minutes': self.PAIRING_CODE_EXPIRY_MINUTES,  # Store duration for calculation
                'used': False
            }
            
            self.db.collection('pairing_codes').document(code).set(pairing_data)
            
            self.logger.info(f"Generated pairing code for {username}: {code}")
            
            # Calculate expiration time for return value
            expires_at_iso = (datetime.now() + timedelta(minutes=self.PAIRING_CODE_EXPIRY_MINUTES)).isoformat()
            
            return {
                'status': 'success',
                'code': code,
                'expires_at': expires_at_iso
            }
            
        except Exception as e:
            return handle_exception(e, f"Failed to generate pairing code for {username}")
    
    def link_with_pairing_code(self, username: str, code: str) -> dict:
        """Link spouses via pairing code"""
        try:
            # Get the pairing code
            code_ref = self.db.collection('pairing_codes').document(code)
            code_doc = code_ref.get()
            
            if not code_doc.exists:
                return {
                    'status': 'error',
                    'message': 'Invalid pairing code'
                }
            
            code_data = code_doc.to_dict()
            
            # Check if already used
            if code_data.get('used', False):
                return {
                    'status': 'error',
                    'message': 'Pairing code has already been used'
                }
            
            # Check if expired
            created_at = code_data.get('created_at')
            created_datetime = convert_firestore_timestamp(created_at)
            expires_minutes = code_data.get('expires_at_minutes', self.PAIRING_CODE_EXPIRY_MINUTES)
            
            if not created_datetime:
                # Assume expired if no created_at
                return {
                    'status': 'error',
                    'message': 'Invalid pairing code'
                }
            
            # Calculate expiration time from created_at + duration
            expires_datetime = created_datetime + timedelta(minutes=expires_minutes)
            
            # Compare with current time (same approach as task_master.py)
            current_time = datetime.now()
            self.logger.debug(f"Checking code expiration: current={current_time}, expires={expires_datetime}, diff={(expires_datetime - current_time).total_seconds()}s")
            
            if current_time > expires_datetime:
                return {
                    'status': 'error',
                    'message': 'Pairing code has expired'
                }
            
            # Can't link to yourself
            creator_username = code_data.get('created_by_username')
            if creator_username == username:
                return {
                    'status': 'error',
                    'message': 'Cannot link to yourself'
                }
            
            # Check if creator already has a spouse
            creator_settings = self.get_user_settings(creator_username)
            if creator_settings.get('spouse_username'):
                return {
                    'status': 'error',
                    'message': 'Code creator already has a spouse linked'
                }
            
            # Check if current user already has a spouse
            user_settings = self.get_user_settings(username)
            if user_settings.get('spouse_username'):
                return {
                    'status': 'error',
                    'message': 'You already have a spouse linked. Unlink first.'
                }
            
            # Create bidirectional link
            creator_ref = self.db.collection('users').document(creator_username)
            user_ref = self.db.collection('users').document(username)
            
            # Creator (initiating partner) should be marked as inverted
            creator_ref.update({
                'spouse_username': username,
                'inverted': True,  # Initiating partner is always inverted
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            user_ref.update({
                'spouse_username': creator_username,
                'inverted': False,  # Joining partner is not inverted
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Mark code as used
            code_ref.update({'used': True})
            
            self.logger.info(f"Linked users: {username} <-> {creator_username}")
            
            return {
                'status': 'success',
                'message': f'Successfully linked to {creator_username}',
                'spouse_username': creator_username
            }
            
        except Exception as e:
            return handle_exception(e, f"Failed to link with pairing code")
    
    def remove_spouse(self, username: str) -> dict:
        """Remove spouse link"""
        try:
            user_settings = self.get_user_settings(username)
            spouse_username = user_settings.get('spouse_username')
            
            if not spouse_username:
                return {
                    'status': 'error',
                    'message': 'No spouse linked to remove'
                }
            
            # Remove bidirectional link
            user_ref = self.db.collection('users').document(username)
            spouse_ref = self.db.collection('users').document(spouse_username)
            
            user_ref.update({
                'spouse_username': None,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            spouse_ref.update({
                'spouse_username': None,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            self.logger.info(f"Removed spouse link: {username} <-> {spouse_username}")
            
            return {
                'status': 'success',
                'message': f'Successfully unlinked from {spouse_username}'
            }
            
        except Exception as e:
            return handle_exception(e, f"Failed to remove spouse link")
    
    def update_preferences(self, username: str, preferences: dict) -> dict:
        """Update user preferences and sync vacation_mode to spouse"""
        try:
            user_ref = self.db.collection('users').document(username)
            user_settings = self.get_user_settings(username)
            
            # Only allow specific preference updates
            allowed_prefs = [
                'can_select_morning_cards',
                'inverted',
                'vacation_mode',
                'travel_day_mode',
            ]
            update_data = {
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Track if vacation_mode or travel_day_mode changed
            old_vacation_mode = user_settings.get('vacation_mode', False)
            old_travel_day_mode = user_settings.get('travel_day_mode', False)
            vacation_mode_changed = False
            travel_day_mode_changed = False
            
            for key, value in preferences.items():
                if key in allowed_prefs:
                    update_data[key] = value
                    if key == 'vacation_mode' and value != old_vacation_mode:
                        vacation_mode_changed = True
                    if key == 'travel_day_mode' and value != old_travel_day_mode:
                        travel_day_mode_changed = True
            
            user_ref.update(update_data)
            
            # Sync vacation_mode to spouse if changed
            spouse_username = user_settings.get('spouse_username')
            if vacation_mode_changed and spouse_username and 'vacation_mode' in preferences:
                spouse_ref = self.db.collection('users').document(spouse_username)
                spouse_ref.update({
                    'vacation_mode': preferences['vacation_mode'],
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                self.logger.info(f"Synced vacation_mode to spouse {spouse_username}: {preferences['vacation_mode']}")
            
            # If vacation_mode changed, reset tasks for both users with tracker reversal
            if vacation_mode_changed:
                from src.services.daily_task_service import DailyTaskService
                daily_task_service = DailyTaskService(self.app_manager)
                
                reset_day = get_reset_day(tz=get_timezone())
                
                # Reset tasks with tracker reversal (undoes points earned today)
                self.logger.info(f"Resetting tasks with tracker reversal for {username} due to vacation_mode change")
                daily_task_service.reset_daily_tasks_with_tracker_reversal(username, reset_day)

            if travel_day_mode_changed:
                from src.services.daily_task_service import DailyTaskService
                daily_task_service = DailyTaskService(self.app_manager)

                reset_day = get_reset_day(tz=get_timezone())

                self.logger.info(
                    f"Resetting tasks for {username} only due to travel_day_mode change"
                )
                daily_task_service.reset_daily_tasks_for_user_only(username, reset_day)
            
            self.logger.info(f"Updated preferences for {username}: {preferences}")
            
            return {
                'status': 'success',
                'message': 'Preferences updated successfully'
            }
            
        except Exception as e:
            return handle_exception(e, f"Failed to update preferences")

