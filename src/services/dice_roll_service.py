"""
Dice Roll Service - manages dice roll credits and dice configuration
"""
import re
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
    
    def _sorted_die_keys(self, dice_configs: Dict[str, Any]) -> List[str]:
        """Return die keys sorted by die number (e.g. die_1, die_3, die_5)."""
        def key_sort(k):
            m = re.match(r'die_(\d+)', k)
            return int(m.group(1)) if m else 0
        return sorted(
            (k for k in dice_configs if re.match(r'die_\d+', k)),
            key=key_sort
        )
    
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
            
            if config_doc.exists:
                data = prepare_firestore_document(config_doc)
                dice_configs_raw = data.get('dice_configs') or {}
                # Use all keys matching die_{N} in stored config; if empty, use defaults
                die_keys = self._sorted_die_keys(dice_configs_raw)
                if not die_keys:
                    dice_configs = self._default_dice_configs()
                    die_keys = self._sorted_die_keys(dice_configs)
                else:
                    dice_configs = {}
                    for key in die_keys:
                        d = dice_configs_raw.get(key) or {}
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
                # Normalize saved_dice_selection: valid indices 0..N-1, filter invalid
                max_idx = len(die_keys) - 1
                raw_saved = data.get('saved_dice_selection') if config_doc.exists else []
                saved = []
                if isinstance(raw_saved, list):
                    seen = set()
                    for x in raw_saved:
                        try:
                            i = int(x)
                            if 0 <= i <= max_idx and i not in seen:
                                saved.append(i)
                                seen.add(i)
                        except (TypeError, ValueError):
                            continue
                saved = sorted(saved)
                result = {'status': 'success', 'dice_configs': dice_configs, 'updated_at': data.get('updated_at'), 'saved_dice_selection': saved}
            else:
                result = {'status': 'success', 'dice_configs': self._default_dice_configs(), 'updated_at': None, 'saved_dice_selection': []}

            # Either partner can roll; no dice selection UI (backend picks 0-4 dice at random)
            result['can_roll'] = True
            result['can_save_selection'] = False
            return result
        except Exception as e:
            self.logger.error(f"Failed to get dice config for {couple_id}: {e}")
            return {'status': 'error', 'message': str(e), 'dice_configs': self._default_dice_configs()}
    
    def save_dice_configuration(self, couple_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Save dice configuration for couple (dice_configs)"""
        try:
            dice_configs = body.get('dice_configs') or {}
            # Accept any keys matching die_{positive_int}; validate and normalize
            normalized = {}
            for key in dice_configs:
                if not re.match(r'^die_\d+$', key) or key == 'die_0':
                    return {'status': 'error', 'message': f'Invalid die key "{key}": must be die_1, die_2, ...'}
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
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            return {'status': 'success', 'dice_configs': normalized}
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
            couple_id = self.get_couple_id(username)
            if not couple_id:
                return {'status': 'error', 'message': 'Could not determine couple_id'}
            config_result = self.get_dice_configuration(couple_id)
            dice_configs = config_result.get('dice_configs') or {}
            max_idx = len(self._sorted_die_keys(dice_configs)) - 1
            if len(saved_dice_selection) > max_idx + 1:
                return {'status': 'error', 'message': f'At most {max_idx + 1} dice can be selected'}
            seen = set()
            for x in saved_dice_selection:
                try:
                    i = int(x)
                    if i < 0 or i > max_idx:
                        return {'status': 'error', 'message': f'Invalid die index: {i}'}
                    if i in seen:
                        return {'status': 'error', 'message': 'Duplicate die index'}
                    seen.add(i)
                except (TypeError, ValueError):
                    return {'status': 'error', 'message': f'Invalid die index: {x}'}
            normalized = sorted(seen)
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
        """Import (partial) dice config. For each die present, full replace that die; empty fields stay empty. Only replaces dice that exist in current config."""
        try:
            if not isinstance(body, dict):
                return {'status': 'error', 'message': 'Import payload must be a JSON object'}
            dice_configs_in = body.get('dice_configs')
            if dice_configs_in is not None and not isinstance(dice_configs_in, dict):
                return {'status': 'error', 'message': 'dice_configs must be an object'}
            # Get current config - only allow replacing dice that exist
            current = self.get_dice_configuration(couple_id)
            if current.get('status') != 'success':
                return current
            valid_die_keys = set(current.get('dice_configs') or {})
            if dice_configs_in:
                for key in dice_configs_in:
                    if key not in valid_die_keys:
                        return {'status': 'error', 'message': f'Invalid key "{key}": not in current configuration'}
                    d = dice_configs_in[key]
                    if not isinstance(d, dict):
                        return {'status': 'error', 'message': f'dice_configs.{key} must be an object'}
                    # Validate shape: title, base_rule, alternate_rule, face_rules (1-6), face_names (1-6)
                    for f in range(1, 7):
                        if d.get('face_rules') is not None and not isinstance(d.get('face_rules'), dict):
                            return {'status': 'error', 'message': f'dice_configs.{key}.face_rules must be an object with keys "1"-"6"'}
                        if d.get('face_names') is not None and not isinstance(d.get('face_names'), dict):
                            return {'status': 'error', 'message': f'dice_configs.{key}.face_names must be an object with keys "1"-"6"'}
            
            merged_configs = dict(current.get('dice_configs') or self._default_dice_configs())
            if dice_configs_in:
                for key in valid_die_keys:
                    if key in dice_configs_in:
                        merged_configs[key] = self._normalize_one_die(dice_configs_in[key])
            
            return self.save_dice_configuration(couple_id, {'dice_configs': merged_configs})
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
    
    def roll_dice(self, username: str, available_dice: List[int] = None, num_dice: int = None) -> Dict[str, Any]:
        """Roll dice - either partner can roll. Roller picks available pool + exact count; backend picks that many random dice from pool and rolls them."""
        try:
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
            
            # Get dice configuration
            config_result = self.get_dice_configuration(couple_id)
            dice_configs = config_result.get('dice_configs') or self._default_dice_configs()
            sorted_keys = self._sorted_die_keys(dice_configs)
            num_dice = len(sorted_keys)
            
            # Normalize available_dice: list of ints 0..N-1, no duplicates
            pool = []
            if isinstance(available_dice, list):
                seen = set()
                for x in available_dice:
                    try:
                        i = int(x)
                        if 0 <= i < num_dice and i not in seen:
                            pool.append(i)
                            seen.add(i)
                    except (TypeError, ValueError):
                        continue
            # Normalize num_dice: exact count to roll, cap at pool size
            try:
                n = int(num_dice) if num_dice is not None else len(pool)
            except (TypeError, ValueError):
                n = len(pool)
            n = max(0, min(n, len(pool))) if pool else 0
            # Pick exactly n random dice from the available pool
            dice_selected = sorted(random.sample(pool, n)) if n > 0 else []
            
            # Roll dice
            dice_results = {}
            for die_idx in dice_selected:
                face_value = random.randint(1, 6)
                dice_results[str(die_idx)] = face_value
            
            # Build final_rules and rules_detail (alternate + face on separate lines for display)
            # - Not selected: base_rule only. Selected: alternate_rule and face_rule separately.
            final_rules = {}
            rules_detail = {}
            die_titles = {}
            face_names_by_die = {}
            for pos, (rule_idx, die_key) in enumerate(zip(range(1, num_dice + 1), sorted_keys)):
                die_idx = pos
                cfg = dice_configs.get(die_key) or {}
                base = (cfg.get('base_rule') or '').strip()
                alt = (cfg.get('alternate_rule') or '').strip()
                face_rules_map = cfg.get('face_rules') or {}
                rule_key = f'rule_{rule_idx}'
                if die_idx in dice_selected:
                    face_value = dice_results.get(str(die_idx), 1)
                    face_rule = (face_rules_map.get(str(face_value)) or '').strip()
                    parts = [p for p in (alt, face_rule) if p]
                    final_rules[rule_key] = ' '.join(parts)
                    rules_detail[str(rule_idx)] = {'alternate': alt, 'face': face_rule}
                else:
                    final_rules[rule_key] = base
                    rules_detail[str(rule_idx)] = {'alternate': base, 'face': ''}
                t = (cfg.get('title') or '').strip()
                die_titles[rule_idx] = t if t else f'Die {rule_idx}'
                fn = cfg.get('face_names') or {}
                face_names_by_die[rule_idx] = {str(f): (fn.get(str(f)) or '').strip() or str(f) for f in range(1, 7)}
            
            self.logger.info(f"User {username} rolled {len(dice_selected)} dice")
            
            return {
                'status': 'success',
                'message': f'Rolled {len(dice_selected)} dice',
                'dice_results': dice_results,
                'final_rules': final_rules,
                'rules_detail': rules_detail,
                'die_titles': die_titles,
                'face_names_by_die': face_names_by_die,
                'credits_used': 0,
                'remaining_credits': 0
            }
        except Exception as e:
            return handle_exception(e, "Failed to roll dice")
    
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
