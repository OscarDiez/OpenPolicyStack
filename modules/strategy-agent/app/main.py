"""
main.py — Strategy & Feedback Agent (SFA) — IA Edition v0.3.0

Endpoints:
  GET  /health          liveness check
  GET  /indicators      fetch live Eurostat + CORDIS indicators
  POST /assess          score policy options (MCDA)
  POST /sensitivity     weight sensitivity analysis
  POST /brief           deterministic evidence-linked brief (always works)
  POST /brief/llm       LLM-enhanced brief (requires ANTHROPIC_API_KEY)
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
from app.llm_brief import generate_llm_brief

app = FastAPI(
    title="Strategy & Feedback Agent — IA Edition",
    version="0.3.0",
    description=(
        "AI microservice for EU Impact Assessment option comparison. "
        "Implements MCDA scoring, sensitivity analysis, deterministic "
        "evidence-linked brief generation, and an LLM-enhanced brief "
        "endpoint constrained strictly to structured scoring outputs."
    ),
)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.3.0"}


# ─── Indicators ───────────────────────────────────────────────────────────────

@app.get("/indicators", response_model=list[IndicatorValue])
def get_indicators(geo: str = "EU27_2020"):
    """Fetch all live Quantum Act pilot indicators from Eurostat and CORDIS."""
    return fetch_all_indicators(geo=geo)


# ─── Assess ───────────────────────────────────────────────────────────────────

@app.post("/assess", response_model=AssessResponse)
def assess(req: AssessRequest):
    """
    Score all policy options in the IA blueprint against IA criteria.
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

    option_scores = score_options(blueprint=req.blueprint, indicators=indicators)
    preferred     = next((os for os in option_scores if os.rank == 1), option_scores[0])
    drivers       = generate_drivers(preferred)
    evidence      = build_evidence(option_scores, indicators)
    assumptions   = collect_assumptions(option_scores)

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
    """Run weight sensitivity analysis on already-scored options."""
    if not req.option_scores:
        raise HTTPException(status_code=422, detail="option_scores must not be empty.")

    response             = run_sensitivity(req.option_scores, req.weight_grid)
    response.run_id      = req.run_id
    response.scenario_id = req.scenario_id
    return response


# ─── Brief (deterministic) ────────────────────────────────────────────────────

@app.post("/brief", response_model=BriefResponse)
def brief(req: BriefRequest):
    """
    Generate a deterministic evidence-linked markdown brief from structured
    scoring outputs. No LLM involved — always works, fully traceable.
    """
    if not req.option_scores:
        raise HTTPException(status_code=422, detail="option_scores must not be empty.")

    preferred = next(
        (os for os in req.option_scores if os.rank == 1), req.option_scores[0]
    )

    proxy_count    = sum(1 for e in req.evidence if e.quality_flag in ("proxy", "assumption"))
    total_evidence = len(req.evidence)
    quality_note   = (
        f"{total_evidence - proxy_count}/{total_evidence} indicators verified from official sources."
        if total_evidence > 0 else "No indicators attached."
    )

    driver_lines = "\n".join(
        f"- **{d.criterion}** ({d.direction}, contribution: {d.contribution:.3f})"
        + (f" — {d.source_ref}" if d.source_ref else "")
        for d in req.drivers
    ) or "_No drivers computed._"

    ranking_lines = "\n".join(
        f"| {os.rank} | {os.option_name} | {os.weighted_total:+.3f} | {os.status} |"
        for os in sorted(req.option_scores, key=lambda x: x.rank)
    )

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


# ─── Brief (LLM-enhanced) ─────────────────────────────────────────────────────

@app.post("/brief/llm", response_model=BriefResponse)
def brief_llm(req: BriefRequest):
    """
    Generate an LLM-enhanced brief using the Anthropic API.

    The LLM receives ONLY structured scoring outputs and is constrained
    by a strict system prompt to introduce no new facts. Falls back to
    the deterministic /brief output if the API key is missing or the
    API call fails, ensuring the endpoint never breaks the orchestrator.

    Requires ANTHROPIC_API_KEY environment variable to be set.
    """
    if not req.option_scores:
        raise HTTPException(status_code=422, detail="option_scores must not be empty.")

    try:
        llm_markdown = generate_llm_brief(req)
        brief_md = llm_markdown + "\n\n---\n_Brief generated by LLM from structured scoring outputs only. All claims are traceable to the evidence payload._"

    except Exception as exc:
        # Graceful fallback — return deterministic brief with warning
        preferred = next(
            (os for os in req.option_scores if os.rank == 1), req.option_scores[0]
        )
        ranking_lines = "\n".join(
            f"| {os.rank} | {os.option_name} | {os.weighted_total:+.3f} | {os.status} |"
            for os in sorted(req.option_scores, key=lambda x: x.rank)
        )
        brief_md = f"""## Impact Assessment Brief — {req.scenario_id} (fallback)

> **Note:** LLM generation unavailable ({str(exc)}). Returning deterministic brief.

**Preferred Option:** {preferred.option_name} (score: {preferred.weighted_total:+.3f})

### Option Ranking

| Rank | Option | Score | Status |
|------|--------|-------|--------|
{ranking_lines}

---
_Fallback brief generated from structured scoring outputs only._
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


# ─── Brief (PDF export) ───────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse
import io

@app.post("/brief/pdf")
def brief_pdf(req: BriefRequest):
    """
    Generate a professional 3-page PDF brief:
      Page 1 — Executive summary (LLM-generated narrative)
      Page 2 — Full MCDA scoring table with rationales
      Page 3 — Evidence payload and assumptions

    Falls back to deterministic brief text if LLM is unavailable.
    Returns a downloadable PDF file.
    """
    from app.pdf_brief import generate_pdf_brief

    if not req.option_scores:
        raise HTTPException(status_code=422, detail="option_scores must not be empty.")

    # Get LLM brief or fall back to deterministic
    try:
        llm_text = generate_llm_brief(req)
    except Exception:
        preferred = next(
            (os for os in req.option_scores if os.rank == 1), req.option_scores[0]
        )
        llm_text = (
            f"Preferred Option: {preferred.option_name} "
            f"(score: {preferred.weighted_total:+.3f})\n\n"
            "This brief was generated from structured scoring outputs only. "
            "All claims are traceable to the evidence payload."
        )

    pdf_bytes = generate_pdf_brief(req, llm_text)

    filename = f"IA_Brief_{req.scenario_id}_{req.run_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )