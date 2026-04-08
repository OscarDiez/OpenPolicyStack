"""
scoring.py — MCDA scoring engine for the Strategy & Feedback Agent.

Scoring rules are threshold-driven, using live indicator values to produce
scenario-sensitive scores. Rankings change across baseline, adverse, and
recovery scenarios as intended by the EU Better Regulation IA framework.

Scoring scale: -2 (strongly negative) to +2 (strongly positive)
Default weights: economic 0.25, competitiveness 0.25, social 0.15,
                 feasibility 0.15, environmental 0.10, coherence 0.10
"""

from app.schemas import IABlueprint, IndicatorValue, OptionScore, CriteriaScore
from app.config import DEFAULT_WEIGHTS, SCORE_MIN, SCORE_MAX


def _clamp(score: float) -> float:
    return max(SCORE_MIN, min(SCORE_MAX, score))


def _get_indicator(indicators: list, indicator_id: str):
    for ind in indicators:
        if ind.indicator_id == indicator_id:
            return ind.value
    return None


def _score_option(option_id: str, indicators: list) -> dict:
    """
    Return a dict mapping criterion -> (score, rationale, evidence_ids, assumption)
    using live indicator values and threshold logic to produce scenario-sensitive scores.
    """
    gerd         = _get_indicator(indicators, "gerd_pct_gdp") or 2.22
    rd_personnel = _get_indicator(indicators, "rd_personnel_pct") or 1.43
    hightech     = _get_indicator(indicators, "hightech_employment_pct") or 4.8
    projects     = _get_indicator(indicators, "cordis_quantum_projects") or 320
    funding      = _get_indicator(indicators, "cordis_quantum_funding_meur") or 1200

    # Threshold flags
    gerd_declining  = gerd < 2.0
    gerd_recovering = gerd > 2.35
    funding_low     = funding < 1000
    funding_high    = funding > 1400
    projects_low    = projects < 300
    hightech_low    = hightech < 4.5
    hightech_high   = hightech > 5.0

    # ── opt-0: Baseline — no new intervention ────────────────────────────────
    if option_id == "opt-0":
        econ_score = -1.0 if gerd_declining else 0.0
        econ_rat   = (
            f"No new spending; GERD declining to {gerd:.2f}% GDP risks further contraction without intervention."
            if gerd_declining else
            f"No new spending; GERD at {gerd:.2f}% GDP continues on current trajectory."
        )
        soc_score = -1.0 if hightech_low else 0.0
        soc_rat   = (
            f"R&D personnel at {rd_personnel:.2f}% active pop; declining high-tech employment ({hightech:.1f}%) signals structural weakening."
            if hightech_low else
            f"R&D personnel at {rd_personnel:.2f}% active pop; no structural change expected."
        )
        comp_score = -2.0 if (funding_low or projects_low) else -1.0
        comp_rat   = (
            f"With only {int(projects)} quantum projects and {funding:.0f}M EUR funded, absence of framework accelerates falling behind US/China."
            if (funding_low or projects_low) else
            f"With {int(projects)} quantum projects and {funding:.0f}M EUR funded, absence of dedicated framework risks falling behind US/China."
        )
        return {
            "economic":        (econ_score, econ_rat, ["gerd_pct_gdp"], None),
            "social":          (soc_score, soc_rat, ["rd_personnel_pct"], None),
            "environmental":   (0.0, "No regulatory change; environmental impact remains as-is.", [], "No direct indicator available; score based on domain knowledge."),
            "competitiveness": (comp_score, comp_rat, ["cordis_quantum_projects", "cordis_quantum_funding_meur"], None),
            "feasibility":     (2.0, "Baseline requires no implementation effort.", [], "No direct indicator available; score based on domain knowledge."),
            "coherence":       (0.0, "Consistent with existing EU policy but misses Quantum Flagship ambition.", [], "No direct indicator available; score based on domain knowledge."),
        }

    # ── opt-1: Coordination only — voluntary frameworks ──────────────────────
    if option_id == "opt-1":
        econ_score = 0.0 if gerd_declining else 1.0
        econ_rat   = (
            f"Soft coordination insufficient to arrest GERD decline from {gerd:.2f}% GDP; voluntary measures lack enforcement."
            if gerd_declining else
            f"Soft coordination expected to modestly increase GERD above {gerd:.2f}% GDP via improved funding alignment."
        )
        comp_score = 0.0 if projects_low else 1.0
        comp_rat   = (
            f"Only {int(projects)} active CORDIS quantum projects; voluntary framework improves visibility but lacks enforcement under constrained conditions."
            if projects_low else
            f"Aligning {int(projects)} existing CORDIS quantum projects under a voluntary framework improves visibility but lacks enforcement."
        )
        return {
            "economic":        (econ_score, econ_rat, ["gerd_pct_gdp"], None),
            "social":          (1.0, f"Voluntary talent pipelines could raise R&D personnel (currently {rd_personnel:.2f}% active pop) through mobility schemes.", ["rd_personnel_pct"], None),
            "environmental":   (0.0, "Coordination option has negligible direct environmental impact.", [], "No direct indicator available; score based on domain knowledge."),
            "competitiveness": (comp_score, comp_rat, ["cordis_quantum_projects"], None),
            "feasibility":     (2.0, "Voluntary framework is low-risk and fast to implement.", [], "No direct indicator available; score based on domain knowledge."),
            "coherence":       (1.0, "Consistent with existing EU open-coordination method.", [], "No direct indicator available; score based on domain knowledge."),
        }

    # ── opt-2: Light regulation — standardisation and certification ───────────
    if option_id == "opt-2":
        # Economic: strongest when investment base is growing
        econ_score = 2.0 if (gerd_recovering and funding_high) else 1.0
        econ_rat   = (
            f"Standardisation unlocks full value of growing {funding:.0f}M EUR quantum investment base; GERD at {gerd:.2f}% provides strong fiscal foundation."
            if (gerd_recovering and funding_high) else
            f"Standardisation reduces fragmentation costs; builds on {funding:.0f}M EUR quantum investment base."
        )
        # Social: strongest when labour pool is large
        soc_score = 2.0 if hightech_high else 1.0
        soc_rat   = (
            f"Certification requirements create skilled workforce demand; strong high-tech employment at {hightech:.1f}% provides deep labour base."
            if hightech_high else
            f"Certification requirements create skilled workforce demand; high-tech employment at {hightech:.1f}% provides labour base."
        )
        # Coherence: weaker under adverse as voluntary standards lose enforceability
        coh_score = 1.0 if gerd_declining else 2.0
        coh_rat   = (
            "Standards-based approach less enforceable under fiscal pressure; coherence with Digital Decade targets constrained."
            if gerd_declining else
            "Fully coherent with NIS2, Cyber Resilience Act, and Digital Decade targets."
        )
        return {
            "economic":        (econ_score, econ_rat, ["gerd_pct_gdp", "cordis_quantum_funding_meur"], None),
            "social":          (soc_score, soc_rat, ["hightech_employment_pct"], None),
            "environmental":   (1.0, "Energy-efficiency standards for quantum hardware reduce footprint.", [], "No direct indicator available; score based on domain knowledge."),
            "competitiveness": (2.0, f"Mandatory standards position EU as global norm-setter in quantum, leveraging {int(projects)} active projects.", ["cordis_quantum_projects", "cordis_quantum_funding_meur"], None),
            "feasibility":     (1.0, "Manageable compliance burden; existing ETSI/CEN structures can absorb.", [], "No direct indicator available; score based on domain knowledge."),
            "coherence":       (coh_score, coh_rat, [], "No direct indicator available; score based on domain knowledge."),
        }

    # ── opt-3: Comprehensive regulation — EU Quantum Agency ──────────────────
    if option_id == "opt-3":
        econ_rat = (
            f"Dedicated agency and mandatory procurement rules provide strongest counter-cyclical stimulus when GERD is declining to {gerd:.2f}% GDP."
            if gerd_declining else
            f"Dedicated agency and procurement rules expected to significantly increase GERD above {gerd:.2f}% GDP in quantum-specific sectors."
        )
        soc_rat = (
            f"Mandatory training and certification most critical when high-tech employment is declining ({hightech:.1f}%); R&D personnel at {rd_personnel:.2f}% needs structural support."
            if hightech_low else
            f"Mandatory training and certification boosts skilled employment; R&D personnel ratio ({rd_personnel:.2f}%) projected to rise."
        )
        return {
            "economic":        (2.0, econ_rat, ["gerd_pct_gdp", "cordis_quantum_funding_meur"], None),
            "social":          (2.0, soc_rat, ["rd_personnel_pct", "hightech_employment_pct"], None),
            "environmental":   (1.0, "Comprehensive framework includes sustainability criteria for quantum hardware.", [], "No direct indicator available; score based on domain knowledge."),
            "competitiveness": (2.0, f"Strongest intervention; {int(projects)} quantum projects brought under single governance with mandatory certification and EU procurement preference.", ["cordis_quantum_projects", "cordis_quantum_funding_meur"], None),
            "feasibility":     (-1.0, "High implementation complexity; agency setup requires 2-4 years and significant institutional coordination.", [], "No direct indicator available; score based on domain knowledge."),
            "coherence":       (1.0, "Coherent with EU strategic autonomy agenda but creates new regulatory layer.", [], "No direct indicator available; score based on domain knowledge."),
        }

    return {c: (0.0, "Unknown option.", [], "No indicator available.")
            for c in ["economic", "social", "environmental", "competitiveness", "feasibility", "coherence"]}


def score_options(blueprint: IABlueprint,
                  indicators: list[IndicatorValue]) -> list[OptionScore]:
    """Score all policy options and return a ranked list of OptionScore objects."""
    weights = DEFAULT_WEIGHTS
    results = []

    for option in blueprint.policy_options:
        raw = _score_option(option.id, indicators)

        criteria_scores = []
        weighted_total  = 0.0

        for criterion, (score, rationale, evidence_ids, assumption) in raw.items():
            clamped = _clamp(score)
            weighted_total += clamped * weights.get(criterion, 0.0)
            criteria_scores.append(CriteriaScore(
                criterion    = criterion,
                score        = clamped,
                rationale    = rationale,
                evidence_ids = evidence_ids,
                assumption   = assumption,
            ))

        results.append(OptionScore(
            option_id       = option.id,
            option_name     = option.name,
            criteria_scores = criteria_scores,
            weighted_total  = round(weighted_total, 3),
            rank            = 0,
            status          = "alternative",
        ))

    results.sort(key=lambda x: (
    x.weighted_total,
    sum(cs.score for cs in x.criteria_scores if cs.criterion in ("economic", "social"))
), reverse=True)
    
    for i, opt in enumerate(results):
        opt.rank   = i + 1
        opt.status = (
            "preferred"   if i == 0 else
            "baseline"    if opt.option_id == "opt-0" else
            "alternative"
        )

    return results