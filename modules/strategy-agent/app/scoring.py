"""
scoring.py — MCDA weighted additive scoring for IA option comparison.
Uses plain string criterion keys throughout.
"""

from typing import List, Dict
from app.schemas import (
    IABlueprint, IndicatorValue, OptionScore, CriteriaScore,
    OptionStatus, EvidenceItem
)
from app.config import DEFAULT_WEIGHTS, SCORE_MIN, SCORE_MAX


def _build_option_scores(option_id: str, indicators: Dict[str, IndicatorValue]) -> Dict:
    gerd_v  = indicators["gerd_pct_gdp"].value      if "gerd_pct_gdp"               in indicators else 2.22
    pers_v  = indicators["rd_personnel_pct"].value  if "rd_personnel_pct"            in indicators else 1.43
    ht_v    = indicators["hightech_employment_pct"].value if "hightech_employment_pct" in indicators else 4.8
    qp_v    = indicators["cordis_quantum_projects"].value if "cordis_quantum_projects" in indicators else 320.0
    qf_v    = indicators["cordis_quantum_funding_meur"].value if "cordis_quantum_funding_meur" in indicators else 1200.0

    if option_id == "opt-0":
        return {
            "economic":        (0.0,  f"No new spending; GERD at {gerd_v:.2f}% GDP continues on current trajectory.", ["gerd_pct_gdp"]),
            "social":          (0.0,  f"R&D personnel at {pers_v:.2f}% active pop; no structural change expected.", ["rd_personnel_pct"]),
            "environmental":   (0.0,  "No regulatory change; environmental impact remains as-is.", []),
            "competitiveness": (-1.0, f"With {qp_v:.0f} quantum projects and {qf_v:.0f}M EUR funded, absence of dedicated framework risks falling behind US/China.", ["cordis_quantum_projects", "cordis_quantum_funding_meur"]),
            "feasibility":     (2.0,  "Baseline requires no implementation effort.", []),
            "coherence":       (0.0,  "Consistent with existing EU policy but misses Quantum Flagship ambition.", []),
        }
    elif option_id == "opt-1":
        return {
            "economic":        (1.0,  f"Soft coordination expected to modestly increase GERD above {gerd_v:.2f}% GDP via improved funding alignment.", ["gerd_pct_gdp"]),
            "social":          (1.0,  f"Voluntary talent pipelines could raise R&D personnel (currently {pers_v:.2f}% active pop) through mobility schemes.", ["rd_personnel_pct"]),
            "environmental":   (0.0,  "Coordination option has negligible direct environmental impact.", []),
            "competitiveness": (1.0,  f"Aligning {qp_v:.0f} existing CORDIS quantum projects under a voluntary framework improves visibility but lacks enforcement.", ["cordis_quantum_projects"]),
            "feasibility":     (2.0,  "Voluntary framework is low-risk and fast to implement.", []),
            "coherence":       (1.0,  "Consistent with existing EU open-coordination method.", []),
        }
    elif option_id == "opt-2":
        return {
            "economic":        (1.0,  f"Standardisation reduces fragmentation costs; builds on {qf_v:.0f}M EUR quantum investment base.", ["gerd_pct_gdp", "cordis_quantum_funding_meur"]),
            "social":          (1.0,  f"Certification requirements create skilled workforce demand; high-tech employment at {ht_v:.1f}% provides labour base.", ["hightech_employment_pct"]),
            "environmental":   (1.0,  "Energy-efficiency standards for quantum hardware reduce footprint.", []),
            "competitiveness": (2.0,  f"Mandatory standards position EU as global norm-setter in quantum, leveraging {qp_v:.0f} active projects.", ["cordis_quantum_projects", "cordis_quantum_funding_meur"]),
            "feasibility":     (1.0,  "Manageable compliance burden; existing ETSI/CEN structures can absorb.", []),
            "coherence":       (2.0,  "Fully coherent with NIS2, Cyber Resilience Act, and Digital Decade targets.", []),
        }
    elif option_id == "opt-3":
        return {
            "economic":        (2.0,  f"Dedicated agency and procurement rules expected to significantly increase GERD above {gerd_v:.2f}% GDP in quantum-specific sectors.", ["gerd_pct_gdp", "cordis_quantum_funding_meur"]),
            "social":          (2.0,  f"Mandatory training and certification boosts skilled employment; R&D personnel ratio ({pers_v:.2f}%) projected to rise.", ["rd_personnel_pct", "hightech_employment_pct"]),
            "environmental":   (1.0,  "Comprehensive framework includes sustainability criteria for quantum hardware.", []),
            "competitiveness": (2.0,  f"Strongest intervention; {qp_v:.0f} quantum projects brought under single governance with mandatory certification and EU procurement preference.", ["cordis_quantum_projects", "cordis_quantum_funding_meur"]),
            "feasibility":     (-1.0, "High implementation complexity; agency setup requires 2-4 years and significant institutional coordination.", []),
            "coherence":       (1.0,  "Coherent with EU strategic autonomy agenda but creates new regulatory layer.", []),
        }
    else:
        return {c: (0.0, "Unknown option; neutral score assumed.", []) for c in DEFAULT_WEIGHTS}


def _clamp(value: float) -> float:
    return max(SCORE_MIN, min(SCORE_MAX, value))


def score_options(
    blueprint: IABlueprint,
    indicators: List[IndicatorValue],
    weights: Dict = None,
) -> List[OptionScore]:
    if weights is None:
        weights = DEFAULT_WEIGHTS

    ind_map: Dict[str, IndicatorValue] = {i.indicator_id: i for i in indicators}
    scored = []

    for option in blueprint.policy_options:
        raw_scores = _build_option_scores(option.id, ind_map)
        criteria_scores: List[CriteriaScore] = []
        weighted_total = 0.0

        for criterion, (raw_score, rationale, evidence_ids) in raw_scores.items():
            score = _clamp(raw_score)
            weight = weights.get(criterion, 1 / len(DEFAULT_WEIGHTS))
            weighted_total += weight * score

            cs = CriteriaScore(
                criterion=criterion,
                score=score,
                rationale=rationale,
                evidence_ids=evidence_ids,
                assumption=None if evidence_ids else (
                    "No direct indicator available; score based on domain knowledge."
                ),
            )
            criteria_scores.append(cs)

        scored.append((option, criteria_scores, round(weighted_total, 4)))

    scored.sort(key=lambda x: x[2], reverse=True)

    results: List[OptionScore] = []
    for rank, (option, criteria_scores, total) in enumerate(scored, start=1):
        if option.status == OptionStatus.BASELINE:
            status = OptionStatus.BASELINE
        elif rank == 1:
            status = OptionStatus.PREFERRED
        else:
            status = OptionStatus.ALTERNATIVE

        results.append(OptionScore(
            option_id=option.id,
            option_name=option.name,
            criteria_scores=criteria_scores,
            weighted_total=total,
            rank=rank,
            status=status,
        ))

    return results