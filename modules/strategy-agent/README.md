# Strategy & Feedback Agent — IA Edition
**Owner:** Antonio Soto Grande
**Version:** 0.2.0
**Part of:** OpenPolicyStack

---

## Overview

The Strategy & Feedback Agent (SFA) is an AI-based microservice that automates EU Impact Assessment (IA) artefacts aligned with the European Commission's Better Regulation framework. Given a structured IA blueprint and live open-data indicators, it scores policy options across six IA criteria, runs weight sensitivity analysis, and generates evidence-linked stakeholder briefs.

The system is piloted on the **EU Quantum Act** Impact Assessment but is designed to be reusable across any EU technical legislation (Chips Act, Cloud infrastructure directive, etc.) by swapping the indicator catalogue.

---

## Architecture

```
AssessRequest
  └── IABlueprint (legislation + options + objectives)
  └── indicators[]  ← Eurostat + CORDIS live fetch (or explicit values)
        │
        ▼
  scoring.py       MCDA weighted additive scoring (6 IA criteria)
  explain.py       Driver attribution (top-3 contributing criteria)
  evidence.py      Evidence payload + assumption collection
        │
        ▼
  AssessResponse   Ranked OptionScore[] + drivers + evidence

        │
        ▼
  sensitivity.py   Weight variation across 4 stakeholder scenarios
        │
        ▼
  SensitivityResponse  Per-scenario rankings + stability flag

        │
        ▼
  main.py /brief   Markdown brief from structured outputs only
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
| POST | `/brief` | Generate evidence-linked markdown brief |

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

# Run
docker run --rm -p 8010:8010 ops-strategy-agent

# Health check
curl http://localhost:8010/health

# Fetch live indicators
curl http://localhost:8010/indicators

# Run baseline assessment (uses live data)
curl -X POST http://localhost:8010/assess \
  -H "Content-Type: application/json" \
  -d @modules/strategy-agent/examples/assess_request_baseline.json
```

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
│   ├── main.py                 # FastAPI app — 4 endpoints
│   ├── schemas.py              # Pydantic models (all I/O types)
│   ├── config.py               # IA criteria weights + scoring anchors
│   ├── indicator_catalogue.py  # Live Eurostat + CORDIS fetchers
│   ├── scoring.py              # MCDA scoring engine
│   ├── sensitivity.py          # Weight sensitivity analysis
│   ├── explain.py              # Driver attribution
│   ├── evidence.py             # Evidence payload builder
│   └── utils.py                # Shared helpers
├── examples/
│   ├── assess_request_baseline.json
│   ├── assess_response_baseline.json
│   ├── assess_request_adverse.json
│   ├── assess_response_adverse.json
│   ├── assess_request_recovery.json
│   └── assess_response_recovery.json
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