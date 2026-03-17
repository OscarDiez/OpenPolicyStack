from typing import List, Optional, Tuple, Dict, Any
from .analytics import get_recursive_risk_metrics

# ⚖️ POLICY RISK WEIGHTS (Adjust these based on Advisor feedback)
# Must sum to 1.0
RISK_WEIGHTS = {
    "hhi": 0.25,                  # Market Concentration
    "geopolitics": 0.20,          # Adversarial Exposure
    "shelf_life": 0.15,           # Perishability (e.g., He-3 decay)
    "substitutability": 0.15,     # Ease of replacement
    "lead_time": 0.10,            # Procurement delay
    "regulatory": 0.10,           # Export Controls
    "impact": 0.05                # Strategic Bottleneck rating
}

from pathlib import Path

def score_component(
    region: str,
    segment: str,
    scenario: Optional[str] = None,
    data_dir: Optional[Path] = None,
) -> Tuple[float, List[str], str]:
    """
    Level 4: Recursive 'Chain of Dependency' Scoring Engine.
    Integrates individual pillar scores with accumulated sub-component risk.
    """
    seg = segment.strip().lower()
    metrics = get_recursive_risk_metrics(seg, region=region, data_dir=data_dir)
    
    if "error" in metrics and "Unknown Component" not in metrics.get("key_drivers", [""])[0]:
        return 0.50, ["insufficient_data"], "low"

    # 1. Calculate Weighted Base Score (for this component specifically)
    raw_scores = metrics["pillar_scores"]
    base_weighted_score = sum(raw_scores[p] * RISK_WEIGHTS[p] for p in RISK_WEIGHTS)
    
    # 2. Accumulated System Risk
    # The 'accumulated_score' from analytics reflects child risks.
    # We blend the weighted base score with the system-wide accumulated risk.
    final_score = (base_weighted_score + metrics["accumulated_score"]) / 2
    
    # 3. Collect Drivers
    drivers = metrics["key_drivers"]
    if metrics.get("spof"):
        drivers.append(f"Strategic Bottleneck: Total system risk is driven by critical sub-component '{metrics['spof']}'.")
    
    # 4. Scenario Overrides
    scenario_bump = 0.0
    if scenario:
        s = scenario.strip().lower()
        if "sanction" in s and (metrics["raw"].get("russia_exposure") or metrics["raw"].get("china_exposure")):
            scenario_bump += 0.20
            drivers.append("sanctions_vulnerability")
        elif "shortage" in s:
            scenario_bump += 0.10
            drivers.append("supply_shortage_risk")
            
    total_score = min(1.0, final_score + scenario_bump)
    confidence = "high" if metrics["raw"].get("has_industry_total") else "medium"
    
    return round(total_score, 2), drivers, confidence
