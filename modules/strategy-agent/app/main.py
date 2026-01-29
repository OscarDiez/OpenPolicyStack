from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

app = FastAPI(title="Strategy & Feedback Agent", version="0.1.0")

class Driver(BaseModel):
    name: str
    direction: str
    value: Optional[float] = None
    source: Optional[str] = None

class EvidenceItem(BaseModel):
    type: str
    ref: Optional[str] = None
    path: Optional[str] = None
    note: Optional[str] = None

class Recommendation(BaseModel):
    id: str
    title: str
    priority: str
    rationale: str
    expected_impact: Dict[str, Any] = Field(default_factory=dict)

class Counterfactual(BaseModel):
    id: str
    changes: Dict[str, Any]
    predicted_kpi_delta: Dict[str, Any] = Field(default_factory=dict)
    predicted_risk_delta: Dict[str, Any] = Field(default_factory=dict)
    feasibility_checks: Dict[str, Any] = Field(default_factory=dict)
    explanation: str

class BaseRequest(BaseModel):
    run_id: str
    scenario_id: str
    objective: Optional[str] = None
    upstream_outputs: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)

class RecommendResponse(BaseModel):
    run_id: str
    scenario_id: str
    recommendations: List[Recommendation]
    drivers: List[Driver]
    assumptions: List[str]
    evidence: List[EvidenceItem]

class CounterfactualRequest(BaseRequest):
    current_state: Dict[str, Any] = Field(default_factory=dict)
    feasible_levers: Dict[str, Any] = Field(default_factory=dict)

class CounterfactualResponse(BaseModel):
    run_id: str
    scenario_id: str
    counterfactuals: List[Counterfactual]
    drivers: List[Driver]
    assumptions: List[str]
    evidence: List[EvidenceItem]

class BriefRequest(BaseModel):
    run_id: str
    scenario_id: str
    objective: Optional[str] = None
    selected_recommendation_ids: List[str] = Field(default_factory=list)
    upstream_outputs: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)

class BriefResponse(BaseModel):
    run_id: str
    scenario_id: str
    brief_markdown: str
    recommendations: List[Recommendation]
    drivers: List[Driver]
    assumptions: List[str]
    evidence: List[EvidenceItem]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: BaseRequest):
    seen = list(req.upstream_outputs.keys())
    recs = [
        Recommendation(
            id="rec-1",
            title="Prioritize resilient actions aligned with objective",
            priority="high",
            rationale="MVP stub. Replace with logic using simulator + risk outputs.",
            expected_impact={"note": "stub"},
        )
    ]
    drivers = [Driver(name="upstream_keys_seen", direction="unknown", value=float(len(seen)), source="upstream_outputs")]
    assumptions = [
        f"Scenario '{req.scenario_id}' treated as fixed exogenous conditions for this run.",
        "This response is an MVP stub.",
    ]
    evidence = [EvidenceItem(type="upstream_output", ref="upstream_outputs", path="keys", note=str(seen))]
    return RecommendResponse(
        run_id=req.run_id,
        scenario_id=req.scenario_id,
        recommendations=recs,
        drivers=drivers,
        assumptions=assumptions,
        evidence=evidence,
    )

@app.post("/counterfactual", response_model=CounterfactualResponse)
def counterfactual(req: CounterfactualRequest):
    levers = list(req.feasible_levers.keys())
    changes = {}
    if levers:
        first = levers[0]
        spec = req.feasible_levers.get(first, {})
        if isinstance(spec, dict) and "max" in spec:
            changes[first] = spec["max"]
        else:
            changes[first] = "adjust"

    cfs = [
        Counterfactual(
            id="cf-1",
            changes=changes,
            predicted_kpi_delta={"note": "stub"},
            predicted_risk_delta={"note": "stub"},
            feasibility_checks={"within_bounds": True},
            explanation="MVP stub counterfactual based on feasible_levers.",
        )
    ]
    drivers = [Driver(name="feasible_levers_count", direction="unknown", value=float(len(levers)), source="feasible_levers")]
    assumptions = [
        "Counterfactuals modify only actionable levers defined in feasible_levers.",
        "Scenario toggles (exogenous shocks) are handled upstream.",
    ]
    evidence = [EvidenceItem(type="note", note=f"feasible_levers={levers}")]
    return CounterfactualResponse(
        run_id=req.run_id,
        scenario_id=req.scenario_id,
        counterfactuals=cfs,
        drivers=drivers,
        assumptions=assumptions,
        evidence=evidence,
    )

@app.post("/brief", response_model=BriefResponse)
def brief(req: BriefRequest):
    seen = list(req.upstream_outputs.keys())
    recs = [
        Recommendation(
            id="rec-1",
            title="Prioritize resilient actions aligned with objective",
            priority="high",
            rationale="Stub recommendation used for brief generation.",
            expected_impact={"note": "stub"},
        )
    ]
    drivers = [Driver(name="upstream_keys_seen", direction="unknown", value=float(len(seen)), source="upstream_outputs")]
    assumptions = [f"Scenario '{req.scenario_id}' treated as fixed exogenous conditions for this run."]
    evidence = [EvidenceItem(type="upstream_output", ref="upstream_outputs", path="keys", note=str(seen))]
    brief_md = (
        "## Executive brief (MVP)\n\n"
        f"**Objective:** {req.objective or 'N/A'}\n\n"
        f"**Scenario:** {req.scenario_id}\n\n"
        "Stub brief. Will be generated from structured outputs in later iterations.\n"
    )
    return BriefResponse(
        run_id=req.run_id,
        scenario_id=req.scenario_id,
        brief_markdown=brief_md,
        recommendations=recs,
        drivers=drivers,
        assumptions=assumptions,
        evidence=evidence,
    )
