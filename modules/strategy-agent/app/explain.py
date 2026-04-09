"""
explain.py — Driver attribution from criteria scores.
Uses plain string criterion keys.
"""

from typing import List
from app.schemas import OptionScore, Driver
from app.config import DEFAULT_WEIGHTS, TOP_K_DRIVERS


def generate_drivers(preferred_option: OptionScore, weights: dict = None) -> List[Driver]:
    if weights is None:
        weights = DEFAULT_WEIGHTS

    contributions = []
    for cs in preferred_option.criteria_scores:
        w = weights.get(cs.criterion, 1 / len(DEFAULT_WEIGHTS))
        contribution = w * cs.score
        direction = "positive" if contribution > 0 else "negative" if contribution < 0 else "neutral"
        source_ref = ", ".join(cs.evidence_ids) if cs.evidence_ids else None
        contributions.append(Driver(
            criterion=cs.criterion,
            direction=direction,
            contribution=round(abs(contribution), 4),
            source_ref=source_ref,
        ))

    contributions.sort(key=lambda d: d.contribution, reverse=True)
    return contributions[:TOP_K_DRIVERS]