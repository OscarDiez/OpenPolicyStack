"""
Analytics Engine — Supply Chain Risk Intelligence
==================================================
Implements:
  - 7-Pillar component risk scoring (as per methodology)
  - Recursive dependency propagation (ARI)
  - Perspective-driven geopolitical comparison (EU / US / China)
  - Scenario overlays (sanctions, shortage, tariffs)
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


def normalize_component_name(stem: str) -> str:
    """
    Convert a supplier file stem (e.g. 'helium_3_suppliers' → 'helium_3')
    to the canonical display name used everywhere in the app.
    Must stay in sync with app.py:_normalize_component_name().
    """
    name = stem.replace("_", " ").title()
    name = name.replace("Nbti", "NbTi").replace("Ofhc", "OFHC")
    name = name.replace("Rf ", "RF ").replace("Pid ", "PID ")
    if "Helium 3" in name:
        name = "Helium-3"
    if "Helium 4" in name:
        name = "Helium-4"
    return name


# ─── Adversary Configurations per Perspective ─────────────────────────────────
# Each perspective defines which countries are considered strategic adversaries.
# This is the core of the perspective-driven approach described in section 5.3
# of the methodology.

ADVERSARY_SETS: Dict[str, List[str]] = {
    # EU adversaries: hostile states per EU foreign policy / sanctions lists
    "EU": [
        "RUSSIA", "RUSSIAN FEDERATION", "CHINA", "CN", "PEOPLE'S REPUBLIC OF CHINA",
        "IRAN", "ISLAMIC REPUBLIC OF IRAN",
        "NORTH KOREA", "DPRK", "DEMOCRATIC PEOPLE'S REPUBLIC OF KOREA",
        "BELARUS",
    ],
    # US adversaries: OFAC-sanctioned and export-controlled states
    # Note: Venezuela removed (2026 — US engagement shifted following political developments)
    # Cuba retained as adversary per OFAC SDN
    "US": [
        "RUSSIA", "RUSSIAN FEDERATION", "CHINA", "CN", "PEOPLE'S REPUBLIC OF CHINA",
        "IRAN", "ISLAMIC REPUBLIC OF IRAN",
        "NORTH KOREA", "DPRK", "DEMOCRATIC PEOPLE'S REPUBLIC OF KOREA",
        "CUBA",
    ],
    # China adversaries: states China views as strategic competitors or hostile
    "CHINA": [
        "UNITED STATES", "USA", "US",
        "JAPAN", "SOUTH KOREA", "KOREA, REPUBLIC OF",
        "TAIWAN", "TAIWAN, PROVINCE OF CHINA",
        "AUSTRALIA", "UNITED KINGDOM", "UK",
        "INDIA",  # Border tensions and strategic rivalry
    ],
    # Global: no adversaries — pure concentration/HHI analysis
    "GLOBAL": [],
}


def _resolve_adversaries(region: str) -> List[str]:
    r = region.upper().strip()
    for key in ADVERSARY_SETS:
        if r == key or r.startswith(key):
            return ADVERSARY_SETS[key]
    return ADVERSARY_SETS["EU"]


# ─── HHI ──────────────────────────────────────────────────────────────────────

def calculate_hhi(shares: List[float]) -> float:
    """
    Herfindahl-Hirschman Index.
    Input shares as decimals (e.g. 0.35 for 35%) OR percentages (e.g. 35.0).
    Automatically normalizes: if any share > 1.0, treats all as percentages and divides by 100.
    Result is on the 0–10,000 scale used by the DoJ / European Commission.
    """
    if shares and max(shares) > 1.0:
        shares = [s / 100.0 for s in shares]
    return sum((s * 100) ** 2 for s in shares)


# ─── 7-Pillar Component Scoring ───────────────────────────────────────────────

def get_component_risk_metrics(
    component: str,
    region: str = "EU",
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Level 3: 7-Pillar risk scoring for a single component.
    Pillar 1 (HHI) and Pillar 2 (Geopolitics) are calibrated from trade flow data
    where available; fall back to supplier registry otherwise.
    """
    base_dir    = data_dir or (Path(__file__).resolve().parents[1] / "data" / "segments" / "cryogenics")
    safe_name   = component.lower().replace(" ", "_").replace("/", "_").replace("-", "_").replace("(", "").replace(")", "")
    supp_file   = base_dir / "suppliers" / f"{safe_name}_suppliers.json"
    trade_file  = base_dir / "trade"     / f"{safe_name}_trade_flows.json"

    if not supp_file.exists():
        return {"error": f"No supplier registry found for '{component}'"}

    with open(supp_file) as f:
        supp_data = json.load(f)

    trade_data: Optional[Dict] = None
    if trade_file.exists():
        with open(trade_file) as f:
            trade_data = json.load(f)

    suppliers      = supp_data.get("suppliers", [])
    real_suppliers = [s for s in suppliers if s.get("name") != "GLOBAL_INDUSTRY_TOTAL"]
    notes_blob     = " ".join((s.get("strategic_notes") or "") for s in suppliers).lower()

    if not real_suppliers:
        return {"error": "Empty supplier registry"}

    adversaries = _resolve_adversaries(region)

    # ── Pillar 1: Market Concentration (HHI) ──────────────────────────────────
    # Perspective-aware: if the dominant suppliers are in the same bloc as the
    # perspective country, concentration is a strength (low risk), not a weakness.
    PERSPECTIVE_SELF: Dict[str, List[str]] = {
        "EU":    ["GERMANY", "FRANCE", "NETHERLANDS", "FINLAND", "SWEDEN", "ITALY",
                  "SPAIN", "BELGIUM", "AUSTRIA", "DENMARK", "NORWAY", "POLAND",
                  "CZECH REPUBLIC", "EUROPEAN UNION", "EU"],
        "US":    ["UNITED STATES", "USA", "US"],
        "CHINA": ["CHINA", "CN", "PEOPLE'S REPUBLIC OF CHINA"],
        "GLOBAL": [],
    }
    self_countries = PERSPECTIVE_SELF.get(region.upper(), [])

    if trade_data and trade_data.get("exporters"):
        raw_shares  = [e.get("share", 0) for e in trade_data["exporters"]]
        # Normalize: LLM sometimes returns 35 instead of 0.35 — detect and fix
        if raw_shares and max(raw_shares) > 1.0:
            raw_shares = [s / 100.0 for s in raw_shares]
            # Also fix in-place so downstream adversary_share calc is correct
            for e, ns in zip(trade_data["exporters"], raw_shares):
                e["share"] = ns
        shares      = raw_shares
        hhi         = calculate_hhi(shares)
        hhi_source  = trade_data.get("data_source", "Trade Data")
        n_suppliers = len(trade_data["exporters"])
        # Share controlled by the perspective's own bloc
        self_share  = sum(
            e.get("share", 0) for e in trade_data["exporters"]
            if e.get("country", "").upper() in self_countries
        )
    else:
        n_suppliers = len(real_suppliers)
        hhi         = calculate_hhi([1.0 / n_suppliers] * n_suppliers)
        if n_suppliers <= 2:
            hhi = max(hhi, 5000)   # Conservative floor when data is sparse
        hhi_source  = "Supplier registry (fallback)"
        self_share  = sum(
            1 for s in real_suppliers
            if (s.get("country") or "").upper() in self_countries
        ) / max(n_suppliers, 1)

    # If perspective controls a large share of the market, concentration is a
    # strategic asset, not a risk — discount the HHI penalty proportionally.
    # self_share is clamped to [0,1] to prevent arithmetic errors from bad data.
    self_share = max(0.0, min(1.0, self_share))
    raw_p1 = min(1.0, hhi / 10_000 + 0.1)
    p1_score = round(max(0.0, raw_p1 * (1.0 - 0.8 * self_share)), 3)

    # ── Pillar 2: Geopolitical Dependency ─────────────────────────────────────
    r_region = region.upper()
    if trade_data and trade_data.get("exporters"):
        adversary_share = sum(
            e.get("share", 0)
            for e in trade_data["exporters"]
            if e.get("country", "").upper() in adversaries
        )
        p2_score = 0.2 + (0.75 * adversary_share)
        countries = [e.get("country", "") for e in trade_data["exporters"]]
    else:
        # Prefer beneficial_owner_country (enriched ownership intelligence) over
        # the listed country of operation — catches hidden foreign state control.
        countries = [
            s.get("beneficial_owner_country") or s.get("country") or "Unknown"
            for s in real_suppliers
        ]
        has_adversary = any(c.upper() in adversaries for c in countries if isinstance(c, str))
        p2_score      = 0.8 if has_adversary else 0.2
    p2_score = max(0.0, min(1.0, p2_score))

    # ── Pillar 3: Shelf-Life / Perishability ──────────────────────────────────
    comp_lower = component.lower()
    p3_score   = 0.1
    if any(k in comp_lower for k in ["helium-3", "he-3", "tritium"]):
        p3_score = 0.55  # ~5.5% annual decay rate

    # ── Pillar 4: Substitutability ────────────────────────────────────────────
    bespoke_kw = [
        "custom", "fridge", "mixing", "superconducting", "bespoke", "chamber",
        "dilution", "cryostat", "niobium", "nbti", "josephson",
    ]
    p4_score = 0.8 if any(k in comp_lower for k in bespoke_kw) else 0.3

    # ── Pillar 5: Lead-Time & Logistics ───────────────────────────────────────
    long_leadtime_kw = ["magnet", "bespoke", "custom", "fridge", "dilution", "cryostat", "chamber"]
    p5_score = 0.85 if any(k in comp_lower for k in long_leadtime_kw) else 0.4

    # ── Pillar 6: Regulatory Exposure ─────────────────────────────────────────
    reg_kw   = ["itar", "dual-use", "dual use", "export control", "license", "regulated", "restricted"]
    p6_score = 0.9 if any(k in notes_blob for k in reg_kw) else 0.2

    # ── Pillar 7: Strategic Impact ────────────────────────────────────────────
    core_kw  = ["chamber", "pump", "fridge", "helium-3", "magnet", "wire", "dilution", "cryostat", "qubit"]
    p7_score = 0.95 if any(k in comp_lower for k in core_kw) else 0.5

    # ── Build driver messages ──────────────────────────────────────────────────
    drivers = []
    top_names = [s.get("name") for s in real_suppliers[:2] if s.get("name")]
    top_str   = ", ".join(top_names) if top_names else "major suppliers"

    if p1_score > 0.6:
        label = "Volume-Weighted" if trade_data else "Structural"
        drivers.append(
            f"{label} Monopoly Risk: The market for {component} is highly concentrated "
            f"(HHI {int(hhi):,} — source: {hhi_source}). Supply is dangerously reliant on "
            f"a small number of actors including {top_str}."
        )
    if p2_score > 0.5:
        adv_list  = [c for c in countries if c and c.upper() in adversaries]
        adv_names = ", ".join(sorted(set(adv_list))) or "strategic rivals"
        drivers.append(
            f"Geopolitical Dependency: Sourcing for {component} shows significant exposure to "
            f"adversarial jurisdictions ({adv_names}) from the {r_region} perspective, "
            f"creating export-ban and sanctions risk."
        )
    if p3_score > 0.5:
        drivers.append(
            f"Physical Perishability: {component} degrades over time (~5.5% annual decay), "
            f"making long-term strategic reserves impractical."
        )
    if p4_score > 0.6:
        drivers.append(
            f"Low Substitutability: {component} is a highly bespoke, custom-engineered part; "
            f"no drop-in replacement exists in the open market."
        )
    if p5_score > 0.6:
        drivers.append(
            f"Inertia Risk: Specialised engineering requirements for {component} lead to "
            f"procurement lead times exceeding 12 months."
        )
    if p6_score > 0.6:
        drivers.append(
            f"Regulatory Bottleneck: {component} is subject to dual-use export controls "
            f"(ITAR / EU dual-use) that could be revoked with little notice."
        )
    if p7_score > 0.8:
        drivers.append(
            f"Critical System Failure Risk: {component} is a 'life-blood' bottleneck; "
            f"any disruption cascades immediately through the system."
        )

    # Hard clamp — pillar scores must always be in [0.0, 1.0]
    p1_score = max(0.0, min(1.0, p1_score))
    p2_score = max(0.0, min(1.0, p2_score))
    p3_score = max(0.0, min(1.0, p3_score))
    p4_score = max(0.0, min(1.0, p4_score))
    p5_score = max(0.0, min(1.0, p5_score))
    p6_score = max(0.0, min(1.0, p6_score))
    p7_score = max(0.0, min(1.0, p7_score))

    return {
        "pillar_scores": {
            "hhi":             round(p1_score, 3),
            "geopolitics":     round(p2_score, 3),
            "shelf_life":      round(p3_score, 3),
            "substitutability": round(p4_score, 3),
            "lead_time":       round(p5_score, 3),
            "regulatory":      round(p6_score, 3),
            "impact":          round(p7_score, 3),
        },
        "key_drivers": drivers,
        "raw": {
            "hhi":                 hhi,
            "hhi_source":          hhi_source,
            "n_suppliers":         n_suppliers,
            "russia_exposure":     any(c.upper() in ["RUSSIA", "RUSSIAN FEDERATION"]
                                       for c in countries if isinstance(c, str)),
            "china_exposure":      any(c.upper() in ["CHINA", "CN", "PEOPLE'S REPUBLIC OF CHINA"]
                                       for c in countries if isinstance(c, str)),
            "taiwan_exposure":     any(c.upper() in ["TAIWAN", "TAIWAN, PROVINCE OF CHINA"]
                                       for c in countries if isinstance(c, str)),
            "australia_exposure":  any(c.upper() in ["AUSTRALIA"]
                                       for c in countries if isinstance(c, str)),
            "has_trade_data":      trade_data is not None,
        },
    }


# ─── Dependency Graph ─────────────────────────────────────────────────────────

def load_dependency_graph(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    base_dir = data_dir or (Path(__file__).resolve().parents[1] / "data" / "segments" / "cryogenics")
    dep_file = base_dir / "dependencies.json"
    if not dep_file.exists():
        return {"dependencies": []}
    with open(dep_file) as f:
        return json.load(f)


# ─── Recursive Risk Propagation (ARI) ─────────────────────────────────────────

def get_recursive_risk_metrics(
    component: str,
    region: str = "EU",
    memo: Optional[Dict] = None,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Level 4: Recursive 'Chain of Dependency' scoring.
    ARI = (own_avg_pillar_score + max_child_avg_score) / 2
    """
    if memo is None:
        memo = {}
    if component in memo:
        return memo[component]

    base = get_component_risk_metrics(component, region, data_dir=data_dir)
    if "error" in base:
        base = {
            "pillar_scores": {k: 0.5 for k in
                              ["hhi", "geopolitics", "shelf_life", "substitutability",
                               "lead_time", "regulatory", "impact"]},
            "key_drivers": ["Unknown component — data not yet extracted"],
            "raw": {},
        }

    # Find children in the dependency graph
    graph         = load_dependency_graph(data_dir=data_dir)
    children_names: List[str] = []
    for entry in graph.get("dependencies", []):
        if entry["parent"].lower() == component.lower():
            children_names = entry.get("children", [])
            break

    # Recursively score children
    child_results = []
    for child in children_names:
        child_metrics = get_recursive_risk_metrics(child, region, memo, data_dir=data_dir)
        child_results.append({"name": child, "metrics": child_metrics})

    # ARI calculation
    base_avg         = sum(base["pillar_scores"].values()) / 7
    accumulated_score = base_avg
    spof:  Optional[str]  = None
    max_child_score: float = 0.0

    if child_results:
        for child in child_results:
            child_avg = sum(child["metrics"]["pillar_scores"].values()) / 7
            if child_avg > max_child_score:
                max_child_score = child_avg
                spof            = child["name"]
        accumulated_score = (base_avg + max_child_score) / 2

    drivers = list(base["key_drivers"])
    if spof:
        drivers.append(
            f"Chain Vulnerability: Critical bottleneck in sub-component '{spof}' "
            f"(avg pillar score {max_child_score:.2f})."
        )

    result = {
        "component":        component,
        "base_avg_score":   round(base_avg, 3),
        "accumulated_score": round(accumulated_score, 3),
        "spof":             spof,
        "pillar_scores":    base["pillar_scores"],
        "key_drivers":      drivers,
        "children":         [c["name"] for c in child_results],
        "raw":              base["raw"],
    }
    memo[component] = result
    return result


# ─── Perspective Comparison ───────────────────────────────────────────────────

def get_perspective_comparison(
    component: str,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run the full 7-pillar scoring for EU, US, and China perspectives
    on the same component and return a structured comparison.

    This implements methodology section 5.3: Perspective-Driven Geopolitical Comparison.
    """
    perspectives = ["EU", "US", "CHINA"]
    scores:   Dict[str, float] = {}
    pillars:  Dict[str, Dict]  = {}
    drivers:  Dict[str, List]  = {}

    RISK_WEIGHTS = {
        "hhi": 0.25, "geopolitics": 0.20, "shelf_life": 0.15,
        "substitutability": 0.15, "lead_time": 0.10, "regulatory": 0.10, "impact": 0.05,
    }

    for region in perspectives:
        recursive = get_recursive_risk_metrics(component, region, data_dir=data_dir)
        metrics   = get_component_risk_metrics(component, region, data_dir=data_dir)
        if "error" in metrics:
            scores[region]  = 0.0
            pillars[region] = {k: 0.0 for k in RISK_WEIGHTS}
            drivers[region] = [metrics["error"]]
        else:
            ps        = metrics["pillar_scores"]
            s_base    = sum(ps[p] * RISK_WEIGHTS[p] for p in RISK_WEIGHTS)
            ari       = recursive["accumulated_score"]
            blended   = round((s_base + ari) / 2, 3)
            scores[region]  = blended
            pillars[region] = ps
            drivers[region] = metrics["key_drivers"]

    score_values = [v for v in scores.values() if v > 0]
    divergence   = round(max(score_values) - min(score_values), 3) if len(score_values) > 1 else 0.0

    # Identify the pillar with the most variance across perspectives
    pillar_names = ["hhi", "geopolitics", "shelf_life", "substitutability",
                    "lead_time", "regulatory", "impact"]
    max_variance_pillar = max(
        pillar_names,
        key=lambda p: max(
            (pillars[r].get(p, 0) for r in perspectives), default=0
        ) - min(
            (pillars[r].get(p, 0) for r in perspectives), default=0
        ),
    )

    return {
        "component":            component,
        "scores":               scores,
        "pillar_scores":        pillars,
        "drivers":              drivers,
        "divergence":           divergence,
        "divergence_label":     "High" if divergence > 0.3 else ("Medium" if divergence > 0.15 else "Low"),
        "key_divergence_pillar": max_variance_pillar,
        "adversary_configs":    {r: _resolve_adversaries(r) for r in perspectives},
    }


def get_segment_perspective_comparison(
    data_dir: Path,
    scenario: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Run get_perspective_comparison for every component that has a supplier file
    in the given data_dir.  Returns a list sorted by EU score descending.
    Optionally applies a scenario overlay to the scores.
    """
    suppliers_dir = data_dir / "suppliers"
    if not suppliers_dir.exists():
        return []

    # Import SCENARIOS here to avoid circular imports
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from scoring import SCENARIOS
    except ImportError:
        SCENARIOS = {}

    results = []
    for f in sorted(suppliers_dir.glob("*_suppliers.json")):
        component_name = normalize_component_name(f.stem.replace("_suppliers", ""))
        comparison     = get_perspective_comparison(component_name, data_dir=data_dir)

        # Apply scenario overlay if provided
        if scenario and scenario in SCENARIOS:
            sc_def = SCENARIOS[scenario]

            # Load raw supplier data for exposure flags
            try:
                with open(f) as fh:
                    sdata = json.load(fh)
                suppliers = sdata.get("suppliers", [])
                # Use beneficial_owner_country when available (catches hidden foreign control)
                countries = [
                    (s.get("beneficial_owner_country") or s.get("country") or "").upper()
                    for s in suppliers
                    if s.get("beneficial_owner_country") or s.get("country")
                ]
                russia_exp   = any(c in ["RUSSIA", "RUSSIAN FEDERATION"] for c in countries)
                china_exp    = any(c in ["CHINA", "CN", "PEOPLE'S REPUBLIC OF CHINA"] for c in countries)
                taiwan_exp   = any(c in ["TAIWAN", "TAIWAN, PROVINCE OF CHINA"] for c in countries)
                australia_exp = any(c in ["AUSTRALIA"] for c in countries)
            except Exception:
                russia_exp = china_exp = taiwan_exp = australia_exp = False

            comp_lower = component_name.lower()
            perspectives_to_apply = sc_def.get("perspectives", [])

            for region in ["EU", "US", "CHINA"]:
                if region not in perspectives_to_apply and "GLOBAL" not in perspectives_to_apply:
                    continue
                cond = sc_def.get("condition", "always")
                geo_score = comparison.get("pillar_scores", {}).get(region, {}).get("geopolitics", 0)
                triggered = (
                    cond == "always"
                    or (cond == "russia_exposure" and russia_exp)
                    or (cond == "china_exposure" and china_exp)
                    or (cond == "taiwan_exposure" and taiwan_exp)
                    or (cond == "australia_exposure" and australia_exp)
                    or (cond == "geopolitics_high" and geo_score > 0.5)
                    or (cond == "helium3_component" and any(
                        k in comp_lower for k in ["helium-3", "helium 3", "he-3", "he3"]
                    ))
                )
                if triggered:
                    delta = sc_def.get("delta", 0)
                    comparison["scores"][region] = round(
                        min(1.0, comparison["scores"].get(region, 0) + delta), 3
                    )

        results.append(comparison)

    results.sort(key=lambda x: x["scores"].get("EU", 0), reverse=True)
    return results


# ─── Main (quick test) ────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = get_component_risk_metrics("Helium-3", region="EU")
    print(json.dumps(result, indent=2))
    print("\n--- Perspective Comparison ---")
    comp = get_perspective_comparison("Helium-3")
    print(json.dumps(comp, indent=2))
