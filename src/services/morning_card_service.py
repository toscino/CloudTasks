"""
Morning Card Service - handles morning card templates and daily selections
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta
import pytz
import random
from src.utils.logger import logger
from typing import List, Dict, Any


class MorningCardService:
    """Service for morning card operations"""
    
    def __init__(self, db):
        self.db = db
        self.central_tz = pytz.timezone('America/Chicago')  # Central time
    
    def get_card_templates(self) -> Dict[str, Any]:
        """Get all card templates"""
        try:
            templates_query = self.db.collection('morning_card_templates')
            templates_docs = templates_query.stream()
            
            templates = []
            for doc in templates_docs:
                template_data = doc.to_dict()
                template_data['id'] = doc.id
                
                # Convert timestamps
                if 'created_at' in template_data and hasattr(template_data['created_at'], 'timestamp'):
                    template_data['created_at'] = datetime.fromtimestamp(template_data['created_at'].timestamp())
                if 'updated_at' in template_data and hasattr(template_data['updated_at'], 'timestamp'):
                    template_data['updated_at'] = datetime.fromtimestamp(template_data['updated_at'].timestamp())
                
                templates.append(template_data)
            
            return {
                'status': 'success',
                'templates': templates
            }
        except Exception as e:
            logger.error(f"Failed to get card templates: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get card templates: {str(e)}'
            }
    
    def create_card_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new card template"""
        try:
            if not data or not data.get('card_text'):
                return {'status': 'error', 'message': 'Card text is required'}
            
            # Validate and prepare data
            card_text = data['card_text'].strip()
            clothes_points = int(data.get('clothes_points', 0))
            timer_minutes = int(data.get('timer_minutes', 0))
            ian_rules = data.get('ian_rules', []) or []
            karleigh_rules = data.get('karleigh_rules', []) or []
            active = data.get('active', True)
            
            # Ensure rules are arrays
            if not isinstance(ian_rules, list):
                ian_rules = []
            if not isinstance(karleigh_rules, list):
                karleigh_rules = []
            
            # Filter out empty rules
            ian_rules = [r.strip() for r in ian_rules if r and r.strip()]
            karleigh_rules = [r.strip() for r in karleigh_rules if r and r.strip()]
            
            # Create template data
            template_data = {
                'card_text': card_text,
                'clothes_points': clothes_points,
                'timer_minutes': timer_minutes,
                'ian_rules': ian_rules,
                'karleigh_rules': karleigh_rules,
                'active': active,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Create new template in Firestore
            doc_ref = self.db.collection('morning_card_templates').add(template_data)
            template_id = doc_ref[1].id
            
            logger.info(f"Created morning card template: {template_id}")
            
            return {
                'status': 'success',
                'message': 'Card template created successfully',
                'template_id': template_id
            }
        except Exception as e:
            logger.error(f"Failed to create card template: {e}")
            return {
                'status': 'error',
                'message': f'Failed to create card template: {str(e)}'
            }
    
    def update_card_template(self, card_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing card template"""
        try:
            doc_ref = self.db.collection('morning_card_templates').document(card_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Card template not found'
                }
            
            # Validate and prepare update data
            update_data = {'updated_at': firestore.SERVER_TIMESTAMP}
            
            if 'card_text' in data:
                update_data['card_text'] = data['card_text'].strip()
            if 'clothes_points' in data:
                update_data['clothes_points'] = int(data['clothes_points'])
            if 'timer_minutes' in data:
                update_data['timer_minutes'] = int(data['timer_minutes'])
            if 'ian_rules' in data:
                ian_rules = data['ian_rules'] or []
                if not isinstance(ian_rules, list):
                    ian_rules = []
                update_data['ian_rules'] = [r.strip() for r in ian_rules if r and r.strip()]
            if 'karleigh_rules' in data:
                karleigh_rules = data['karleigh_rules'] or []
                if not isinstance(karleigh_rules, list):
                    karleigh_rules = []
                update_data['karleigh_rules'] = [r.strip() for r in karleigh_rules if r and r.strip()]
            if 'active' in data:
                update_data['active'] = bool(data['active'])
            
            doc_ref.update(update_data)
            
            logger.info(f"Updated morning card template: {card_id}")
            
            return {
                'status': 'success',
                'message': 'Card template updated successfully'
            }
        except Exception as e:
            logger.error(f"Failed to update card template {card_id}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to update card template: {str(e)}'
            }
    
    def delete_card_template(self, card_id: str) -> Dict[str, Any]:
        """Delete a card template"""
        try:
            doc_ref = self.db.collection('morning_card_templates').document(card_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'status': 'error',
                    'message': 'Card template not found'
                }
            
            # Delete template
            doc_ref.delete()
            
            logger.info(f"Deleted morning card template: {card_id}")
            
            return {
                'status': 'success',
                'message': 'Card template deleted successfully'
            }
        except Exception as e:
            logger.error(f"Failed to delete card template {card_id}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to delete card template: {str(e)}'
            }
    
    def get_todays_selection(self) -> Dict[str, Any]:
        """Get today's card selection (creates if needed)"""
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
                selection_data = selection_docs[0].to_dict()
                selection_data['id'] = selection_docs[0].id
                
                # Convert timestamps
                if 'created_at' in selection_data and hasattr(selection_data['created_at'], 'timestamp'):
                    selection_data['created_at'] = datetime.fromtimestamp(selection_data['created_at'].timestamp())
                
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
                    'ian_rules': [],
                    'karleigh_rules': [],
                    'locked': False,
                    'created_at': firestore.SERVER_TIMESTAMP
                }
                
                doc_ref = self.db.collection('morning_card_selections').add(selection_data)
                selection_data['id'] = doc_ref[1].id
                
                logger.info(f"Created new selection for {today_central}")
                
                return {
                    'status': 'success',
                    'selection': selection_data
                }
        except Exception as e:
            logger.error(f"Failed to get today's selection: {e}")
            return {
                'status': 'error',
                'message': f'Failed to get today\'s selection: {str(e)}'
            }
    
    def select_cards(self, card_ids: List[str], username: str) -> Dict[str, Any]:
        """Lock in card selection (Karleigh only)"""
        try:
            # Enforce Karleigh-only restriction
            if username != 'Karleigh':
                return {
                    'status': 'error',
                    'message': 'Only Karleigh can select morning cards'
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
            collab_service = CollaborationService(self.db)
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
            all_ian_rules = []
            all_karleigh_rules = []
            
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
                
                selected_cards.append({
                    'id': card_id,
                    'card_text': card_data.get('card_text', ''),
                    'clothes_points': card_data.get('clothes_points', 0),
                    'timer_minutes': card_data.get('timer_minutes', 0),
                    'ian_rules': card_data.get('ian_rules', []),
                    'karleigh_rules': card_data.get('karleigh_rules', [])
                })
                
                total_clothes += card_data.get('clothes_points', 0)
                total_timer += card_data.get('timer_minutes', 0)
                all_ian_rules.extend(card_data.get('ian_rules', []))
                all_karleigh_rules.extend(card_data.get('karleigh_rules', []))
            
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
                'ian_rules': all_ian_rules,
                'karleigh_rules': all_karleigh_rules,
                'locked': True
            })
            
            logger.info(f"Locked {len(card_ids)} cards for {datetime.now(self.central_tz).date()}")
            
            return {
                'status': 'success',
                'message': f'Successfully locked {len(card_ids)} cards',
                'selection': {
                    'selected_card_ids': card_ids,
                    'collaboration_score': collaboration_score,
                    'total_clothes_points': final_clothes,
                    'total_timer_minutes': final_timer,
                    'ian_rules': all_ian_rules,
                    'karleigh_rules': all_karleigh_rules,
                    'locked': True
                }
            }
        except Exception as e:
            logger.error(f"Failed to select cards: {e}")
            return {
                'status': 'error',
                'message': f'Failed to select cards: {str(e)}'
            }
    
    def check_and_reset_cards(self) -> Dict[str, Any]:
        """Check if card selections need to be reset (lazy reset after 2am)"""
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
            logger.info(f"Resetting morning cards for {today_central}")
            
            # Delete all selections older than today
            old_selections_query = self.db.collection('morning_card_selections').where(
                filter=FieldFilter('date', '<', today_central.isoformat())
            )
            
            deleted_count = 0
            for doc in old_selections_query.stream():
                doc.reference.delete()
                deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} old morning card selections")
            
            return {
                'status': 'success',
                'message': f'Reset completed, deleted {deleted_count} old selections'
            }
        except Exception as e:
            logger.error(f"Failed to reset morning cards: {e}")
            return {
                'status': 'error',
                'message': f'Failed to reset morning cards: {str(e)}'
            }
    
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
                'ian_rules': [],
                'karleigh_rules': []
            })
            
            logger.info(f"Unlocked morning card selection for {today_central}")
            
            return {
                'status': 'success',
                'message': 'Selection unlocked successfully'
            }
        except Exception as e:
            logger.error(f"Failed to unlock selection: {e}")
            return {
                'status': 'error',
                'message': f'Failed to unlock selection: {str(e)}'
            }

