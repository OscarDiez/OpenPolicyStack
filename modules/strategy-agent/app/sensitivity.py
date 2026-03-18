"""
sensitivity.py — Sensitivity analysis on MCDA criterion weights.

Tests how option rankings change across different weight scenarios.
Returns a SensitivityResponse with per-scenario rankings and a
stability summary indicating whether the top option is robust.
"""

from typing import List, Dict, Optional
from app.schemas import (
    OptionScore, SensitivityResult, SensitivityResponse, IACriterion
)
from app.config import SENSITIVITY_WEIGHT_GRID


def _rescore(
    option_scores: List[OptionScore],
    weights: Dict[str, float],
) -> List[Dict]:
    """
    Re-compute weighted totals for each option under new weights.
    Returns list of {option_id, option_name, score, rank} sorted by score.
    """
    rescored = []
    for os in option_scores:
        total = 0.0
        for cs in os.criteria_scores:
            w = weights.get(cs.criterion, 1 / len(IACriterion))
            total += w * cs.score
        rescored.append({
            "option_id":   os.option_id,
            "option_name": os.option_name,
            "score":       round(total, 4),
        })

    rescored.sort(key=lambda x: x["score"], reverse=True)
    for rank, item in enumerate(rescored, start=1):
        item["rank"] = rank
    return rescored


def run_sensitivity(
    option_scores: List[OptionScore],
    weight_grid: Optional[List[Dict[str, float]]] = None,
) -> SensitivityResponse:
    """
    Run sensitivity analysis across the weight grid.
    If weight_grid is not provided, uses the default SENSITIVITY_WEIGHT_GRID.
    """
    grid = weight_grid or SENSITIVITY_WEIGHT_GRID

    # Identify baseline top option (rank 1 in original scoring)
    baseline_top = next(
        (os.option_id for os in option_scores if os.rank == 1), None
    )

    results: List[SensitivityResult] = []
    stable_count = 0

    for scenario in grid:
        label = scenario.get("label", "unnamed")
        weights = {k: v for k, v in scenario.items() if k != "label"}

        rankings = _rescore(option_scores, weights)
        top_in_scenario = rankings[0]["option_id"] if rankings else None
        ranking_stable = (top_in_scenario == baseline_top)

        if ranking_stable:
            stable_count += 1

        results.append(SensitivityResult(
            scenario_label=label,
            weights_used=weights,
            option_rankings=rankings,
            ranking_stable=ranking_stable,
            top_option_id=top_in_scenario or "",
        ))

    overall_stable = stable_count == len(results)
    stable_pct = round(100 * stable_count / len(results)) if results else 0

    summary = (
        f"Top-ranked option is consistent across {stable_count}/{len(results)} "
        f"weight scenarios ({stable_pct}%). "
        + ("Ranking is robust to weight variation." if overall_stable
           else "Ranking is sensitive to criterion weighting — "
                "review feasibility and competitiveness trade-offs.")
    )

    return SensitivityResponse(
        run_id="",        # filled in main.py
        scenario_id="",   # filled in main.py
        results=results,
        stable=overall_stable,
        summary=summary,
    )