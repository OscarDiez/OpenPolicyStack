"""
evidence.py — Build the evidence payload for an AssessResponse.

Collects all indicator_ids referenced in criteria scores and maps
them back to full EvidenceItem objects from the indicator list.
"""

from typing import List
from app.schemas import OptionScore, IndicatorValue, EvidenceItem, SourceType, QualityFlag


def build_evidence(
    option_scores: List[OptionScore],
    indicators: List[IndicatorValue],
) -> List[EvidenceItem]:
    """
    Return deduplicated EvidenceItems for all indicators referenced
    across any criteria score in any option.
    """
    ind_map = {i.indicator_id: i for i in indicators}

    referenced_ids: set[str] = set()
    for os in option_scores:
        for cs in os.criteria_scores:
            for eid in cs.evidence_ids:
                referenced_ids.add(eid)

    evidence: List[EvidenceItem] = []
    for ind_id in sorted(referenced_ids):
        ind = ind_map.get(ind_id)
        if ind:
            evidence.append(EvidenceItem(
                indicator_id=ind.indicator_id,
                source_type=ind.source_type,
                source_ref=ind.source_ref,
                field_path=f"{ind.indicator_id}.{ind.year or 'latest'}",
                value=ind.value,
                unit=ind.unit,
                quality_flag=ind.quality_flag,
                note=ind.note,
            ))
        else:
            # Referenced but not in catalogue — flag as assumption
            evidence.append(EvidenceItem(
                indicator_id=ind_id,
                source_type=SourceType.MANUAL,
                source_ref="unknown",
                field_path=ind_id,
                quality_flag=QualityFlag.ASSUMPTION,
                note=f"Indicator '{ind_id}' referenced in scoring but not found in catalogue.",
            ))

    return evidence


def collect_assumptions(option_scores: List[OptionScore]) -> List[str]:
    """
    Collect all explicit assumption strings from criteria scores
    where no evidence was available.
    """
    assumptions = []
    seen = set()
    for os in option_scores:
        for cs in os.criteria_scores:
            if cs.assumption and cs.assumption not in seen:
                assumptions.append(
                    f"[{os.option_name} / {cs.criterion}] {cs.assumption}"
                )
                seen.add(cs.assumption)
    return assumptions