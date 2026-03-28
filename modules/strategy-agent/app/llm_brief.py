"""
llm_brief.py — LLM-enhanced brief generator using the Anthropic API.

DESIGN CONSTRAINTS (enforced via system prompt):
  - The LLM receives ONLY structured scoring outputs — no external knowledge
  - It is explicitly instructed not to introduce new facts or claims
  - Every claim must be traceable to a field in the structured payload
  - If the API call fails, main.py falls back to the deterministic /brief output

The LLM's role is purely presentational: it rewrites the structured
brief into clearer, more readable prose for non-technical stakeholders.
It does not score, rank, or recommend — that is done by scoring.py.
"""

import os
import anthropic
from app.schemas import BriefRequest

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are a policy analyst assistant helping to write Impact Assessment briefs for the European Commission.

Your role is strictly presentational: you receive structured scoring data and rewrite it into clear, concise prose suitable for non-technical stakeholders such as senior policy officials and ministers.

ABSOLUTE RULES you must never break:
1. You may ONLY use information explicitly present in the structured data provided. Do not introduce any external facts, statistics, or claims.
2. Do not add any numbers, percentages, or figures that are not in the structured data.
3. Do not make recommendations beyond what the scoring data already states.
4. Do not change any rankings, scores, or option names.
5. If a field is marked as an assumption or proxy, reflect that uncertainty in your language.
6. Keep the brief under 400 words.
7. Use plain, accessible language — avoid jargon.
8. Always end with the evidence quality note from the structured data.

You are a presentation layer only. The analysis has already been done. Your job is clarity, not intelligence."""


def _build_user_prompt(req: BriefRequest) -> str:
    preferred = next(
        (os for os in req.option_scores if os.rank == 1),
        req.option_scores[0] if req.option_scores else None
    )

    preferred_name  = preferred.option_name if preferred else "N/A"
    preferred_score = f"{preferred.weighted_total:+.3f}" if preferred else "N/A"

    ranking = "\n".join(
        f"  Rank {os.rank}: {os.option_name} (weighted score: {os.weighted_total:+.3f}, status: {os.status})"
        for os in sorted(req.option_scores, key=lambda x: x.rank)
    )

    drivers = "\n".join(
        f"  - {d.criterion} ({d.direction}, contribution: {d.contribution:.3f})"
        + (f" — evidence: {d.source_ref}" if d.source_ref else "")
        for d in req.drivers
    )

    verified = sum(1 for e in req.evidence if e.quality_flag == "verified")
    total    = len(req.evidence)
    quality  = f"{verified}/{total} indicators verified from official sources."

    assumptions = "\n".join(f"  - {a}" for a in req.assumptions) \
        if req.assumptions else "  None recorded."

    return f"""Please write a clear, concise Impact Assessment brief using ONLY the structured data below.
Do not add any information not present here.

SCENARIO: {req.scenario_id}
RUN ID: {req.run_id}
OBJECTIVE: {req.objective or "EU Quantum Act option comparison"}

PREFERRED OPTION:
  {preferred_name} (score: {preferred_score})

FULL OPTION RANKING:
{ranking}

KEY DRIVERS OF PREFERRED OPTION:
{drivers}

EVIDENCE QUALITY:
  {quality}

EXPLICIT ASSUMPTIONS (where no indicator data was available):
{assumptions}

Write the brief now. Structure it with these sections:
1. Context and objective (1-2 sentences)
2. Preferred option and rationale (2-3 sentences, grounded in the drivers above)
3. Option comparison summary (2-3 sentences)
4. Evidence quality and assumptions (1-2 sentences)

End with: "This brief was generated from structured scoring outputs only. All claims are traceable to the evidence payload."
"""


def generate_llm_brief(req: BriefRequest) -> str:
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Cannot call LLM brief endpoint without an API key."
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    message = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _build_user_prompt(req)}
        ]
    )

    return message.content[0].text