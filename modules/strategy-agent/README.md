# Strategy & Feedback Agent
Owner: Antonio Soto Grande
Goal: /recommend, /counterfactual, /brief + templates.

@'
# Strategy & Feedback Agent (SFA)

The Strategy & Feedback Agent is a microservice inside OpenPolicyStack. It consumes structured outputs from upstream modules
(e.g., simulator KPIs, risk scores) and returns decision-facing outputs:
- recommendations (structured),
- counterfactual-style feedback (feasible “what-if” changes),
- and a short brief with evidence pointers.

This is an MVP skeleton: it returns deterministic placeholder structures so the orchestrator can integrate and test the interface.

## API (MVP)
Base URL: `http://localhost:8010`

Endpoints:
- `GET /health`
- `POST /recommend`
- `POST /counterfactual`
- `POST /brief`

All responses return structured fields:
- `recommendations`
- `drivers`
- `assumptions`
- `evidence[]`

`/counterfactual` additionally returns `counterfactuals[]`.
`/brief` additionally returns `brief_markdown`.

## Run (Docker-first)
From the repo root:

```bash
docker build -t ops-strategy-agent modules/strategy-agent
docker run --rm -p 8010:8010 ops-strategy-agent

