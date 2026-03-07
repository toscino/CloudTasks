"""
Dice Roll Service - manages dice roll credits and game events
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime, date, timedelta
import random
from src.utils.config import get_timezone, DEFAULT_DICE_ROLL_CREDIT_CAP
from src.utils.firestore_helpers import prepare_firestore_document
from src.utils.error_handlers import handle_exception
from typing import List, Dict, Any, Optional


class DiceRollService:
    """Service for dice roll operations"""
    
    DEFAULT_CREDIT_CAP = DEFAULT_DICE_ROLL_CREDIT_CAP
    
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()
    
    def get_couple_id(self, username: str) -> Optional[str]:
        """Get couple identifier (sorted usernames)"""
        try:
            user_ref = self.db.collection('users').document(username)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                return None
            
            user_data = user_doc.to_dict()
            spouse_username = user_data.get('spouse_username')
            
            if not spouse_username:
                # Single user - use their username as couple_id
                return username
            
            # Create sorted couple_id
            usernames = sorted([username, spouse_username])
            return '_'.join(usernames)
        except Exception as e:
            self.logger.error(f"Failed to get couple_id for {username}: {e}")
            return None
    
    def get_or_create_credits(self, couple_id: str) -> Dict[str, Any]:
        """Get or create credits document for couple"""
        try:
            credits_ref = self.db.collection('dice_roll_credits').document(couple_id)
            credits_doc = credits_ref.get()
            
            if credits_doc.exists:
                credits_data = prepare_firestore_document(credits_doc)
                return credits_data
            
            # Create new credits document
            credits_data = {
                'couple_id': couple_id,
                'total_credits': 0,
                'credit_cap': self.DEFAULT_CREDIT_CAP,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            credits_ref.set(credits_data)
            self.logger.info(f"Created credits document for couple: {couple_id}")
            
            # Return with defaults
            credits_data['total_credits'] = 0
            credits_data['credit_cap'] = self.DEFAULT_CREDIT_CAP
            return credits_data
        except Exception as e:
            self.logger.error(f"Failed to get/create credits for {couple_id}: {e}")
            return {
                'couple_id': couple_id,
                'total_credits': 0,
                'credit_cap': self.DEFAULT_CREDIT_CAP
            }
    
    def _default_dice_configs(self) -> Dict[str, Any]:
        """Default dice config (die_1-die_4: title, base_rule, alternate_rule, face_rules, face_names)"""
        return {
            f'die_{i}': {
                'title': '',
                'base_rule': '',
                'alternate_rule': '',
                'face_rules': {str(f): '' for f in range(1, 7)},
                'face_names': {str(f): '' for f in range(1, 7)}
            }
            for i in range(1, 5)
        }
    
    def get_dice_configuration(self, couple_id: str, username: Optional[str] = None) -> Dict[str, Any]:
        """Get dice configuration for couple (create default if missing). If username given, also return saved_dice_selection, can_save_selection, can_roll."""
        try:
            config_ref = self.db.collection('dice_configurations').document(couple_id)
            config_doc = config_ref.get()
            
            # Normalize saved_dice_selection: list of ints 0-3, length 0-3, no duplicates
            def normalize_saved_selection(raw):
                if not isinstance(raw, list):
                    return []
                out = []
                seen = set()
                for x in raw:
                    try:
                        i = int(x)
                        if 0 <= i <= 3 and i not in seen:
                            out.append(i)
                            seen.add(i)
                    except (TypeError, ValueError):
                        continue
                    if len(out) >= 3:
                        break
                return out

            if config_doc.exists:
                data = prepare_firestore_document(config_doc)
                dice_configs = data.get('dice_configs') or {}
                # Ensure full shape: die_1-die_4 with title, base_rule, alternate_rule, face_rules, face_names
                defaults = self._default_dice_configs()
                for key in defaults:
                    d = dice_configs.get(key) or {}
                    title = (d.get('title') or '').strip() if d.get('title') is not None else ''
                    base = (d.get('base_rule') or '').strip() if d.get('base_rule') is not None else ''
                    alt = (d.get('alternate_rule') or '').strip() if d.get('alternate_rule') is not None else ''
                    fr = d.get('face_rules')
                    if not isinstance(fr, dict):
                        fr = {str(f): '' for f in range(1, 7)}
                    else:
                        fr = {str(f): (fr.get(str(f)) or '').strip() if fr.get(str(f)) is not None else '' for f in range(1, 7)}
                    fn = d.get('face_names')
                    if not isinstance(fn, dict):
                        fn = {str(f): '' for f in range(1, 7)}
                    else:
                        fn = {str(f): (fn.get(str(f)) or '').strip() if fn.get(str(f)) is not None else '' for f in range(1, 7)}
                    dice_configs[key] = {'title': title, 'base_rule': base, 'alternate_rule': alt, 'face_rules': fr, 'face_names': fn}
                generic = (data.get('generic_base_rule') or '').strip() if data.get('generic_base_rule') is not None else ''
                full_roll = (data.get('full_roll_rule') or '').strip() if data.get('full_roll_rule') is not None else ''
                saved = normalize_saved_selection(data.get('saved_dice_selection'))
                result = {'status': 'success', 'dice_configs': dice_configs, 'generic_base_rule': generic, 'full_roll_rule': full_roll, 'updated_at': data.get('updated_at'), 'saved_dice_selection': saved}
            else:
                result = {'status': 'success', 'dice_configs': self._default_dice_configs(), 'generic_base_rule': '', 'full_roll_rule': '', 'updated_at': None, 'saved_dice_selection': []}

            if username:
                user_ref = self.db.collection('users').document(username)
                user_doc = user_ref.get()
                can_roll = user_doc.to_dict().get('can_select_morning_cards', False) if user_doc.exists else False
                result['can_roll'] = can_roll
                result['can_save_selection'] = not can_roll
            return result
        except Exception as e:
            self.logger.error(f"Failed to get dice config for {couple_id}: {e}")
            return {'status': 'error', 'message': str(e), 'dice_configs': self._default_dice_configs()}
    
    def save_dice_configuration(self, couple_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Save dice configuration for couple (dice_configs, generic_base_rule, full_roll_rule)"""
        try:
            dice_configs = body.get('dice_configs') or {}
            generic_base = str(body.get('generic_base_rule') or '').strip()
            full_roll = str(body.get('full_roll_rule') or '').strip()
            # Normalize: die_1-die_4 with title, base_rule, alternate_rule, face_rules, face_names
            normalized = {}
            for i in range(1, 5):
                key = f'die_{i}'
                d = dice_configs.get(key) or {}
                title = str(d.get('title') or '').strip()
                base = str(d.get('base_rule') or '').strip()
                alt = str(d.get('alternate_rule') or '').strip()
                fr = d.get('face_rules')
                if not isinstance(fr, dict):
                    fr = {str(f): '' for f in range(1, 7)}
                else:
                    fr = {str(f): str(fr.get(str(f)) or '').strip() for f in range(1, 7)}
                fn = d.get('face_names')
                if not isinstance(fn, dict):
                    fn = {str(f): '' for f in range(1, 7)}
                else:
                    fn = {str(f): str(fn.get(str(f)) or '').strip() for f in range(1, 7)}
                normalized[key] = {'title': title, 'base_rule': base, 'alternate_rule': alt, 'face_rules': fr, 'face_names': fn}
            
            config_ref = self.db.collection('dice_configurations').document(couple_id)
            config_ref.set({
                'couple_id': couple_id,
                'dice_configs': normalized,
                'generic_base_rule': generic_base,
                'full_roll_rule': full_roll,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            return {'status': 'success', 'dice_configs': normalized, 'generic_base_rule': generic_base, 'full_roll_rule': full_roll}
        except Exception as e:
            self.logger.error(f"Failed to save dice config for {couple_id}: {e}")
            return handle_exception(e, "Failed to save dice configuration")
    
    def save_saved_dice_selection(self, username: str, saved_dice_selection: List[int]) -> Dict[str, Any]:
        """Save which dice are selected for the couple. Allowed only when can_select_morning_cards is False."""
        try:
            user_ref = self.db.collection('users').document(username)
            user_doc = user_ref.get()
            if not user_doc.exists:
                return {'status': 'error', 'message': 'User not found'}
            can_select = user_doc.to_dict().get('can_select_morning_cards', False)
            if can_select:
                return {'status': 'error', 'message': 'Only the non–morning-card person can save the dice selection'}
            if not isinstance(saved_dice_selection, list):
                return {'status': 'error', 'message': 'saved_dice_selection must be a list'}
            if len(saved_dice_selection) > 3:
                return {'status': 'error', 'message': 'At most 3 dice can be selected'}
            seen = set()
            for x in saved_dice_selection:
                try:
                    i = int(x)
                    if i < 0 or i > 3:
                        return {'status': 'error', 'message': f'Invalid die index: {i}'}
                    if i in seen:
                        return {'status': 'error', 'message': 'Duplicate die index'}
                    seen.add(i)
                except (TypeError, ValueError):
                    return {'status': 'error', 'message': f'Invalid die index: {x}'}
            normalized = sorted(seen)
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id'}
            config_ref = self.db.collection('dice_configurations').document(couple_id)
            config_ref.set({'saved_dice_selection': normalized, 'updated_at': firestore.SERVER_TIMESTAMP}, merge=True)
            return {'status': 'success', 'message': 'Selection saved', 'saved_dice_selection': normalized}
        except Exception as e:
            self.logger.error(f"Failed to save dice selection for {username}: {e}")
            return handle_exception(e, "Failed to save dice selection")
    
    def _normalize_one_die(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single die config (full replace; empty stays empty)."""
        title = str(d.get('title') or '').strip()
        base = str(d.get('base_rule') or '').strip()
        alt = str(d.get('alternate_rule') or '').strip()
        fr = d.get('face_rules')
        if not isinstance(fr, dict):
            fr = {str(f): '' for f in range(1, 7)}
        else:
            fr = {str(f): str(fr.get(str(f)) or '').strip() for f in range(1, 7)}
        fn = d.get('face_names')
        if not isinstance(fn, dict):
            fn = {str(f): '' for f in range(1, 7)}
        else:
            fn = {str(f): str(fn.get(str(f)) or '').strip() for f in range(1, 7)}
        return {'title': title, 'base_rule': base, 'alternate_rule': alt, 'face_rules': fr, 'face_names': fn}
    
    def import_dice_configuration(self, couple_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Import (partial) dice config. For each die present, full replace that die; empty fields stay empty. Optional generic_base_rule, full_roll_rule replace if provided. Validate before any write."""
        try:
            if not isinstance(body, dict):
                return {'status': 'error', 'message': 'Import payload must be a JSON object'}
            dice_configs_in = body.get('dice_configs')
            if dice_configs_in is not None and not isinstance(dice_configs_in, dict):
                return {'status': 'error', 'message': 'dice_configs must be an object'}
            valid_die_keys = {f'die_{i}' for i in range(1, 5)}
            if dice_configs_in:
                for key in dice_configs_in:
                    if key not in valid_die_keys:
                        return {'status': 'error', 'message': f'Invalid key "{key}": must be die_1, die_2, die_3, or die_4'}
                    d = dice_configs_in[key]
                    if not isinstance(d, dict):
                        return {'status': 'error', 'message': f'dice_configs.{key} must be an object'}
                    # Validate shape: title, base_rule, alternate_rule, face_rules (1-6), face_names (1-6)
                    for f in range(1, 7):
                        if d.get('face_rules') is not None and not isinstance(d.get('face_rules'), dict):
                            return {'status': 'error', 'message': f'dice_configs.{key}.face_rules must be an object with keys "1"-"6"'}
                        if d.get('face_names') is not None and not isinstance(d.get('face_names'), dict):
                            return {'status': 'error', 'message': f'dice_configs.{key}.face_names must be an object with keys "1"-"6"'}
            
            # Get current config and build merged (full replace per die present)
            current = self.get_dice_configuration(couple_id)
            if current.get('status') != 'success':
                return current
            merged_configs = dict(current.get('dice_configs') or self._default_dice_configs())
            merged_generic = (body.get('generic_base_rule') if 'generic_base_rule' in body else current.get('generic_base_rule')) or ''
            merged_full_roll = (body.get('full_roll_rule') if 'full_roll_rule' in body else current.get('full_roll_rule')) or ''
            if isinstance(merged_generic, str):
                merged_generic = merged_generic.strip()
            if isinstance(merged_full_roll, str):
                merged_full_roll = merged_full_roll.strip()
            if dice_configs_in:
                for key in valid_die_keys:
                    if key in dice_configs_in:
                        merged_configs[key] = self._normalize_one_die(dice_configs_in[key])
            
            return self.save_dice_configuration(couple_id, {
                'dice_configs': merged_configs,
                'generic_base_rule': merged_generic,
                'full_roll_rule': merged_full_roll
            })
        except Exception as e:
            self.logger.error(f"Failed to import dice config for {couple_id}: {e}")
            return handle_exception(e, "Failed to import dice configuration")
    
    def get_credits(self, username: str) -> Dict[str, Any]:
        """Get current shared credit balance and cap (both users can view)"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {
                    'status': 'error',
                    'message': 'Could not determine couple_id'
                }
            
            credits_data = self.get_or_create_credits(couple_id)
            
            return {
                'status': 'success',
                'total_credits': credits_data.get('total_credits', 0),
                'credit_cap': credits_data.get('credit_cap', self.DEFAULT_CREDIT_CAP),
                'couple_id': couple_id
            }
        except Exception as e:
            return handle_exception(e, "Failed to get credits")
    
    def add_credits_from_morning_cards(self, username: str) -> Dict[str, Any]:
        """Add earned credits immediately when cards locked"""
        try:
            # Get today's morning card selection
            today_central = datetime.now(self.central_tz).date()
            selection_query = self.db.collection('morning_card_selections').where(
                filter=FieldFilter('date', '==', today_central.isoformat())
            ).limit(1)
            
            selection_docs = list(selection_query.stream())
            if not selection_docs:
                return {
                    'status': 'error',
                    'message': 'No morning card selection found for today'
                }
            
            selection_data = prepare_firestore_document(selection_docs[0])
            earned_dice_rolls = selection_data.get('total_dice_rolls', 0.0)
            
            if earned_dice_rolls <= 0:
                return {
                    'status': 'success',
                    'message': 'No dice rolls earned today',
                    'credits_added': 0
                }
            
            # Round to whole number
            credits_to_add = int(round(earned_dice_rolls))
            
            if credits_to_add == 0:
                return {
                    'status': 'success',
                    'message': 'Earned dice rolls rounded to 0',
                    'credits_added': 0
                }
            
            # Get couple_id and credits
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {
                    'status': 'error',
                    'message': 'Could not determine couple_id'
                }
            
            credits_ref = self.db.collection('dice_roll_credits').document(couple_id)
            credits_doc = credits_ref.get()
            
            if not credits_doc.exists:
                # Create if doesn't exist
                self.get_or_create_credits(couple_id)
            
            # Get current credits and cap
            current_credits = credits_doc.to_dict().get('total_credits', 0) if credits_doc.exists else 0
            credit_cap = credits_doc.to_dict().get('credit_cap', self.DEFAULT_CREDIT_CAP) if credits_doc.exists else self.DEFAULT_CREDIT_CAP
            
            # Add credits with cap
            new_total = min(current_credits + credits_to_add, credit_cap)
            actual_added = new_total - current_credits
            
            # Update credits
            credits_ref.update({
                'total_credits': new_total,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Log transaction
            transaction_data = {
                'couple_id': couple_id,
                'date': today_central.isoformat(),
                'type': 'earned',
                'amount': float(actual_added),
                'source': 'morning_cards',
                'username': username,
                'earned_float': earned_dice_rolls,
                'rounded': credits_to_add,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            self.db.collection('dice_credit_transactions').add(transaction_data)
            
            self.logger.info(f"Added {actual_added} credits to couple {couple_id} from morning cards (earned: {earned_dice_rolls}, rounded: {credits_to_add})")
            
            return {
                'status': 'success',
                'message': f'Added {actual_added} credits',
                'credits_added': actual_added,
                'earned_float': earned_dice_rolls,
                'rounded': credits_to_add,
                'total_credits': new_total,
                'credit_cap': credit_cap
            }
        except Exception as e:
            return handle_exception(e, "Failed to add credits from morning cards")
    
    def roll_dice(self, username: str, dice_selected: List[int]) -> Dict[str, Any]:
        """Roll selected dice, apply configured rules, deduct credits"""
        try:
            # Check user has permission
            user_ref = self.db.collection('users').document(username)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                return {
                    'status': 'error',
                    'message': 'User not found'
                }
            
            user_data = user_doc.to_dict()
            can_select = user_data.get('can_select_morning_cards', False)
            
            if not can_select:
                return {
                    'status': 'error',
                    'message': 'You do not have permission to roll dice'
                }
            
            # Roller uses saved_dice_selection from config (ignore request body)
            couple_id = self.get_couple_id(username)
            if not couple_id or not isinstance(couple_id, str) or couple_id.strip() == '':
                return {
                    'status': 'error',
                    'message': 'Could not determine couple_id'
                }
            config_result = self.get_dice_configuration(couple_id)
            if config_result.get('status') != 'success':
                return config_result
            saved = config_result.get('saved_dice_selection') or []
            if not isinstance(saved, list):
                saved = []
            # Normalize: ints 0-3, max 3, no duplicates
            dice_selected = []
            seen = set()
            for x in saved:
                try:
                    i = int(x)
                    if 0 <= i <= 3 and i not in seen:
                        dice_selected.append(i)
                        seen.add(i)
                    if len(dice_selected) >= 3:
                        break
                except (TypeError, ValueError):
                    continue
            
            # Calculate credits needed
            credits_needed = 1 + len(dice_selected)  # Base + per die
            
            # Get couple_id and check credits
            couple_id = self.get_couple_id(username)
            if not couple_id or not isinstance(couple_id, str) or couple_id.strip() == '':
                return {
                    'status': 'error',
                    'message': 'Could not determine couple_id'
                }
            
            # Ensure username is valid
            if not username or not isinstance(username, str) or username.strip() == '':
                return {
                    'status': 'error',
                    'message': 'Invalid username'
                }
            
            credits_data = self.get_or_create_credits(couple_id)
            current_credits = credits_data.get('total_credits', 0)
            
            if current_credits < credits_needed:
                return {
                    'status': 'error',
                    'message': f'Insufficient credits. Need {credits_needed}, have {current_credits}'
                }
            
            # Get dice configuration
            config_result = self.get_dice_configuration(couple_id)
            dice_configs = config_result.get('dice_configs') or self._default_dice_configs()
            generic_base = (config_result.get('generic_base_rule') or '').strip()
            full_roll = (config_result.get('full_roll_rule') or '').strip()
            
            # Roll dice
            dice_results = {}
            for die_idx in dice_selected:
                face_value = random.randint(1, 6)
                dice_results[str(die_idx)] = face_value
            
            # Build final_rules and rules_detail (alternate + face on separate lines for display)
            # - Not selected: base_rule only. Selected: alternate_rule and face_rule separately.
            final_rules = {}
            rules_detail = {}
            for rule_idx in range(1, 5):
                die_idx = rule_idx - 1
                cfg = dice_configs.get(f'die_{rule_idx}') or {}
                base = (cfg.get('base_rule') or '').strip()
                alt = (cfg.get('alternate_rule') or '').strip()
                face_rules_map = cfg.get('face_rules') or {}
                rule_key = f'rule_{rule_idx}'
                if die_idx in dice_selected:
                    face_value = dice_results.get(str(die_idx), 1)
                    face_rule = (face_rules_map.get(str(face_value)) or '').strip()
                    parts = [p for p in (alt, face_rule) if p]
                    final_rules[rule_key] = ' '.join(parts)  # keep combined for event/back compat
                    rules_detail[str(rule_idx)] = {'alternate': alt, 'face': face_rule}
                else:
                    final_rules[rule_key] = base
                    rules_detail[str(rule_idx)] = {'alternate': base, 'face': ''}
            
            # Generic base rule: 0–2 dice → generic_base when set; 3 dice → full_roll when set (else nothing)
            base_rule = full_roll if len(dice_selected) == 3 else generic_base
            if base_rule:
                final_rules['base'] = base_rule
            
            # Clean final_rules - ensure no None values, empty keys, or empty values
            # Firestore does not allow empty strings as values in map fields
            cleaned_final_rules = {}
            for key, value in final_rules.items():
                if key is None:
                    continue
                key_str = str(key).strip()
                if not key_str:  # Skip empty keys
                    continue
                if value is None:
                    continue
                value_str = str(value).strip()
                # CRITICAL: Firestore rejects empty strings in map fields - must have non-empty value
                if not value_str:
                    self.logger.warning(f"Skipping empty value for rule key: {key_str}")
                    continue
                cleaned_final_rules[key_str] = value_str
            
            # Deduct credits
            new_total = current_credits - credits_needed
            credits_ref = self.db.collection('dice_roll_credits').document(couple_id)
            credits_ref.update({
                'total_credits': new_total,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Create dice game event - ensure all fields are valid for Firestore
            today_central = datetime.now(self.central_tz).date()
            
            # Final validation of all fields
            couple_id_str = str(couple_id).strip()
            username_str = str(username).strip()
            
            if not couple_id_str or not username_str:
                return {
                    'status': 'error',
                    'message': 'Invalid couple_id or username'
                }
            
            # Build event_data, only including non-empty dictionaries
            # Ensure dice_selected is a list of integers (Firestore can handle this)
            # Ensure dice_results has string keys (already done above)
            event_data = {
                'couple_id': couple_id_str,
                'username': username_str,
                'date': today_central.isoformat(),
                'dice_selected': list(dice_selected) if dice_selected else [],
                'dice_results': dict(dice_results) if dice_results else {},
                'credits_used': int(credits_needed),
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            # Validate final_rules - only include non-empty (Firestore rejects empty map values)
            validated_final_rules = {}
            if cleaned_final_rules:
                for key, value in cleaned_final_rules.items():
                    if value and str(value).strip():
                        validated_final_rules[str(key).strip()] = str(value).strip()
                    else:
                        self.logger.warning(f"Skipping empty final_rule value for key: {key}")
            
            if validated_final_rules:
                event_data['final_rules'] = validated_final_rules
            
            # Validate event_data before storing - check all nested values
            try:
                # Validate all nested dictionary values and ensure proper types
                for key, value in event_data.items():
                    # Skip SERVER_TIMESTAMP - that's handled by Firestore
                    if value == firestore.SERVER_TIMESTAMP:
                        continue
                    
                    if isinstance(value, dict):
                        # Ensure all map keys are strings (Firestore requirement)
                        for dict_key, dict_value in value.items():
                            if dict_key is None:
                                raise ValueError(f"None key in {key} dictionary")
                            dict_key_str = str(dict_key).strip()
                            if not dict_key_str:
                                raise ValueError(f"Empty key in {key} dictionary")
                            if dict_value is None:
                                raise ValueError(f"None value for key {dict_key_str} in {key}")
                            if isinstance(dict_value, str) and not dict_value.strip():
                                raise ValueError(f"Empty string value for key {dict_key_str} in {key}")
                    elif isinstance(value, str) and not value.strip():
                        raise ValueError(f"Empty string value in event_data for key: {key}")
                    elif isinstance(value, list):
                        # Validate list items
                        for item in value:
                            if item is None:
                                raise ValueError(f"None value in list for key: {key}")
                
                # Create a clean copy with only Firestore-compatible types
                clean_event_data = {}
                for key, value in event_data.items():
                    if value == firestore.SERVER_TIMESTAMP:
                        clean_event_data[key] = value
                    elif isinstance(value, dict):
                        # Ensure all keys are strings
                        clean_dict = {}
                        for k, v in value.items():
                            clean_dict[str(k)] = v
                        clean_event_data[key] = clean_dict
                    else:
                        clean_event_data[key] = value
                
                event_ref = self.db.collection('dice_game_events').add(clean_event_data)
                event_id = event_ref[1].id
            except Exception as e:
                # Log more details about the data structure
                self.logger.error(f"Error creating dice game event: {e}")
                self.logger.error(f"couple_id: '{couple_id_str}', username: '{username_str}'")
                self.logger.error(f"event_data keys: {list(event_data.keys())}")
                if 'final_rules' in event_data:
                    self.logger.error(f"final_rules: {event_data['final_rules']}")
                    self.logger.error(f"final_rules types: {[(k, type(v).__name__) for k, v in event_data['final_rules'].items()]}")
                if 'dice_results' in event_data:
                    self.logger.error(f"dice_results: {event_data['dice_results']}")
                    self.logger.error(f"dice_results key types: {[type(k).__name__ for k in event_data['dice_results'].keys()]}")
                raise
            
            # Log transaction - ensure all fields are valid
            transaction_data = {
                'couple_id': couple_id_str,
                'date': today_central.isoformat(),
                'type': 'spent',
                'amount': float(credits_needed),
                'source': 'dice_roll',
                'username': username_str,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            # Validate transaction data before storing
            for key, value in transaction_data.items():
                if value == firestore.SERVER_TIMESTAMP:
                    continue
                if isinstance(value, str) and not value.strip():
                    self.logger.warning(f"Empty string in transaction_data for key: {key}")
                    transaction_data[key] = 'unknown'  # Use placeholder instead of empty string
            
            self.db.collection('dice_credit_transactions').add(transaction_data)
            
            self.logger.info(f"User {username} rolled {len(dice_selected)} dice, used {credits_needed} credits")
            
            # Build display names for frontend (die titles and face names)
            die_titles = {}
            face_names_by_die = {}
            for rule_idx in range(1, 5):
                cfg = dice_configs.get(f'die_{rule_idx}') or {}
                t = (cfg.get('title') or '').strip()
                die_titles[rule_idx] = t if t else f'Die {rule_idx}'
                fn = cfg.get('face_names') or {}
                face_names_by_die[rule_idx] = {str(f): (fn.get(str(f)) or '').strip() or str(f) for f in range(1, 7)}
            
            return {
                'status': 'success',
                'message': f'Rolled {len(dice_selected)} dice',
                'dice_results': dice_results,
                'final_rules': final_rules,
                'rules_detail': rules_detail,
                'base_rule': base_rule,
                'die_titles': die_titles,
                'face_names_by_die': face_names_by_die,
                'credits_used': credits_needed,
                'remaining_credits': new_total,
                'event_id': event_id
            }
        except Exception as e:
            return handle_exception(e, "Failed to roll dice")
    
    def get_recent_games(self, username: str, limit: int = 10) -> Dict[str, Any]:
        """Get recent dice game events for couple"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {
                    'status': 'error',
                    'message': 'Could not determine couple_id'
                }
            
            # Query events for this couple (no ordering to avoid composite index requirement)
            events_query = self.db.collection('dice_game_events').where(
                filter=FieldFilter('couple_id', '==', couple_id)
            )
            
            events = []
            for doc in events_query.stream():
                event_data = prepare_firestore_document(doc)
                events.append(event_data)
            
            # Sort by created_at in memory (most recent first)
            # Handle both datetime objects and timestamps
            def get_sort_key(event):
                created_at = event.get('created_at')
                if created_at is None:
                    return datetime.min
                if isinstance(created_at, datetime):
                    return created_at
                # If it's a Firestore timestamp, convert it
                if hasattr(created_at, 'timestamp'):
                    return datetime.fromtimestamp(created_at.timestamp())
                return datetime.min
            
            events.sort(key=get_sort_key, reverse=True)
            
            # Limit after sorting
            events = events[:limit]
            
            return {
                'status': 'success',
                'events': events
            }
        except Exception as e:
            return handle_exception(e, "Failed to get recent games")
    
    def reset_credits_daily(self) -> Dict[str, Any]:
        """Daily reset at 2am - carry over credits (with cap)"""
        try:
            now_central = datetime.now(self.central_tz)
            today_central = now_central.date()
            
            # Check if already reset today
            reset_time_today = datetime.combine(today_central, datetime.min.time().replace(hour=2))
            reset_time_today = self.central_tz.localize(reset_time_today)
            
            if now_central < reset_time_today:
                # Not yet 2am today
                return {
                    'status': 'success',
                    'message': 'Reset not needed yet (before 2am)'
                }
            
            # Check if already reset today
            reset_query = self.db.collection('dice_credit_resets').where(
                filter=FieldFilter('reset_date', '==', today_central.isoformat())
            ).limit(1)
            
            reset_docs = list(reset_query.stream())
            if reset_docs:
                return {
                    'status': 'success',
                    'message': 'Already reset today'
                }
            
            # Get all credits documents
            credits_docs = self.db.collection('dice_roll_credits').stream()
            
            reset_count = 0
            for doc in credits_docs:
                credits_data = doc.to_dict()
                current_credits = credits_data.get('total_credits', 0)
                credit_cap = credits_data.get('credit_cap', self.DEFAULT_CREDIT_CAP)
                
                # Credits already capped, no change needed
                # (Credits persist day-to-day, just ensure they're capped)
                if current_credits > credit_cap:
                    doc.reference.update({
                        'total_credits': credit_cap,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    })
                    reset_count += 1
            
            # Mark as reset
            self.db.collection('dice_credit_resets').add({
                'reset_date': today_central.isoformat(),
                'reset_at': firestore.SERVER_TIMESTAMP,
                'credits_checked': reset_count
            })
            
            self.logger.info(f"Daily dice credit reset completed for {today_central}")
            
            return {
                'status': 'success',
                'message': f'Reset completed, checked {reset_count} credit documents'
            }
        except Exception as e:
            return handle_exception(e, "Failed to reset credits daily")
    
    def test_add_credits(self, username: str, amount: int) -> Dict[str, Any]:
        """Test endpoint to add credits manually"""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {
                    'status': 'error',
                    'message': 'Could not determine couple_id'
                }
            
            credits_data = self.get_or_create_credits(couple_id)
            current_credits = credits_data.get('total_credits', 0)
            credit_cap = credits_data.get('credit_cap', self.DEFAULT_CREDIT_CAP)
            
            new_total = min(current_credits + amount, credit_cap)
            actual_added = new_total - current_credits
            
            credits_ref = self.db.collection('dice_roll_credits').document(couple_id)
            credits_ref.update({
                'total_credits': new_total,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Log transaction
            today_central = datetime.now(self.central_tz).date()
            transaction_data = {
                'couple_id': couple_id,
                'date': today_central.isoformat(),
                'type': 'earned',
                'amount': float(actual_added),
                'source': 'manual',
                'username': username,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            self.db.collection('dice_credit_transactions').add(transaction_data)
            
            return {
                'status': 'success',
                'message': f'Added {actual_added} credits (capped at {credit_cap})',
                'credits_added': actual_added,
                'total_credits': new_total
            }
        except Exception as e:
            return handle_exception(e, "Failed to add test credits")
