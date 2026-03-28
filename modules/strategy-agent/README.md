# Strategy & Feedback Agent — IA Edition
**Owner:** Antonio Soto Grande
**Version:** 0.3.0
**Part of:** OpenPolicyStack

---

## Overview

The Strategy & Feedback Agent (SFA) is an AI-based microservice that automates EU Impact Assessment (IA) artefacts aligned with the European Commission's Better Regulation framework. Given a structured IA blueprint and live open-data indicators, it scores policy options across six IA criteria, runs weight sensitivity analysis, generates evidence-linked stakeholder briefs, produces LLM-enhanced narratives, and exports professional PDF reports.

The system is piloted on the **EU Quantum Act** Impact Assessment but is designed to be reusable across any EU technical legislation (Chips Act, Cloud infrastructure directive, etc.) by swapping the indicator catalogue. It is designed to be rerun each time new data is available, producing consistent, comparable, traceable outputs across time.

---

## Architecture

```
AssessRequest
  └── IABlueprint (legislation + options + objectives)
  └── indicators[]  ← Eurostat + CORDIS live fetch (or explicit values)
        │
        ▼
  scoring.py        MCDA weighted additive scoring (6 IA criteria)
  explain.py        Driver attribution (top-3 contributing criteria)
  evidence.py       Evidence payload + assumption collection
        │
        ▼
  AssessResponse    Ranked OptionScore[] + drivers + evidence

        │
        ▼
  sensitivity.py    Weight variation across 4 stakeholder scenarios
        │
        ▼
  SensitivityResponse   Per-scenario rankings + stability flag

        │
        ├──▶ /brief      Deterministic markdown brief (always works)
        ├──▶ /brief/llm  LLM-enhanced brief via Anthropic API
        └──▶ /brief/pdf  Professional 3-page PDF export
```

---

## API

**Base URL:** `http://localhost:8010`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/indicators` | Fetch live Eurostat + CORDIS indicators |
| POST | `/assess` | Score policy options (MCDA) |
| POST | `/sensitivity` | Weight sensitivity analysis |
| POST | `/brief` | Deterministic evidence-linked markdown brief |
| POST | `/brief/llm` | LLM-enhanced brief (requires `ANTHROPIC_API_KEY`) |
| POST | `/brief/pdf` | Professional 3-page PDF export |

---

## IA Criteria and Scoring Scale

Each policy option is scored on six criteria derived from the EU Better Regulation framework:

| Criterion | Weight (default) |
|-----------|-----------------|
| Economic impact | 0.25 |
| Competitiveness | 0.25 |
| Social impact | 0.15 |
| Feasibility | 0.15 |
| Environmental impact | 0.10 |
| Coherence | 0.10 |

**Scale:** `-2` (strongly negative) to `+2` (strongly positive).
Every score is linked to an evidence item or carries an explicit assumption tag.

---

## Data Sources

| Indicator | Source | Dataset |
|-----------|--------|---------|
| EU GERD as % of GDP | Eurostat | `rd_e_gerdtot` |
| R&D personnel as % active pop | Eurostat | `rd_p_persocc` |
| High-tech employment % | Eurostat | `htec_emp_nat2` |
| Quantum project count | CORDIS | public search |
| Quantum funding (M EUR) | CORDIS | public search |

All sources are free and require no authentication.
On fetch failure, the system falls back to proxy values with a `quality_flag: proxy` tag.

---

## Run (Docker-first)

```bash
# Build
docker build -t ops-strategy-agent modules/strategy-agent

# Run (with LLM support)
docker run --rm -p 8010:8010 \
  -e ANTHROPIC_API_KEY="your-key-here" \
  ops-strategy-agent

# Run (without LLM — /brief/llm falls back to deterministic)
docker run --rm -p 8010:8010 ops-strategy-agent

# Health check
curl http://localhost:8010/health

# Fetch live indicators
curl http://localhost:8010/indicators

# Run baseline assessment
curl -X POST http://localhost:8010/assess \
  -H "Content-Type: application/json" \
  -d @modules/strategy-agent/examples/assess_request_baseline.json

# Generate PDF brief
curl -X POST http://localhost:8010/brief/pdf \
  -H "Content-Type: application/json" \
  -d @modules/strategy-agent/examples/assess_response_baseline.json \
  --output modules/strategy-agent/IA_Brief_baseline.pdf
```

---

## Streamlit UI

A Streamlit visualization app is included for interactive demonstration and exploration.

**Requirements:** Python 3.10+ with streamlit and requests installed.

```bash
pip install streamlit requests pandas
```

**Run (Docker service must be running first):**

```bash
python -m streamlit run modules/strategy-agent/streamlit_app.py
```

The app opens automatically in your browser and provides:

| Tab | Description |
|-----|-------------|
| 📊 MCDA Scoring | Full criteria scoring table, key drivers, per-option rationale |
| 🔄 Sensitivity Analysis | Weight scenario matrix showing ranking stability |
| 📝 Brief Comparison | Side-by-side deterministic vs LLM-enhanced brief |
| 📋 Evidence & Provenance | Full indicator table with quality flags and assumptions |

The sidebar allows scenario selection (baseline / adverse / recovery) and PDF download.

---

## PDF Brief

The `/brief/pdf` endpoint generates a professional 3-page PDF:

- **Page 1** — Executive summary (LLM narrative + option ranking table)
- **Page 2** — Full MCDA scoring table with rationales per option
- **Page 3** — Evidence payload, indicator notes, and explicit assumptions

The PDF uses EU Commission colour styling and includes a full methodology note and traceability footer on every page.

---

## LLM Layer

The `/brief/llm` endpoint calls the Anthropic API (`claude-sonnet-4-20250514`) to generate a readable narrative brief constrained strictly to structured scoring outputs. The system prompt enforces:

- No new facts beyond what is in the structured payload
- No changes to rankings, scores, or option names
- Explicit reflection of assumption and proxy flags
- Output under 400 words in plain accessible language

If the API key is missing or the call fails, the endpoint falls back gracefully to the deterministic `/brief` output. The service never breaks the orchestrator.

---

## Examples

Golden request/response pairs are in `examples/` and serve as both documentation and integration tests:

| File | Description |
|------|-------------|
| `assess_request_baseline.json` | Baseline scenario — live Eurostat/CORDIS fetch |
| `assess_response_baseline.json` | Expected response, opt-2 preferred (score: +1.425) |
| `assess_request_adverse.json` | Adverse shock — declining GERD + reduced funding |
| `assess_response_adverse.json` | Expected response, opt-3 preferred (score: +1.275) |
| `assess_request_recovery.json` | Recovery — rising GERD + oversubscribed quantum calls |
| `assess_response_recovery.json` | Expected response, opt-2 preferred (score: +1.625) |

---

## Repository Structure

```
modules/strategy-agent/
├── app/
│   ├── main.py                 # FastAPI app — 6 endpoints
│   ├── schemas.py              # Pydantic models (all I/O types)
│   ├── config.py               # IA criteria weights + scoring anchors
│   ├── indicator_catalogue.py  # Live Eurostat + CORDIS fetchers
│   ├── scoring.py              # MCDA scoring engine
│   ├── sensitivity.py          # Weight sensitivity analysis
│   ├── explain.py              # Driver attribution
│   ├── evidence.py             # Evidence payload builder
│   ├── llm_brief.py            # Constrained LLM brief via Anthropic API
│   ├── pdf_brief.py            # Professional PDF generator (reportlab)
│   └── utils.py                # Shared helpers
├── examples/
│   ├── assess_request_baseline.json
│   ├── assess_response_baseline.json
│   ├── assess_request_adverse.json
│   ├── assess_response_adverse.json
│   ├── assess_request_recovery.json
│   └── assess_response_baseline.json
├── streamlit_app.py            # Interactive Streamlit UI
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Evidence and Provenance

Every output includes a structured evidence payload. Each item records:
- `indicator_id` — unique indicator reference
- `source_type` — `eurostat` | `cordis` | `derived` | `manual`
- `source_ref` — dataset code or endpoint (e.g. `eurostat:rd_e_gerdtot`)
- `field_path` — specific field used (e.g. `gerd_pct_gdp.latest`)
- `quality_flag` — `verified` | `proxy` | `assumption` | `stale`

The `no evidence → no claim` rule is enforced: any criteria score without a referenced indicator must carry an explicit `assumption` string.

---

## Sensitivity Analysis

Four weight scenarios test ranking robustness:

| Scenario | Focus |
|----------|-------|
| Economic priority | Elevated weights on economic + competitiveness criteria |
| Social/environmental priority | Elevated weights on social + environmental criteria |
| Feasibility priority | Elevated weight on feasibility (risk-averse perspective) |
| Equal weights | All criteria weighted equally (baseline sensitivity check) |

Results show whether the preferred option is stable across stakeholder value assumptions.