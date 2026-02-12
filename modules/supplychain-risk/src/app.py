from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from .scoring import score_component

app = FastAPI(
    title="Supply-Chain Risk Service (Quantum)",
    version="0.1.0",
    description="Minimal runnable skeleton for OpenPolicyStack integration."
)


class ScoreRequest(BaseModel):
    region: str
    segment: str
    scenario: Optional[str] = None


class ScoreResponse(BaseModel):
    region: str
    segment: str
    scenario: Optional[str] = None
    risk_score: float
    key_drivers: List[str]
    confidence: str


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "supply-chain-risk", "version": "0.1.0"}


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    risk_score, drivers, confidence = score_component(
        region=req.region,
        segment=req.segment,
        scenario=req.scenario,
    )
    return ScoreResponse(
        region=req.region,
        segment=req.segment,
        scenario=req.scenario,
        risk_score=risk_score,
        key_drivers=drivers,
        confidence=confidence,
    )


@app.post("/brief")
def brief(req: ScoreRequest) -> Dict[str, Any]:
    risk_score, drivers, confidence = score_component(
        region=req.region,
        segment=req.segment,
        scenario=req.scenario,
    )

    brief_text = (
        f"Risk score (0–1): {risk_score:.2f} ({confidence} confidence). "
        f"Main drivers: {', '.join(drivers) if drivers else 'n/a'}. "
        "MVP skeleton using a small curated demo dataset; logic and data will be expanded."
    )

    return {
        "region": req.region,
        "segment": req.segment,
        "scenario": req.scenario,
        "risk_score": risk_score,
        "confidence": confidence,
        "drivers": drivers,
        "brief": brief_text,
    }
