"""
Dice Roll Service - dice configuration and owed-point rolls
"""
import re
import uuid
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from datetime import datetime
import random
from src.utils.config import get_timezone
from src.utils.firestore_helpers import prepare_firestore_document
from src.utils.error_handlers import handle_exception
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.performance_reward_service import PerformanceRewardService

MAX_FACE_COUNT = 20
DEFAULT_FACE_COUNT = 6
DEFAULT_POINT_VALUE = 1
DEFAULT_MAX_ROLLS = 1
MAX_ROLLS_PER_TURN = 10
COL_SESSIONS = 'dice_roll_sessions'
KEEP_SESSIONS_PER_USER = 2


class DiceRollService:
    """Service for dice roll operations"""

    def __init__(self, app_manager, performance_reward_service: Optional["PerformanceRewardService"] = None):
        self.app_manager = app_manager
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.central_tz = get_timezone()
        self.performance_reward_service = performance_reward_service

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
                return username

            usernames = sorted([username, spouse_username])
            return '_'.join(usernames)
        except Exception as e:
            self.logger.error(f"Failed to get couple_id for {username}: {e}")
            return None

    def get_couple_usernames(self, username: str) -> List[str]:
        """Usernames in this couple (sorted)."""
        try:
            user_ref = self.db.collection('users').document(username)
            user_doc = user_ref.get()
            if not user_doc.exists:
                return [username]
            spouse_username = user_doc.to_dict().get('spouse_username')
            if spouse_username:
                return sorted([username, spouse_username])
            return [username]
        except Exception as e:
            self.logger.error(f"Failed to get couple usernames for {username}: {e}")
            return [username]

    def _sorted_die_keys(self, dice_configs: Dict[str, Any]) -> List[str]:
        def key_sort(k):
            m = re.match(r'die_(\d+)', k)
            return int(m.group(1)) if m else 0
        return sorted(
            (k for k in dice_configs if re.match(r'die_\d+', k)),
            key=key_sort
        )

    def _normalize_face_rules(self, fr: Any, face_count: int) -> Dict[str, str]:
        if isinstance(fr, dict):
            return {str(f): str(fr.get(str(f)) or '').strip() for f in range(1, face_count + 1)}
        return {str(f): '' for f in range(1, face_count + 1)}

    def _normalize_for_usernames(self, raw: Any, couple_usernames: List[str]) -> List[str]:
        members = list(couple_usernames)
        if not isinstance(raw, list) or not raw:
            return members
        valid = [str(u).strip() for u in raw if str(u).strip() in members]
        return valid if valid else members

    def _normalize_one_die(self, d: Dict[str, Any], couple_usernames: List[str]) -> Dict[str, Any]:
        """Normalize a single die config; fill missing fields with defaults."""
        title = str(d.get('title') or '').strip()
        try:
            face_count = int(d.get('face_count', DEFAULT_FACE_COUNT))
        except (TypeError, ValueError):
            face_count = DEFAULT_FACE_COUNT
        face_count = max(2, min(MAX_FACE_COUNT, face_count))
        try:
            point_value = int(d.get('point_value', DEFAULT_POINT_VALUE))
        except (TypeError, ValueError):
            point_value = DEFAULT_POINT_VALUE
        point_value = max(0, point_value)
        face_rules = self._normalize_face_rules(d.get('face_rules'), face_count)
        for_usernames = self._normalize_for_usernames(d.get('for_usernames'), couple_usernames)
        try:
            max_rolls = int(d.get('max_rolls', DEFAULT_MAX_ROLLS))
        except (TypeError, ValueError):
            max_rolls = DEFAULT_MAX_ROLLS
        max_rolls = max(1, min(MAX_ROLLS_PER_TURN, max_rolls, face_count))
        return {
            'title': title,
            'point_value': point_value,
            'face_count': face_count,
            'face_rules': face_rules,
            'for_usernames': for_usernames,
            'max_rolls': max_rolls,
        }

    def _default_dice_configs(self, couple_usernames: List[str]) -> Dict[str, Any]:
        blank = self._normalize_one_die({}, couple_usernames)
        return {f'die_{i}': dict(blank) for i in range(1, 5)}

    def _validate_die_for_save(self, d: Dict[str, Any], couple_usernames: List[str]) -> Optional[str]:
        try:
            face_count = int(d.get('face_count', DEFAULT_FACE_COUNT))
        except (TypeError, ValueError):
            return 'face_count must be an integer'
        if face_count < 2 or face_count > MAX_FACE_COUNT:
            return f'face_count must be between 2 and {MAX_FACE_COUNT}'
        try:
            point_value = int(d.get('point_value', 0))
        except (TypeError, ValueError):
            return 'point_value must be an integer'
        if point_value < 0:
            return 'point_value must be >= 0'
        if d.get('max_rolls') is not None:
            try:
                max_rolls = int(d.get('max_rolls'))
            except (TypeError, ValueError):
                return 'max_rolls must be an integer'
            if max_rolls < 1 or max_rolls > MAX_ROLLS_PER_TURN:
                return f'max_rolls must be between 1 and {MAX_ROLLS_PER_TURN}'
            if max_rolls > face_count:
                return 'max_rolls cannot exceed face_count'
        raw_for = d.get('for_usernames')
        if raw_for is not None:
            if not isinstance(raw_for, list) or not raw_for:
                return 'for_usernames must be a non-empty list'
            for u in raw_for:
                if str(u).strip() not in couple_usernames:
                    return f'for_usernames contains unknown user: {u}'
        return None

    def get_dice_configuration(self, couple_id: str, username: Optional[str] = None) -> Dict[str, Any]:
        """Get dice configuration for couple."""
        try:
            couple_usernames = self.get_couple_usernames(username) if username else []
            if not couple_usernames and couple_id:
                parts = couple_id.split('_')
                couple_usernames = parts if len(parts) > 1 else [couple_id]

            config_ref = self.db.collection('dice_configurations').document(couple_id)
            config_doc = config_ref.get()

            if config_doc.exists:
                data = prepare_firestore_document(config_doc)
                dice_configs_raw = data.get('dice_configs') or {}
                die_keys = self._sorted_die_keys(dice_configs_raw)
                if not die_keys:
                    dice_configs = self._default_dice_configs(couple_usernames)
                else:
                    dice_configs = {}
                    for key in die_keys:
                        d = dice_configs_raw.get(key) or {}
                        dice_configs[key] = self._normalize_one_die(d, couple_usernames)
                max_idx = len(self._sorted_die_keys(dice_configs)) - 1
                raw_saved = data.get('saved_dice_selection') or []
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
                result = {
                    'status': 'success',
                    'dice_configs': dice_configs,
                    'couple_usernames': couple_usernames,
                    'updated_at': data.get('updated_at'),
                    'saved_dice_selection': saved,
                }
            else:
                result = {
                    'status': 'success',
                    'dice_configs': self._default_dice_configs(couple_usernames),
                    'couple_usernames': couple_usernames,
                    'updated_at': None,
                    'saved_dice_selection': [],
                }

            result['can_roll'] = True
            result['can_save_selection'] = False
            return result
        except Exception as e:
            self.logger.error(f"Failed to get dice config for {couple_id}: {e}")
            cu = couple_usernames if couple_usernames else [couple_id]
            return {
                'status': 'error',
                'message': str(e),
                'dice_configs': self._default_dice_configs(cu),
                'couple_usernames': cu,
            }

    def save_dice_configuration(
        self, couple_id: str, body: Dict[str, Any], username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save dice configuration for couple."""
        try:
            couple_usernames = self.get_couple_usernames(username) if username else []
            if not couple_usernames:
                parts = couple_id.split('_')
                couple_usernames = parts if len(parts) > 1 else [couple_id]

            dice_configs = body.get('dice_configs') or {}
            normalized = {}
            for key in dice_configs:
                if not re.match(r'^die_\d+$', key) or key == 'die_0':
                    return {'status': 'error', 'message': f'Invalid die key "{key}": must be die_1, die_2, ...'}
                d = dice_configs.get(key) or {}
                err = self._validate_die_for_save(d, couple_usernames)
                if err:
                    return {'status': 'error', 'message': f'{key}: {err}'}
                normalized[key] = self._normalize_one_die(d, couple_usernames)

            config_ref = self.db.collection('dice_configurations').document(couple_id)
            config_ref.set({
                'couple_id': couple_id,
                'dice_configs': normalized,
                'updated_at': firestore.SERVER_TIMESTAMP,
            }, merge=True)
            return {'status': 'success', 'dice_configs': normalized, 'couple_usernames': couple_usernames}
        except Exception as e:
            self.logger.error(f"Failed to save dice config for {couple_id}: {e}")
            return handle_exception(e, "Failed to save dice configuration")

    def save_saved_dice_selection(self, username: str, saved_dice_selection: List[int]) -> Dict[str, Any]:
        """Save which dice are selected for the couple."""
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
            config_result = self.get_dice_configuration(couple_id, username)
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

    def import_dice_configuration(
        self, couple_id: str, body: Dict[str, Any], username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import (partial) dice config."""
        try:
            if not isinstance(body, dict):
                return {'status': 'error', 'message': 'Import payload must be a JSON object'}
            dice_configs_in = body.get('dice_configs')
            if dice_configs_in is not None and not isinstance(dice_configs_in, dict):
                return {'status': 'error', 'message': 'dice_configs must be an object'}

            current = self.get_dice_configuration(couple_id, username)
            if current.get('status') != 'success':
                return current
            valid_die_keys = set(current.get('dice_configs') or {})
            couple_usernames = current.get('couple_usernames') or []

            if dice_configs_in:
                for key in dice_configs_in:
                    if key not in valid_die_keys:
                        return {'status': 'error', 'message': f'Invalid key "{key}": not in current configuration'}
                    d = dice_configs_in[key]
                    if not isinstance(d, dict):
                        return {'status': 'error', 'message': f'dice_configs.{key} must be an object'}
                    err = self._validate_die_for_save(d, couple_usernames)
                    if err:
                        return {'status': 'error', 'message': f'dice_configs.{key}: {err}'}

            merged_configs = dict(current.get('dice_configs') or self._default_dice_configs(couple_usernames))
            if dice_configs_in:
                for key in valid_die_keys:
                    if key in dice_configs_in:
                        merged_configs[key] = self._normalize_one_die(dice_configs_in[key], couple_usernames)

            return self.save_dice_configuration(couple_id, {'dice_configs': merged_configs}, username)
        except Exception as e:
            self.logger.error(f"Failed to import dice config for {couple_id}: {e}")
            return handle_exception(e, "Failed to import dice configuration")

    @staticmethod
    def compute_roll_points(point_values: List[int]) -> int:
        """Sum of die point values minus the lowest (0 if fewer than 2 dice)."""
        if len(point_values) < 2:
            return 0
        return sum(point_values) - min(point_values)

    def _allowed_die_indices(
        self, username: str, dice_configs: Dict[str, Any], sorted_keys: List[str]
    ) -> List[int]:
        allowed = []
        for idx, die_key in enumerate(sorted_keys):
            cfg = dice_configs.get(die_key) or {}
            for_users = cfg.get('for_usernames') or []
            if username in for_users:
                allowed.append(idx)
        return allowed

    def _expand_selected_dice(self, selected_dice: Any) -> List[int]:
        """Expand selection to ordered list of die indices (supports list or index->count map)."""
        indices: List[int] = []
        if isinstance(selected_dice, dict):
            for key in sorted(selected_dice.keys(), key=lambda k: int(k) if str(k).isdigit() else 0):
                try:
                    idx = int(key)
                    count = int(selected_dice[key])
                except (TypeError, ValueError):
                    continue
                if count > 0:
                    indices.extend([idx] * count)
            return indices
        if isinstance(selected_dice, list):
            for x in selected_dice:
                try:
                    indices.append(int(x))
                except (TypeError, ValueError):
                    continue
        return indices

    def _validate_selected_dice(
        self,
        indices: List[int],
        die_count: int,
        allowed_indices: set,
        dice_configs: Dict[str, Any],
        sorted_keys: List[str],
    ) -> Optional[str]:
        if not indices:
            return None
        counts: Dict[int, int] = {}
        for i in indices:
            if i < 0 or i >= die_count:
                return f'Invalid die index: {i}'
            if i not in allowed_indices:
                return f'Die index {i} is not available for you'
            counts[i] = counts.get(i, 0) + 1
            die_key = sorted_keys[i]
            cfg = dice_configs.get(die_key) or {}
            face_count = int(cfg.get('face_count', DEFAULT_FACE_COUNT))
            max_rolls = min(int(cfg.get('max_rolls', DEFAULT_MAX_ROLLS)), face_count)
            title = (cfg.get('title') or '').strip() or die_key
            if counts[i] > max_rolls:
                return f'"{title}" can be rolled at most {max_rolls} time(s) per roll'
            if counts[i] > face_count:
                return (
                    f'"{title}" cannot be rolled {counts[i]} times — only {face_count} '
                    f'unique face(s) per die'
                )
        return None

    def _unique_faces_for_die(self, face_count: int, roll_count: int) -> List[int]:
        """Sample roll_count distinct face values from 1..face_count."""
        if roll_count <= 0:
            return []
        if roll_count > face_count:
            raise ValueError('roll_count exceeds face_count')
        return random.sample(range(1, face_count + 1), roll_count)

    @staticmethod
    def remaining_faces_for_reroll(
        instances: List[Dict[str, Any]], instance_index: int, face_count: int
    ) -> List[int]:
        """Faces available when rerolling one instance (keeps other instances' faces unique)."""
        if instance_index < 0 or instance_index >= len(instances):
            return []
        inst = instances[instance_index]
        die_idx = inst.get('die_index')
        try:
            current_face = int(inst.get('face_value', 1))
        except (TypeError, ValueError):
            current_face = 1
        used = set()
        for i in instances:
            if i.get('die_index') != die_idx:
                continue
            try:
                used.add(int(i.get('face_value', 0)))
            except (TypeError, ValueError):
                continue
        all_faces = set(range(1, face_count + 1))
        return sorted(all_faces - (used - {current_face}))

    @staticmethod
    def can_reroll_instance(
        instances: List[Dict[str, Any]],
        instance_index: int,
        face_count: int,
        reroll_used: bool = False,
    ) -> bool:
        """True when reroll could change to a different face (not reroll_used)."""
        if reroll_used:
            return False
        remaining = DiceRollService.remaining_faces_for_reroll(
            instances, instance_index, face_count
        )
        if not remaining:
            return False
        try:
            current_face = int(instances[instance_index].get('face_value', 1))
        except (TypeError, ValueError):
            current_face = 1
        return any(f != current_face for f in remaining)

    def _face_count_for_die(
        self, die_index: int, dice_configs: Dict[str, Any], sorted_keys: List[str]
    ) -> int:
        if die_index < 0 or die_index >= len(sorted_keys):
            return DEFAULT_FACE_COUNT
        cfg = dice_configs.get(sorted_keys[die_index]) or {}
        return int(cfg.get('face_count', DEFAULT_FACE_COUNT))

    def _annotate_instances_rerollable(
        self,
        instances: List[Dict[str, Any]],
        dice_configs: Dict[str, Any],
        sorted_keys: List[str],
        reroll_used: bool,
    ) -> List[Dict[str, Any]]:
        out = []
        for i, inst in enumerate(instances):
            row = dict(inst)
            row['instance_index'] = i
            fc = self._face_count_for_die(row.get('die_index', 0), dice_configs, sorted_keys)
            row['rerollable'] = self.can_reroll_instance(
                instances, i, fc, reroll_used=reroll_used
            )
            out.append(row)
        return out

    def _session_doc_to_api(self, data: Dict[str, Any]) -> Dict[str, Any]:
        created = data.get('created_at')
        created_iso = None
        if hasattr(created, 'isoformat'):
            created_iso = created.isoformat()
        elif created:
            created_iso = str(created)
        instances = data.get('roll_instances') or []
        return {
            'roll_id': data.get('roll_id'),
            'created_at': created_iso,
            'roll_instances': instances,
            'points_scored': int(data.get('points_scored', 0)),
            'points_subtracted': int(data.get('points_subtracted', 0)),
            'owed_balance_after': int(data.get('owed_balance_after', 0)),
            'reroll_used': bool(data.get('reroll_used', False)),
        }

    def _save_roll_session(
        self,
        *,
        roll_id: str,
        username: str,
        couple_id: str,
        roll_instances: List[Dict[str, Any]],
        points_scored: int,
        points_subtracted: int,
        owed_balance_after: int,
    ) -> None:
        for i, inst in enumerate(roll_instances):
            inst['instance_index'] = i
        doc = {
            'roll_id': roll_id,
            'username': username,
            'couple_id': couple_id,
            'roll_instances': roll_instances,
            'points_scored': points_scored,
            'points_subtracted': points_subtracted,
            'owed_balance_after': owed_balance_after,
            'reroll_used': False,
            'created_at': firestore.SERVER_TIMESTAMP,
        }
        self.db.collection(COL_SESSIONS).document(roll_id).set(doc)
        self._prune_old_sessions(username, keep_roll_id=roll_id)

    def _prune_old_sessions(self, username: str, keep_roll_id: Optional[str] = None) -> None:
        """Keep only the newest KEEP_SESSIONS_PER_USER sessions for this user."""
        try:
            query = self.db.collection(COL_SESSIONS).where(
                filter=FieldFilter('username', '==', username)
            )
            sessions = []
            for doc in query.stream():
                data = prepare_firestore_document(doc)
                data['roll_id'] = doc.id
                sessions.append(data)

            def sort_key(s):
                c = s.get('created_at')
                if c is None:
                    return datetime.min.replace(tzinfo=self.central_tz)
                if hasattr(c, 'tzinfo') and c.tzinfo is None and hasattr(self.central_tz, 'localize'):
                    return self.central_tz.localize(c)
                return c

            sessions.sort(key=sort_key, reverse=True)
            keep_ids = {s['roll_id'] for s in sessions[:KEEP_SESSIONS_PER_USER]}
            if keep_roll_id:
                keep_ids.add(keep_roll_id)
            for s in sessions:
                if s['roll_id'] not in keep_ids:
                    self.db.collection(COL_SESSIONS).document(s['roll_id']).delete()
        except Exception as e:
            self.logger.error(f"Failed to prune dice sessions for {username}: {e}")

    def get_roll_history(self, username: str, limit: int = 2) -> Dict[str, Any]:
        """Last N roll sessions for this user (newest first)."""
        try:
            query = self.db.collection(COL_SESSIONS).where(
                filter=FieldFilter('username', '==', username)
            )
            sessions = []
            for doc in query.stream():
                data = prepare_firestore_document(doc)
                data['roll_id'] = doc.id
                sessions.append(data)

            def sort_key(s):
                c = s.get('created_at')
                if c is None:
                    return datetime.min.replace(tzinfo=self.central_tz)
                if hasattr(c, 'tzinfo') and c.tzinfo is None and hasattr(self.central_tz, 'localize'):
                    return self.central_tz.localize(c)
                return c

            sessions.sort(key=sort_key, reverse=True)
            api_sessions = [
                self._session_doc_to_api(s) for s in sessions[: max(0, limit)]
            ]
            return {'status': 'success', 'sessions': api_sessions}
        except Exception as e:
            return handle_exception(e, 'Failed to get roll history')

    def _load_roll_session(self, roll_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection(COL_SESSIONS).document(roll_id).get()
        if not doc.exists:
            return None
        data = prepare_firestore_document(doc)
        data['roll_id'] = doc.id
        return data

    def reroll_one_instance(
        self, username: str, roll_id: str, instance_index: int
    ) -> Dict[str, Any]:
        """Reroll a single instance once per session; does not change owed points."""
        try:
            session = self._load_roll_session(roll_id)
            if not session:
                return {'status': 'error', 'message': 'Roll session not found'}
            if session.get('username') != username:
                return {'status': 'error', 'message': 'Not allowed to reroll this roll'}
            if session.get('reroll_used'):
                return {'status': 'error', 'message': 'Reroll already used for this roll'}

            instances = session.get('roll_instances') or []
            try:
                idx = int(instance_index)
            except (TypeError, ValueError):
                return {'status': 'error', 'message': 'Invalid instance_index'}
            if idx < 0 or idx >= len(instances):
                return {'status': 'error', 'message': 'Invalid instance_index'}

            couple_id = session.get('couple_id') or self.get_couple_id(username)
            config_result = self.get_dice_configuration(couple_id, username)
            if config_result.get('status') != 'success':
                return config_result
            dice_configs = config_result.get('dice_configs') or {}
            sorted_keys = self._sorted_die_keys(dice_configs)

            die_idx = instances[idx].get('die_index')
            face_count = self._face_count_for_die(die_idx, dice_configs, sorted_keys)
            if not self.can_reroll_instance(instances, idx, face_count, reroll_used=False):
                return {
                    'status': 'error',
                    'message': 'No other faces available for this die',
                }
            remaining = self.remaining_faces_for_reroll(instances, idx, face_count)
            try:
                current_face = int(instances[idx].get('face_value', 1))
            except (TypeError, ValueError):
                current_face = 1
            remaining = [f for f in remaining if f != current_face]

            new_face = random.choice(remaining)
            die_key = sorted_keys[die_idx]
            cfg = dice_configs.get(die_key) or {}
            face_rules_map = cfg.get('face_rules') or {}
            instances[idx]['face_value'] = new_face
            instances[idx]['face_rule'] = (
                face_rules_map.get(str(new_face)) or ''
            ).strip()

            session['roll_instances'] = instances
            session['reroll_used'] = True
            self.db.collection(COL_SESSIONS).document(roll_id).set({
                'roll_instances': instances,
                'reroll_used': True,
                'updated_at': firestore.SERVER_TIMESTAMP,
            }, merge=True)

            annotated = self._annotate_instances_rerollable(
                instances, dice_configs, sorted_keys, reroll_used=True
            )
            return {
                'status': 'success',
                'message': 'Die rerolled',
                'roll_id': roll_id,
                'roll_instances': annotated,
                'points_scored': int(session.get('points_scored', 0)),
                'points_subtracted': int(session.get('points_subtracted', 0)),
                'owed_balance_before': int(session.get('owed_balance_after', 0)),
                'owed_balance_after': int(session.get('owed_balance_after', 0)),
                'reroll_used': True,
            }
        except Exception as e:
            return handle_exception(e, 'Failed to reroll die')

    def roll_dice(self, username: str, selected_dice: Any = None) -> Dict[str, Any]:
        """Roll explicitly selected dice; subtract scored points from roller's owed balance."""
        try:
            couple_id = self.get_couple_id(username)
            if not couple_id or not isinstance(couple_id, str) or couple_id.strip() == '':
                return {'status': 'error', 'message': 'Could not determine couple_id'}
            if not username or not isinstance(username, str) or username.strip() == '':
                return {'status': 'error', 'message': 'Invalid username'}

            config_result = self.get_dice_configuration(couple_id, username)
            if config_result.get('status') != 'success':
                return config_result

            dice_configs = config_result.get('dice_configs') or self._default_dice_configs(
                config_result.get('couple_usernames') or [username]
            )
            sorted_keys = self._sorted_die_keys(dice_configs)
            die_count = len(sorted_keys)
            allowed_indices = set(self._allowed_die_indices(username, dice_configs, sorted_keys))

            dice_selected = self._expand_selected_dice(selected_dice)
            err = self._validate_selected_dice(
                dice_selected, die_count, allowed_indices, dice_configs, sorted_keys
            )
            if err:
                return {'status': 'error', 'message': err}

            counts_by_die: Dict[int, int] = {}
            for die_idx in dice_selected:
                counts_by_die[die_idx] = counts_by_die.get(die_idx, 0) + 1

            faces_queue_by_die: Dict[int, List[int]] = {}
            for die_idx, roll_count in counts_by_die.items():
                cfg = dice_configs.get(sorted_keys[die_idx]) or {}
                face_count = int(cfg.get('face_count', DEFAULT_FACE_COUNT))
                try:
                    faces_queue_by_die[die_idx] = self._unique_faces_for_die(
                        face_count, roll_count
                    )
                except ValueError:
                    die_key = sorted_keys[die_idx]
                    title = (cfg.get('title') or '').strip() or die_key
                    return {
                        'status': 'error',
                        'message': (
                            f'"{title}" cannot be rolled {roll_count} times — only '
                            f'{face_count} unique face(s) per die'
                        ),
                    }

            face_use_index: Dict[int, int] = {}
            roll_instances = []
            rolled_point_values = []
            for die_idx in dice_selected:
                die_key = sorted_keys[die_idx]
                cfg = dice_configs.get(die_key) or {}
                queue = faces_queue_by_die[die_idx]
                use_i = face_use_index.get(die_idx, 0)
                face_value = queue[use_i]
                face_use_index[die_idx] = use_i + 1
                face_rules_map = cfg.get('face_rules') or {}
                face_rule = (face_rules_map.get(str(face_value)) or '').strip()
                pv = int(cfg.get('point_value', DEFAULT_POINT_VALUE))
                rolled_point_values.append(pv)
                t = (cfg.get('title') or '').strip() or f'Die {die_idx + 1}'
                roll_instances.append({
                    'die_index': die_idx,
                    'title': t,
                    'point_value': pv,
                    'face_value': face_value,
                    'face_rule': face_rule,
                })

            points_scored = self.compute_roll_points(rolled_point_values)

            owed_balance_before = 0
            if self.performance_reward_service:
                owed_balance_before = self.performance_reward_service._get_owed_balance(
                    username
                )
            min_required = 0
            if self.performance_reward_service:
                min_required = self.performance_reward_service.minimum_dice_roll_points(
                    owed_balance_before
                )
            if min_required > 0 and points_scored < min_required:
                return {
                    'status': 'error',
                    'message': (
                        f'This roll scores {points_scored} points, but with '
                        f'{owed_balance_before} owed you must roll at least '
                        f'{min_required} points'
                    ),
                }

            roll_id = str(uuid.uuid4())

            points_subtracted = 0
            owed_balance_after = owed_balance_before
            if self.performance_reward_service and points_scored > 0:
                debit = self.performance_reward_service.debit_owed_for_dice_roll(
                    username, points_scored, roll_id=roll_id
                )
                if debit.get('status') == 'success':
                    owed_balance_before = debit.get('owed_balance_before', 0)
                    points_subtracted = debit.get('points_subtracted', 0)
                    owed_balance_after = debit.get('owed_balance_after', 0)
                elif debit.get('status') == 'error':
                    return debit

            self._save_roll_session(
                roll_id=roll_id,
                username=username,
                couple_id=couple_id,
                roll_instances=roll_instances,
                points_scored=points_scored,
                points_subtracted=points_subtracted,
                owed_balance_after=owed_balance_after,
            )

            annotated = self._annotate_instances_rerollable(
                roll_instances, dice_configs, sorted_keys, reroll_used=False
            )

            self.logger.info(
                f"User {username} rolled {len(dice_selected)} dice, "
                f"scored {points_scored}, subtracted {points_subtracted}"
            )

            return {
                'status': 'success',
                'message': f'Rolled {len(dice_selected)} dice',
                'roll_id': roll_id,
                'roll_instances': annotated,
                'points_scored': points_scored,
                'points_subtracted': points_subtracted,
                'owed_balance_before': owed_balance_before,
                'owed_balance_after': owed_balance_after,
                'reroll_used': False,
            }
        except Exception as e:
            return handle_exception(e, "Failed to roll dice")
