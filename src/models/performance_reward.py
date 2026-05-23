"""
Performance reward band logic and tier defaults.
"""
from typing import Optional, List, Dict, Any

MIN_GOAL_FOR_BANDS = 3
TIER_COUNT = 5
TOP_BAND_INDEX = 4  # 2× goal — two reward_slots; other bands have one


# Uneven steps from G to 2G: +30%, +30%, +40% of G (e.g. goal 500 → 500 / 650 / 800 / 1000)
_BAND_STEP_NUMERATORS = (3, 6)  # band 1 upper at G+30%, band 2 at G+60%


def band_cutoffs_for_goal(goal: int) -> Dict[str, int]:
    """Upper bounds for bands 1–3 and 2× goal; empty if goal too low."""
    if goal < MIN_GOAL_FOR_BANDS:
        return {}
    g = int(goal)
    return {
        "below_goal": g,
        "band_1": g + (_BAND_STEP_NUMERATORS[0] * g) // 10,
        "band_2": g + (_BAND_STEP_NUMERATORS[1] * g) // 10,
        "two_x": 2 * g,
    }


def compute_performance_band(points: int, goal: int) -> Optional[int]:
    """
    Map daily points to band 0..4 (highest tier only is chosen by caller).
    Returns None if goal < MIN_GOAL_FOR_BANDS (skip reward flow).
    """
    if goal < MIN_GOAL_FOR_BANDS:
        return None

    g = int(goal)
    pts = int(points)
    cutoffs = band_cutoffs_for_goal(g)
    if pts < cutoffs["below_goal"]:
        return 0
    if pts >= cutoffs["two_x"]:
        return 4
    if pts < cutoffs["band_1"]:
        return 1
    if pts < cutoffs["band_2"]:
        return 2
    return 3


def slot_count_for_band(band_index: int) -> int:
    return 2 if band_index == TOP_BAND_INDEX else 1


def _normalize_assign_to(assign_to: str) -> str:
    return assign_to if assign_to in ("self", "spouse") else "self"


def normalize_reward_slot(slot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "item_text": str(slot.get("item_text", ""))[:500],
        "owed_conversion_points": max(0, int(slot.get("owed_conversion_points", 0))),
        "assign_to": _normalize_assign_to(str(slot.get("assign_to", "self"))),
    }


def default_reward_slot(
    item_text: str = "",
    owed_conversion_points: int = 0,
    assign_to: str = "self",
) -> Dict[str, Any]:
    return normalize_reward_slot({
        "item_text": item_text,
        "owed_conversion_points": owed_conversion_points,
        "assign_to": assign_to,
    })


def tier_reward_slots(tier: Dict[str, Any], band_index: int) -> List[Dict[str, Any]]:
    """Normalized reward_slots for a tier (1 or 2 entries)."""
    count = slot_count_for_band(band_index)
    raw = tier.get("reward_slots", [])[:count]
    slots = [normalize_reward_slot(s) for s in raw]
    while len(slots) < count:
        slots.append(default_reward_slot())
    return slots[:count]


def earned_reward_configs(tier: Dict[str, Any], band: int) -> List[Dict[str, Any]]:
    """Active reward lines to create for a band (non-empty item_text only)."""
    return [s for s in tier_reward_slots(tier, band) if s["item_text"].strip()]


def prepare_tier_for_client(tier: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure API/UI tier shape with reward_slots."""
    t = dict(tier)
    idx = int(t.get("band_index", 0))
    t["reward_slots"] = tier_reward_slots(t, idx)
    return t


def default_tier_settings() -> List[Dict[str, Any]]:
    """Default tier rows for a new couple settings doc."""
    defaults = [
        (0, "Below goal", "consequence", "Complete your below-goal consequence", 1, "self"),
        (1, "Low", "reward", "Low tier reward", 1, "self"),
        (2, "Mid", "reward", "Mid tier reward", 2, "self"),
        (3, "High", "reward", "High tier reward", 3, "self"),
    ]
    rows = [
        {
            "band_index": idx,
            "label": label,
            "kind": kind,
            "reward_slots": [default_reward_slot(text, owed, assign_to)],
        }
        for idx, label, kind, text, owed, assign_to in defaults
    ]
    rows.append({
        "band_index": TOP_BAND_INDEX,
        "label": "2× goal",
        "kind": "reward",
        "reward_slots": [
            default_reward_slot("2× goal reward", 5, "self"),
            default_reward_slot("", 0, "self"),
        ],
    })
    return rows
