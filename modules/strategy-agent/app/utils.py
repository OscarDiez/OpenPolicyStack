"""
utils.py — Shared utility functions.
"""


def normalize_score(value: float, min_val: float = -2.0, max_val: float = 2.0) -> float:
    """Normalize a score to the [0, 1] range for display purposes."""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)


def check_bounds(value: float, min_val: float, max_val: float) -> bool:
    """Return True if value is within [min_val, max_val]."""
    return min_val <= value <= max_val


def safe_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def direction_from_value(value: float) -> str:
    if value > 0:
        return "positive"
    elif value < 0:
        return "negative"
    return "neutral"