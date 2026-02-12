from typing import List, Optional, Tuple
from .data_loader import load_demo_data


def score_component(
    region: str,
    segment: str,
    scenario: Optional[str] = None,
) -> Tuple[float, List[str], str]:
    """
    Minimal scoring logic for MVP skeleton.
    Uses a tiny curated demo dataset + simple scenario hooks.
    Returns: (risk_score, key_drivers, confidence)
    """
    data = load_demo_data()

    seg = segment.strip().lower()
    if seg not in data:
        return 0.50, ["insufficient_demo_data"], "low"

    base = float(data[seg]["base_risk"])
    drivers = list(data[seg]["drivers"])

    bump = 0.0
    if scenario:
        s = scenario.strip().lower()
        if "export" in s or "restriction" in s:
            bump += 0.08
            drivers = ["policy_exposure"] + drivers
        if "geopolit" in s or "sanction" in s:
            bump += 0.06
            drivers = ["geopolitical_risk"] + drivers

    r = region.strip().lower()
    if r in {"eu", "european union"}:
        bump += 0.00
    elif r in {"us", "usa", "united states"}:
        bump += 0.00
    else:
        bump += 0.02  # unknown region penalty for demo

    score = min(1.0, max(0.0, base + bump))
    confidence = "medium"
    return score, drivers[:5], confidence
