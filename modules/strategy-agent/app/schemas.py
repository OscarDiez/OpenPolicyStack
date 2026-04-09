"""
schemas.py — Pydantic models for the IA-based Strategy & Feedback Agent.
All inputs and outputs are strictly typed. Every score must reference
at least one EvidenceItem or carry an explicit assumption tag.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class QualityFlag(str, Enum):
    VERIFIED   = "verified"    # value from official source, recent
    PROXY      = "proxy"       # estimated or derived value
    ASSUMPTION = "assumption"  # no data found, explicit assumption used
    STALE      = "stale"       # data older than 3 years


class SourceType(str, Enum):
    EUROSTAT = "eurostat"
    CORDIS   = "cordis"
    DERIVED  = "derived"
    MANUAL   = "manual"


class IACriterion(str, Enum):
    ECONOMIC        = "economic"
    SOCIAL          = "social"
    ENVIRONMENTAL   = "environmental"
    COMPETITIVENESS = "competitiveness"
    FEASIBILITY     = "feasibility"
    COHERENCE       = "coherence"


class OptionStatus(str, Enum):
    PREFERRED   = "preferred"
    ALTERNATIVE = "alternative"
    BASELINE    = "baseline"
    REJECTED    = "rejected"


# ─── Evidence & Provenance ────────────────────────────────────────────────────

class EvidenceItem(BaseModel):
    indicator_id:  str
    source_type:   SourceType
    source_ref:    str                         # e.g. "eurostat:rd_e_gerdtot"
    field_path:    str                         # e.g. "EU27_2020.2022"
    value:         Optional[float] = None
    unit:          Optional[str]   = None
    quality_flag:  QualityFlag     = QualityFlag.VERIFIED
    note:          Optional[str]   = None


# ─── Indicator Catalogue Entry ────────────────────────────────────────────────

class IndicatorValue(BaseModel):
    indicator_id:  str
    name:          str
    value:         float
    unit:          str
    source_type:   SourceType
    source_ref:    str
    quality_flag:  QualityFlag = QualityFlag.VERIFIED
    year:          Optional[int] = None
    note:          Optional[str] = None


# ─── IA Blueprint ─────────────────────────────────────────────────────────────

class IAObjective(BaseModel):
    id:          str
    level:       str                           # "general" or "specific"
    description: str
    indicators:  List[str] = Field(default_factory=list)


class PolicyOption(BaseModel):
    id:          str
    name:        str
    description: str
    status:      OptionStatus = OptionStatus.ALTERNATIVE


class IABlueprint(BaseModel):
    legislation_name: str                      # e.g. "EU Quantum Act"
    problem_statement: str
    baseline_description: str
    objectives: List[IAObjective] = Field(default_factory=list)
    policy_options: List[PolicyOption] = Field(default_factory=list)
    monitoring_indicators: List[str] = Field(default_factory=list)


# ─── Scoring ──────────────────────────────────────────────────────────────────

class CriteriaScore(BaseModel):
    criterion:    str
    score:        float                        # anchored scale: -2 to +2
    rationale:    str
    evidence_ids: List[str] = Field(default_factory=list)   # ref indicator_ids
    assumption:   Optional[str] = None        # required if no evidence


class OptionScore(BaseModel):
    option_id:       str
    option_name:     str
    criteria_scores: List[CriteriaScore]
    weighted_total:  float
    rank:            int
    status:          OptionStatus


# ─── Sensitivity Analysis ─────────────────────────────────────────────────────

class SensitivityResult(BaseModel):
    scenario_label:   str                      # e.g. "economic_priority"
    weights_used:     Dict[str, float]
    option_rankings:  List[Dict[str, Any]]     # [{option_id, rank, score}]
    ranking_stable:   bool                     # True if top option unchanged
    top_option_id:    str


# ─── Drivers ──────────────────────────────────────────────────────────────────

class Driver(BaseModel):
    criterion:   str
    direction:   str                           # "positive" | "negative" | "neutral"
    contribution: float                        # absolute weighted contribution
    source_ref:  Optional[str] = None


# ─── Request Models ───────────────────────────────────────────────────────────

class AssessRequest(BaseModel):
    run_id:      str
    scenario_id: str
    blueprint:   IABlueprint
    indicators:  List[IndicatorValue] = Field(default_factory=list)
    constraints: Dict[str, Any]       = Field(default_factory=dict)


class SensitivityRequest(BaseModel):
    run_id:        str
    scenario_id:   str
    option_scores: List[OptionScore]
    weight_grid:   Optional[List[Dict[str, float]]] = None  # custom weight scenarios
    constraints:   Dict[str, Any] = Field(default_factory=dict)


class BriefRequest(BaseModel):
    run_id:        str
    scenario_id:   str
    option_scores: List[OptionScore]
    drivers:       List[Driver]       = Field(default_factory=list)
    assumptions:   List[str]          = Field(default_factory=list)
    evidence:      List[EvidenceItem] = Field(default_factory=list)
    objective:     Optional[str]      = None


# ─── Response Models ──────────────────────────────────────────────────────────

class AssessResponse(BaseModel):
    run_id:        str
    scenario_id:   str
    option_scores: List[OptionScore]
    drivers:       List[Driver]
    assumptions:   List[str]
    evidence:      List[EvidenceItem]


class SensitivityResponse(BaseModel):
    run_id:      str
    scenario_id: str
    results:     List[SensitivityResult]
    stable:      bool                          # True if top option consistent across all scenarios
    summary:     str


class BriefResponse(BaseModel):
    run_id:        str
    scenario_id:   str
    brief_markdown: str
    option_scores: List[OptionScore]
    drivers:       List[Driver]
    assumptions:   List[str]
    evidence:      List[EvidenceItem]
