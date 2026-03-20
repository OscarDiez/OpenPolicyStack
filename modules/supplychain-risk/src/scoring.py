"""
Scoring Engine
==============
Top-level entry point for component risk scoring.
Blends the 7-pillar base score with ARI (Accumulated Risk Index)
from the dependency graph, then applies scenario overlays.

Final formula (from methodology):
  S_final = min(1.0, (S_base + ARI) / 2 + Δ_scenario)
"""

from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

from analytics import (
    get_recursive_risk_metrics,
    get_component_risk_metrics,
    load_dependency_graph,
    get_perspective_comparison,
    get_segment_perspective_comparison,
)

# ─── Risk Weights (must sum to 1.0) ───────────────────────────────────────────
RISK_WEIGHTS: Dict[str, float] = {
    "hhi":              0.25,   # Market Concentration
    "geopolitics":      0.20,   # Adversarial Exposure
    "shelf_life":       0.15,   # Perishability
    "substitutability": 0.15,   # Ease of replacement
    "lead_time":        0.10,   # Procurement delay
    "regulatory":       0.10,   # Export Controls
    "impact":           0.05,   # Strategic Bottleneck
}

# ─── Scenario Overlays ────────────────────────────────────────────────────────
# Each scenario defines:
#   label        — display name
#   description  — what it means for the score
#   condition    — what triggers the delta (key in the raw metrics dict, or "always")
#   delta        — score bump when triggered
#   perspectives — which analysis perspectives this scenario is relevant to
#                  ["EU", "US", "CHINA", "GLOBAL"] or subset
#
# Condition keys that map to raw metrics fields:
#   "always"              → always triggered
#   "russia_exposure"     → component has Russian suppliers
#   "china_exposure"      → component has Chinese suppliers
#   "taiwan_exposure"     → component has Taiwanese suppliers
#   "australia_exposure"  → component has Australian suppliers
#   "geopolitics_high"    → geopolitics pillar score > 0.5
#   "helium3_component"   → component name contains "helium-3" or "he-3"

SCENARIOS: Dict[str, Dict] = {

    # ── Universal scenarios (all perspectives) ──────────────────────────────
    "supply_shortage": {
        "label":        "Global Supply Shortage",
        "perspectives": ["EU", "US", "CHINA", "GLOBAL"],
        "condition":    "always",
        "delta":        0.10,
        "description":  "General supply shock affecting all components. +0.10 across the board.",
    },
    "pandemic_logistics": {
        "label":        "Pandemic / Logistics Disruption",
        "perspectives": ["EU", "US", "CHINA", "GLOBAL"],
        "condition":    "always",
        "delta":        0.12,
        "description":  "Global logistics disruption (e.g. COVID-style) increases lead times and creates shortages. +0.12 across the board.",
    },
    "helium3_shortage": {
        "label":        "Helium-3 Critical Shortage",
        "perspectives": ["EU", "US", "CHINA", "GLOBAL"],
        "condition":    "helium3_component",
        "delta":        0.45,
        "description":  "Critical shortage of He-3 isotope (key for dilution refrigerators). +0.45 for He-3 dependent components.",
    },
    "climate_disruption": {
        "label":        "Climate-Related Supply Disruption",
        "perspectives": ["EU", "US", "CHINA", "GLOBAL"],
        "condition":    "always",
        "delta":        0.08,
        "description":  "Flooding, drought, or extreme weather events disrupt mining and logistics routes. +0.08 across the board.",
    },

    # ── EU perspective scenarios ─────────────────────────────────────────────
    "eu_sanctions_russia": {
        "label":        "EU Sanctions on Russia",
        "perspectives": ["EU"],
        "condition":    "russia_exposure",
        "delta":        0.20,
        "description":  "Export controls or sanctions imposed on Russia by the EU. +0.20 for components sourced from Russia.",
    },
    "eu_sanctions_china": {
        "label":        "EU Sanctions on China",
        "perspectives": ["EU"],
        "condition":    "china_exposure",
        "delta":        0.20,
        "description":  "Export controls or sanctions imposed on China by the EU. +0.20 for components with Chinese supply.",
    },
    "eu_china_crm_ban": {
        "label":        "China Critical Material Export Restrictions",
        "perspectives": ["EU"],
        "condition":    "china_exposure",
        "delta":        0.28,
        "description":  "China restricts exports of critical raw materials (gallium, germanium, niobium, graphite). +0.28 for China-exposed components. Precedent: July 2023 Ga/Ge restrictions.",
    },
    "eu_tariffs": {
        "label":        "EU Trade Tariffs",
        "perspectives": ["EU"],
        "condition":    "geopolitics_high",
        "delta":        0.15,
        "description":  "Broad EU tariff regime on strategic imports. +0.15 for components with high geopolitical exposure.",
    },
    "eu_us_itar_tighten": {
        "label":        "US ITAR Tightening (EU Impact)",
        "perspectives": ["EU"],
        "condition":    "geopolitics_high",
        "delta":        0.18,
        "description":  "US tightens ITAR export controls, restricting EU access to US-origin dual-use components. +0.18 for highly geopolitically exposed components.",
    },

    # ── US perspective scenarios ─────────────────────────────────────────────
    "us_sanctions_russia": {
        "label":        "US Sanctions on Russia",
        "perspectives": ["US"],
        "condition":    "russia_exposure",
        "delta":        0.22,
        "description":  "US sanctions and export controls on Russia. +0.22 for components sourced from Russia.",
    },
    "us_china_decoupling": {
        "label":        "Full US-China Technology Decoupling",
        "perspectives": ["US"],
        "condition":    "china_exposure",
        "delta":        0.35,
        "description":  "Full ban on US procurement of Chinese technology inputs. +0.35 for all China-exposed components.",
    },
    "us_china_crm_ban": {
        "label":        "China Critical Material Export Ban (US)",
        "perspectives": ["US"],
        "condition":    "china_exposure",
        "delta":        0.30,
        "description":  "China restricts critical material exports targeting the US. +0.30 for components with Chinese supply dependency.",
    },
    "us_taiwan_conflict": {
        "label":        "Taiwan Strait Military Conflict",
        "perspectives": ["US"],
        "condition":    "taiwan_exposure",
        "delta":        0.45,
        "description":  "Military conflict disrupts Taiwan-sourced components. +0.45 for Taiwan-exposed supply chains.",
    },
    "us_tariffs_broad": {
        "label":        "US Broad Tariff Regime",
        "perspectives": ["US"],
        "condition":    "always",
        "delta":        0.12,
        "description":  "Broad US tariffs on strategic imports across all trading partners. +0.12 across the board.",
    },

    # ── China perspective scenarios ──────────────────────────────────────────
    "cn_western_embargo": {
        "label":        "Western Technology Embargo on China",
        "perspectives": ["CHINA"],
        "condition":    "geopolitics_high",
        "delta":        0.35,
        "description":  "US-led coalition imposes comprehensive technology export ban on China. +0.35 for components dependent on Western suppliers.",
    },
    "cn_taiwan_conflict": {
        "label":        "Taiwan Strait Conflict",
        "perspectives": ["CHINA"],
        "condition":    "taiwan_exposure",
        "delta":        0.30,
        "description":  "Military conflict around Taiwan affects supply chains. +0.30 for Taiwan-sourced components.",
    },
    "cn_australia_minerals": {
        "label":        "Australia Critical Mineral Export Restrictions",
        "perspectives": ["CHINA"],
        "condition":    "australia_exposure",
        "delta":        0.25,
        "description":  "Australia restricts exports of critical minerals to China. +0.25 for Australia-exposed supply chains.",
    },
    "cn_us_sanctions": {
        "label":        "US Sanctions on Chinese Entities",
        "perspectives": ["CHINA"],
        "condition":    "geopolitics_high",
        "delta":        0.28,
        "description":  "US sanctions restrict Chinese firms from accessing US-origin technology and components. +0.28 for high-geopolitical-exposure components.",
    },
}


def get_scenarios_for_perspective(region: str) -> Dict[str, Dict]:
    """Return only scenarios relevant to the given perspective."""
    r = region.upper()
    return {
        k: v for k, v in SCENARIOS.items()
        if r in v.get("perspectives", []) or "GLOBAL" in v.get("perspectives", [])
    }


def score_component(
    region: str,
    component: str,
    scenario: Optional[str] = None,
    data_dir: Optional[Path] = None,
) -> Tuple[float, List[str], str]:
    """
    Compute the final composite risk score for a single component.

    Returns:
        (score, key_drivers, confidence_label)
        score: float in [0, 1]
        confidence: "high" | "medium" | "low"
    """
    seg   = component.strip().lower()
    memo: Dict = {}
    metrics = get_recursive_risk_metrics(seg, region=region, memo=memo, data_dir=data_dir)

    # 1. Weighted base score from 7 pillars
    raw_scores    = metrics["pillar_scores"]
    s_base        = sum(raw_scores[p] * RISK_WEIGHTS[p] for p in RISK_WEIGHTS)

    # 2. ARI from dependency graph
    ari           = metrics["accumulated_score"]

    # 3. Blend: S_final = (S_base + ARI) / 2
    blended       = (s_base + ari) / 2

    # 4. Scenario overlay (Δ_scenario)
    delta         = 0.0
    drivers       = list(metrics["key_drivers"])

    if metrics.get("spof"):
        drivers.append(
            f"Strategic Bottleneck: Entire system risk is driven by sub-component "
            f"'{metrics['spof']}'."
        )

    if scenario and scenario in SCENARIOS:
        sc   = SCENARIOS[scenario]
        cond = sc["condition"]
        raw  = metrics.get("raw", {})
        comp_lower = component.lower()
        triggered = (
            cond == "always"
            or (cond == "russia_exposure"    and raw.get("russia_exposure"))
            or (cond == "china_exposure"     and raw.get("china_exposure"))
            or (cond == "taiwan_exposure"    and raw.get("taiwan_exposure"))
            or (cond == "australia_exposure" and raw.get("australia_exposure"))
            or (cond == "geopolitics_high"   and raw_scores.get("geopolitics", 0) > 0.5)
            or (cond == "helium3_component"  and any(k in comp_lower for k in ["helium-3", "helium 3", "he-3", "he3"]))
        )
        if triggered:
            delta = sc["delta"]
            drivers.append(
                f"Scenario — {sc['label']}: {sc['description']} "
                f"Score raised by +{delta:.2f}."
            )

    final_score = round(min(1.0, blended + delta), 3)

    # Confidence: high if we have real trade data, medium otherwise
    confidence = "high" if metrics["raw"].get("has_trade_data") else "medium"

    return final_score, drivers, confidence
