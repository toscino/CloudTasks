"""
Morning Card Service - handles morning card templates and daily selections
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta
import random
from src.utils.config import get_timezone
from src.utils.firestore_helpers import prepare_firestore_document
from src.utils.error_handlers import handle_exception
from typing import List, Dict, Any


class MorningCardService:
    """Service for morning card operations"""
    
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()
    
    def _convert_generic_rules_to_usernames(self, user_rules: Dict[str, List[str]], card_owner: str) -> Dict[str, List[str]]:
        """Convert generic 'mine'/'spouse' keys to actual usernames"""
        if not isinstance(user_rules, dict):
            return {}
        
        converted_rules = {}
        
        # Get spouse username from database
        spouse_username = None
        try:
            user_ref = self.db.collection('users').document(card_owner)
            user_doc = user_ref.get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                spouse_username = user_data.get('spouse_username')
        except Exception as e:
            self.logger.debug(f"Could not fetch spouse for {card_owner}: {e}")
        
        for key, rules in user_rules.items():
            if key == 'mine':
                converted_rules[card_owner] = rules
            elif key == 'spouse' and spouse_username:
                converted_rules[spouse_username] = rules
            else:
                # Keep other keys as-is
                converted_rules[key] = rules
        
        return converted_rules
    
    def get_card_templates(self, username: str) -> Dict[str, Any]:
        """Get card templates for user and spouse"""
        try:
            # Query cards for current user
            templates_query = self.db.collection('morning_card_templates').where(
                filter=FieldFilter('username', '==', username)
            )
            templates_docs = list(templates_query.stream())
            
            # Query cards for spouse if linked
            spouse_username = None
            try:
                user_ref = self.db.collection('users').document(username)
                user_doc = user_ref.get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    spouse_username = user_data.get('spouse_username')
            except Exception as e:
                self.logger.debug(f"Could not fetch spouse for {username}: {e}")
            
            if spouse_username:
                spouse_query = self.db.collection('morning_card_templates').where(
                    filter=FieldFilter('username', '==', spouse_username)
                )
                templates_docs.extend(list(spouse_query.stream()))
            
            templates = []
            for doc in templates_docs:
                template_data = prepare_firestore_document(doc)
                
                # Convert generic rules to actual usernames for display
                card_owner = template_data.get('username')
                if card_owner and 'user_rules' in template_data:
                    template_data['user_rules'] = self._convert_generic_rules_to_usernames(
                        template_data['user_rules'], 
                        card_owner
                    )
                
                templates.append(template_data)
            
            return {
                'status': 'success',
                'templates': templates
            }
        except Exception as e:
            return handle_exception(e, "Failed to get card templates")
    
    def create_card_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create card template"""
        try:
            if not data or not data.get('card_text'):
                return {'status': 'error', 'message': 'Card text is required'}
            
            # Validate and prepare data
            card_text = data['card_text'].strip()
            clothes_points = int(data.get('clothes_points', 0))
            timer_minutes = int(data.get('timer_minutes', 0))
            user_rules = data.get('user_rules', {}) or {}
            active = data.get('active', True)
            
            # Ensure user_rules is a dict
            if not isinstance(user_rules, dict):
                user_rules = {}
            
            # Get username from auth context (passed from API endpoint)
            username = data.get('username')
            if not username:
                return {'status': 'error', 'message': 'Username is required'}
            
            # Validate and clean user_rules
            # Keep as generic keys ('mine', 'spouse') for storage
            cleaned_user_rules = {}
            for rule_key, rules in user_rules.items():
                if isinstance(rules, list):
                    cleaned_rules = [r.strip() for r in rules if r and r.strip()]
                    if cleaned_rules:  # Only include non-empty rule lists
                        cleaned_user_rules[rule_key] = cleaned_rules
            
            # Create template data
            template_data = {
                'username': username,
                'card_text': card_text,
                'clothes_points': clothes_points,
                'timer_minutes': timer_minutes,
                'user_rules': cleaned_user_rules,
                'active': active,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Create new template in Firestore
            doc_ref = self.db.collection('morning_card_templates').add(template_data)
            template_id = doc_ref[1].id
            
            self.logger.info(f"Created morning card template: {template_id}")
            
            return {
                'status': 'success',
                'message': 'Card template created successfully',
                'template_id': template_id
            }
        except Exception as e:
            return handle_exception(e, "Failed to create card template")
    
    def update_card_template(self, card_id: str, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Update card template"""
        try:
            doc_ref = self.db.collection('morning_card_templates').document(card_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Card template not found'
                }
            
            # Verify ownership: allow if user owns card OR user is card owner's spouse
            doc_data = doc.to_dict()
            card_owner = doc_data.get('username')
            
            # Get spouse username from database
            from src.utils.config import get_spouse
            spouse_username = get_spouse(username)
            
            # Allow if current user is owner, or current user is owner's spouse
            if card_owner != username and card_owner != spouse_username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Card belongs to another user'
                }
            
            # Validate and prepare update data
            update_data = {'updated_at': firestore.SERVER_TIMESTAMP}
            
            if 'card_text' in data:
                update_data['card_text'] = data['card_text'].strip()
            if 'clothes_points' in data:
                update_data['clothes_points'] = int(data['clothes_points'])
            if 'timer_minutes' in data:
                update_data['timer_minutes'] = int(data['timer_minutes'])
            if 'user_rules' in data:
                user_rules = data['user_rules'] or {}
                if not isinstance(user_rules, dict):
                    user_rules = {}
                
                # Validate and clean user_rules
                # Keep as generic keys ('mine', 'spouse') for storage
                cleaned_user_rules = {}
                for rule_key, rules in user_rules.items():
                    if isinstance(rules, list):
                        cleaned_rules = [r.strip() for r in rules if r and r.strip()]
                        if cleaned_rules:  # Only include non-empty rule lists
                            cleaned_user_rules[rule_key] = cleaned_rules
                
                update_data['user_rules'] = cleaned_user_rules
            if 'active' in data:
                update_data['active'] = bool(data['active'])
            
            doc_ref.update(update_data)
            
            self.logger.info(f"Updated morning card template: {card_id}")
            
            return {
                'status': 'success',
                'message': 'Card template updated successfully'
            }
        except Exception as e:
            return handle_exception(e, f"Failed to update card template {card_id}")
    
    def delete_card_template(self, card_id: str, username: str) -> Dict[str, Any]:
        """Delete card template"""
        try:
            doc_ref = self.db.collection('morning_card_templates').document(card_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Card template not found'
                }
            
            # Verify ownership: allow if user owns card OR user is card owner's spouse
            doc_data = doc.to_dict()
            card_owner = doc_data.get('username')
            
            # Get spouse username from database
            from src.utils.config import get_spouse
            spouse_username = get_spouse(username)
            
            # Allow if current user is owner, or current user is owner's spouse
            if card_owner != username and card_owner != spouse_username:
                return {
                    'status': 'error',
                    'message': 'Unauthorized: Card belongs to another user'
                }
            
            # Delete template
            doc_ref.delete()
            
            self.logger.info(f"Deleted morning card template: {card_id}")
            
            return {
                'status': 'success',
                'message': 'Card template deleted successfully'
            }
        except Exception as e:
            return handle_exception(e, f"Failed to delete card template {card_id}")
    
    def get_todays_selection(self) -> Dict[str, Any]:
        """Get today's card selection"""
        try:
            # First check if reset is needed
            self.check_and_reset_cards()
            
            # Get today's date in Central time
            today_central = datetime.now(self.central_tz).date()
            
            # Query today's selection
            selection_query = self.db.collection('morning_card_selections').where(
                filter=FieldFilter('date', '==', today_central.isoformat())
            ).limit(1)
            
            selection_docs = list(selection_query.stream())
            
            if selection_docs:
                selection_data = prepare_firestore_document(selection_docs[0])
                
                return {
                    'status': 'success',
                    'selection': selection_data
                }
            else:
                # Create new selection for today
                selection_data = {
                    'date': today_central.isoformat(),
                    'selected_card_ids': [],
                    'collaboration_score': 0,
                    'total_clothes_points': 0,
                    'total_timer_minutes': 0,
                    'user_rules': {},
                    'locked': False,
                    'created_at': firestore.SERVER_TIMESTAMP
                }
                
                doc_ref = self.db.collection('morning_card_selections').add(selection_data)
                selection_data['id'] = doc_ref[1].id
                
                self.logger.info(f"Created new selection for {today_central}")
                
                return {
                    'status': 'success',
                    'selection': selection_data
                }
        except Exception as e:
            return handle_exception(e, "Failed to get today's selection")
    
    def select_cards(self, card_ids: List[str], username: str) -> Dict[str, Any]:
        """Lock in card selection"""
        try:
            # Check if user has permission to select morning cards
            user_ref = self.db.collection('users').document(username)
            user_doc = user_ref.get()
            
            can_select = False
            if user_doc.exists:
                user_data = user_doc.to_dict()
                can_select = user_data.get('can_select_morning_cards', False)
            
            if not can_select:
                return {
                    'status': 'error',
                    'message': 'You do not have permission to select morning cards'
                }
            
            # Validate input
            if not card_ids or not isinstance(card_ids, list):
                return {
                    'status': 'error',
                    'message': 'Invalid card IDs provided'
                }
            
            # Get today's selection
            result = self.get_todays_selection()
            if result['status'] != 'success':
                return result
            
            selection = result['selection']
            
            # Check if already locked
            if selection.get('locked', False):
                return {
                    'status': 'error',
                    'message': 'Cards are already locked for today'
                }
            
            # Get collaboration score
            from src.services.collaboration_service import CollaborationService
            collab_service = CollaborationService(self.app_manager)
            tracker_result = collab_service.get_or_create_tracker()
            
            if not tracker_result:
                return {
                    'status': 'error',
                    'message': 'Failed to get collaboration tracker'
                }
            
            collaboration_score = tracker_result['current_value']
            
            # Validate number of cards selected
            if len(card_ids) != collaboration_score:
                return {
                    'status': 'error',
                    'message': f'Must select exactly {collaboration_score} cards (current collaboration score)'
                }
            
            # Fetch all selected cards
            selected_cards = []
            total_clothes = 0
            total_timer = 0
            all_user_rules = {}
            
            for card_id in card_ids:
                card_doc = self.db.collection('morning_card_templates').document(card_id).get()
                if not card_doc.exists:
                    return {
                        'status': 'error',
                        'message': f'Card {card_id} not found'
                    }
                
                card_data = card_doc.to_dict()
                if not card_data.get('active', True):
                    return {
                        'status': 'error',
                        'message': f'Card {card_id} is not active'
                    }
                
                # Convert generic rules to actual usernames for aggregation
                card_owner = card_data.get('username')
                card_user_rules = card_data.get('user_rules', {})
                if card_owner:
                    card_user_rules = self._convert_generic_rules_to_usernames(card_user_rules, card_owner)
                
                selected_cards.append({
                    'id': card_id,
                    'card_text': card_data.get('card_text', ''),
                    'clothes_points': card_data.get('clothes_points', 0),
                    'timer_minutes': card_data.get('timer_minutes', 0),
                    'user_rules': card_user_rules
                })
                
                total_clothes += card_data.get('clothes_points', 0)
                total_timer += card_data.get('timer_minutes', 0)
                
                # Aggregate user_rules from card (now with actual usernames)
                if isinstance(card_user_rules, dict):
                    for username, rules in card_user_rules.items():
                        if username not in all_user_rules:
                            all_user_rules[username] = []
                        if isinstance(rules, list):
                            all_user_rules[username].extend(rules)
            
            # Calculate final timer: base (20) - 2 per card + card adjustments
            base_timer = 20
            timer_deduction = len(card_ids) * 2
            final_timer = base_timer - timer_deduction + total_timer
            
            # Calculate final clothes: base (1) + card adjustments
            base_clothes = 1
            final_clothes = base_clothes + total_clothes
            
            # Update selection
            selection_doc = self.db.collection('morning_card_selections').document(selection['id'])
            selection_doc.update({
                'selected_card_ids': card_ids,
                'collaboration_score': collaboration_score,
                'total_clothes_points': final_clothes,
                'total_timer_minutes': final_timer,
                'user_rules': all_user_rules,
                'locked': True
            })
            
            self.logger.info(f"Locked {len(card_ids)} cards for {datetime.now(self.central_tz).date()}")
            
            return {
                'status': 'success',
                'message': f'Successfully locked {len(card_ids)} cards',
                'selection': {
                    'selected_card_ids': card_ids,
                    'collaboration_score': collaboration_score,
                    'total_clothes_points': final_clothes,
                    'total_timer_minutes': final_timer,
                    'user_rules': all_user_rules,
                    'locked': True
                }
            }
        except Exception as e:
            return handle_exception(e, "Failed to select cards")
    
    def check_and_reset_cards(self) -> Dict[str, Any]:
        """Check and reset cards after 2am"""
        try:
            now_central = datetime.now(self.central_tz)
            today_central = now_central.date()
            
            # Check if there's already a selection for today
            selection_query = self.db.collection('morning_card_selections').where(
                filter=FieldFilter('date', '==', today_central.isoformat())
            ).limit(1)
            
            selection_docs = list(selection_query.stream())
            
            if selection_docs:
                # Already have a selection for today
                return {'status': 'success', 'message': 'Already reset today'}
            
            # Check if it's past 2am today
            reset_time_today = datetime.combine(today_central, datetime.min.time().replace(hour=2))
            reset_time_today = self.central_tz.localize(reset_time_today)
            
            if now_central < reset_time_today:
                # Not yet 2am today, check if we need to reset from yesterday
                yesterday_central = today_central - timedelta(days=1)
                yesterday_query = self.db.collection('morning_card_selections').where(
                    filter=FieldFilter('date', '==', yesterday_central.isoformat())
                ).limit(1)
                
                yesterday_docs = list(yesterday_query.stream())
                
                if yesterday_docs:
                    # Reset yesterday, no need to reset today yet
                    return {'status': 'success', 'message': 'Reset not needed yet'}
            
            # Need to reset - delete old selections
            self.logger.info(f"Resetting morning cards for {today_central}")
            
            # Delete all selections older than today
            old_selections_query = self.db.collection('morning_card_selections').where(
                filter=FieldFilter('date', '<', today_central.isoformat())
            )
            
            deleted_count = 0
            for doc in old_selections_query.stream():
                doc.reference.delete()
                deleted_count += 1
            
            self.logger.info(f"Deleted {deleted_count} old morning card selections")
            
            return {
                'status': 'success',
                'message': f'Reset completed, deleted {deleted_count} old selections'
            }
        except Exception as e:
            return handle_exception(e, "Failed to reset morning cards")
    
    def unlock_todays_selection(self) -> Dict[str, Any]:
        """Unlock today's selection for testing (doesn't delete the selection, just unlocks it)"""
        try:
            today_central = datetime.now(self.central_tz).date()
            
            # Find today's selection
            selection_query = self.db.collection('morning_card_selections').where(
                filter=FieldFilter('date', '==', today_central.isoformat())
            ).limit(1)
            
            selection_docs = list(selection_query.stream())
            
            if not selection_docs:
                return {
                    'status': 'error',
                    'message': 'No selection found for today'
                }
            
            # Unlock the selection
            selection_doc = selection_docs[0]
            selection_doc.reference.update({
                'locked': False,
                'selected_card_ids': [],
                'total_clothes_points': 0,
                'total_timer_minutes': 0,
                'user_rules': {}
            })
            
            self.logger.info(f"Unlocked morning card selection for {today_central}")
            
            return {
                'status': 'success',
                'message': 'Selection unlocked successfully'
            }
        except Exception as e:
            return handle_exception(e, "Failed to unlock selection")

