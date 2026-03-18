"""
main.py — Strategy & Feedback Agent (SFA) — IA edition.

Endpoints:
  GET  /health          liveness check
  POST /assess          score policy options against IA criteria (MCDA)
  POST /sensitivity     weight sensitivity analysis on option rankings
  POST /brief           generate evidence-linked markdown brief
  POST /indicators      fetch live Eurostat + CORDIS indicators (utility)
"""

from fastapi import FastAPI, HTTPException
from app.schemas import (
    AssessRequest, AssessResponse,
    SensitivityRequest, SensitivityResponse,
    BriefRequest, BriefResponse,
    IndicatorValue,
)
from app.scoring import score_options
from app.sensitivity import run_sensitivity
from app.explain import generate_drivers
from app.evidence import build_evidence, collect_assumptions
from app.indicator_catalogue import fetch_all_indicators

app = FastAPI(
    title="Strategy & Feedback Agent — IA Edition",
    version="0.2.0",
    description=(
        "AI microservice for EU Impact Assessment option comparison. "
        "Implements MCDA scoring, sensitivity analysis, and evidence-linked "
        "brief generation aligned with the EU Better Regulation framework."
    ),
)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


# ─── Indicators (utility endpoint) ───────────────────────────────────────────

@app.get("/indicators", response_model=list[IndicatorValue])
def get_indicators(geo: str = "EU27_2020"):
    """
    Fetch all live Quantum Act pilot indicators from Eurostat and CORDIS.
    Useful for inspecting the data layer independently.
    """
    return fetch_all_indicators(geo=geo)


# ─── Assess ───────────────────────────────────────────────────────────────────

@app.post("/assess", response_model=AssessResponse)
def assess(req: AssessRequest):
    """
    Score all policy options in the IA blueprint against IA criteria.
    Returns ranked option scores, top drivers, assumptions, and evidence.

    If req.indicators is empty, live indicators are fetched automatically.
    """
    indicators = req.indicators
    if not indicators:
        indicators = fetch_all_indicators()

    if not req.blueprint.policy_options:
        raise HTTPException(
            status_code=422,
            detail="blueprint.policy_options must contain at least one option.",
        )

    option_scores = score_options(
        blueprint=req.blueprint,
        indicators=indicators,
    )

    preferred = next((os for os in option_scores if os.rank == 1), option_scores[0])
    drivers   = generate_drivers(preferred)
    evidence  = build_evidence(option_scores, indicators)
    assumptions = collect_assumptions(option_scores)

    return AssessResponse(
        run_id=req.run_id,
        scenario_id=req.scenario_id,
        option_scores=option_scores,
        drivers=drivers,
        assumptions=assumptions,
        evidence=evidence,
    )


# ─── Sensitivity ──────────────────────────────────────────────────────────────

@app.post("/sensitivity", response_model=SensitivityResponse)
def sensitivity(req: SensitivityRequest):
    """
    Run weight sensitivity analysis on already-scored options.
    Tests ranking stability across multiple weight scenarios.
    """
    if not req.option_scores:
        raise HTTPException(
            status_code=422,
            detail="option_scores must not be empty.",
        )

    response = run_sensitivity(
        option_scores=req.option_scores,
        weight_grid=req.weight_grid,
    )
    response.run_id      = req.run_id
    response.scenario_id = req.scenario_id
    return response


# ─── Brief ────────────────────────────────────────────────────────────────────

@app.post("/brief", response_model=BriefResponse)
def brief(req: BriefRequest):
    """
    Generate a short markdown brief from structured scoring outputs.
    The brief is generated ONLY from structured fields — no new facts
    are introduced (no hallucination risk).
    """
    if not req.option_scores:
        raise HTTPException(
            status_code=422,
            detail="option_scores must not be empty.",
        )

    preferred = next(
        (os for os in req.option_scores if os.rank == 1),
        req.option_scores[0],
    )

    # Evidence quality summary
    proxy_count = sum(
        1 for e in req.evidence
        if e.quality_flag in ("proxy", "assumption")
    )
    total_evidence = len(req.evidence)
    quality_note = (
        f"{total_evidence - proxy_count}/{total_evidence} indicators verified from official sources."
        if total_evidence > 0 else "No indicators attached."
    )

    # Top drivers summary
    driver_lines = "\n".join(
        f"- **{d.criterion}** ({d.direction}, contribution: {d.contribution:.3f})"
        + (f" — {d.source_ref}" if d.source_ref else "")
        for d in req.drivers
    ) or "_No drivers computed._"

    # Option ranking table
    ranking_lines = "\n".join(
        f"| {os.rank} | {os.option_name} | {os.weighted_total:+.3f} | {os.status} |"
        for os in sorted(req.option_scores, key=lambda x: x.rank)
    )

    # Assumptions summary
    assumption_lines = "\n".join(
        f"- {a}" for a in req.assumptions
    ) or "_No explicit assumptions recorded._"

    brief_md = f"""## Impact Assessment Brief — {req.scenario_id}

**Objective:** {req.objective or "EU Quantum Act option comparison"}
**Run ID:** {req.run_id}

---

### Preferred Option
**{preferred.option_name}** (weighted score: {preferred.weighted_total:+.3f})

### Option Ranking

| Rank | Option | Score | Status |
|------|--------|-------|--------|
{ranking_lines}

### Key Drivers (preferred option)

{driver_lines}

### Evidence Quality
{quality_note}

### Assumptions
{assumption_lines}

---
_Brief generated from structured scoring outputs only. All claims are traceable to the evidence payload._
"""

    return BriefResponse(
        run_id=req.run_id,
        scenario_id=req.scenario_id,
        brief_markdown=brief_md,
        option_scores=req.option_scores,
        drivers=req.drivers,
        assumptions=req.assumptions,
        evidence=req.evidence,
    )
