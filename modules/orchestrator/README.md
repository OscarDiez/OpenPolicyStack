# Orchestrator
- **Owner:** Adrián Con García  
- **Module Path:** `modules/orchestrator`  
- **Goal:** Provide a central orchestrator service that calls OpenPolicyStack microservices and produces reproducible “runs” with basic logs/traces.

---

## 1) Scope (What This Module Does)

The **Orchestrator** coordinates end-to-end workflows across OpenPolicyStack modules.

It is responsible for:
- Receiving a **Scenario Request** (what to run + which modules + parameters).
- Creating a **Reproducible Run Record** (e.g: Inputs, timestamps, versions, outputs).
- Executing a workflow via a single entrypoint: **`/plan_and_execute`**.
- Calling module microservices (HTTP) and collecting their outputs/artifacts.
- Writing basic **Logs** and optional **Trace Data** for transparency/debugging.
- Returning a structured response that can be plugged into a demo portal/workflow.

**Non-Goals (MVP / Scope NOW)**
- Not an API Gateway or Portal (handled by the **Integration UI / API Gateway** effort).
- Not advanced **Monitoring & Telemetry** (phase 2).
- Not **Privacy & PII Redaction** (phase 2 / optional later).
- Not complex workflow engines (queues, distributed scheduling, etc.); keep sequential execution.
- Not implementing the analytics logic of other modules.
Out of scope for NOW; may be integrated later as separate services.

---

## 2) Definitions (Plain Language)
- **Run:** One execution of the system for a given scenario + parameters.
- **Run ID:** Unique identifier for a run (used to find outputs/logs later).
- **Plan:** A list of steps the orchestrator will execute (e.g: call policy simulator → call strategy agent).
- **Artifact:** A saved output file (plot image, brief markdown, JSON results, etc.).
- **Trace/Logs:** A record of what happened during a run (steps, timing, success/failure).

---

## 3) Interface (What This Module Exposes)

### MVP API (Proposed Interface)
The orchestrator exposes a small HTTP API.

#### `POST /plan_and_execute`
Create a run, generate a simple plan (sequence of module calls), execute it, and persist inputs/outputs/logs under a `run_id`.

**Request (example):** This request starts a new orchestrated run for a demo policy scenario. It specifies which modules to execute and provides the scenario inputs (e.g: country, time horizon, and policy parameters like a VAT rate change).
```json
{
  "scenario_id": "demo-scenario-001",
  "modules": ["policy-simulator", "strategy-agent"],
  "inputs": {
    "country": "DR",
    "time_horizon_years": 5,
    "policy_parameters": {
      "vat_rate": 0.18
    }
  },
  "run_options": {
    "seed": 42,
    "save_artifacts": true
  }
}
```


**Response (example):** The orchestrator returns a unique `run_id`, the execution plan it followed, and pointers to the saved outputs (KPIs/plots/brief) plus where logs and artifacts were stored for reproducibility.

```json
{
  "run_id": "run_2026-01-09T12-34-56Z_ab12cd",
  "status": "completed",
  "plan": [
    {"step": 1, "module": "policy-simulator", "action": "execute"},
    {"step": 2, "module": "strategy-agent", "action": "execute"}
  ],
  "results": {
    "policy-simulator": {"kpis": {"gdp_growth": 0.02}, "artifacts": ["kpis.json", "plot.png"]},
    "strategy-agent": {"brief": "brief.md", "artifacts": ["brief.md"]}
  },
  "artifacts_path": "runs/run_2026-01-09T12-34-56Z_ab12cd/",
  "logs_path": "runs/run_2026-01-09T12-34-56Z_ab12cd/logs.jsonl"
}
```
`GET /runs/{run_id}`

Returns the saved run metadata (inputs, plan, results pointers).

`GET /health`

Simple healthcheck endpoint.

## 4) Inputs → Outputs (MVP)

### Inputs
- `scenario_id` (string)
- `modules` (list of module names to call)
- `inputs` (JSON payload passed to modules)
- optional `run_options` (seed, toggles for saving artifacts, etc.)

### Outputs 
- `run_id`
- `plan` (what steps were executed)
- per-module results (JSON + artifact references)
- paths/pointers to stored logs and artifacts for reproducibility

## 5) Run Storage (Reproducibility)

Every call to `POST /plan_and_execute` creates a **run**.  
A run is a single execution of a scenario with specific modules + inputs.

To make runs **reproducible and traceable**, the orchestrator saves:
- The original request (inputs, chosen modules, options like seed),
- What steps were executed (the “plan”),
- Each module’s returned results,
- Basic logs of what happened.

This is stored under a unique `run_id` in a folder like:


<pre><code>runs/&lt;run_id&gt;/
  run.json        # input request + derived plan + timestamps
  results.json    # merged results (pointers to artifacts)
  logs.jsonl      # structured logs (one JSON per line)
  artifacts/
    &lt;module-name&gt;/
      ...         # plots, JSONs, briefs, etc.</code></pre>

The API response includes the `run_id` and (optionally) paths/pointers to the saved logs and artifacts.

## 6) How Modules Are Called (Assumptions for Integration)

For MVP integration, the orchestrator assumes modules are reachable over **HTTP** (Docker-first) and expose a minimal interface so they can be called consistently.

The proposed minimal module contract is documented in the repo Issue:
**“MVP module interface contract (proposed)”** (see GitHub Issues).

In short, the orchestrator expects:
- `GET /health` for basic service readiness checks
- One primary execution endpoint (preferred: `POST /execute`, or a module-specific endpoint such as `/score`, `/risk`, `/run_scenario`)
- JSON-in / JSON-out
- A consistent response “envelope” including:
  - `status`, `module`, `outputs`
  - Optional `artifacts` and `evidence` fields

> Note: Endpoint naming and exact payload fields may be refined during integration month. The orchestrator will prioritize compatibility with the agreed contract in the Issue and adapt via lightweight adapters if needed.

## 7) How To Run (Local / Docker)

> Status: This module is currently in setup phase. The commands below describe the intended MVP run method and will be made runnable as the skeleton is implemented.

### Docker (recommended for reproducibility)
Planned workflow:
```bash
# from modules/orchestrator
docker build -t openpolicystack-orchestrator:dev .
docker run --rm -p 8000:8000 \
  -v $(pwd)/runs:/app/runs \
  openpolicystack-orchestrator:dev
```

### Local (for development)
Planned workflow:
```bash
# from modules/orchestrator
pip install -r requirements.txt
# example server command (framework to be confirmed)
python -m src.main
```
## 8) Quickstart Demo (Planned)

> Status: This is the intended MVP smoke test once the orchestrator skeleton is implemented.

1) Start the orchestrator (see Section 7)  
2) Start at least one module service (or a stub) reachable by the orchestrator  
3) Trigger a run:

```bash
curl -X POST http://localhost:8000/plan_and_execute \
  -H "Content-Type: application/json" \
  -d @examples/plan_and_execute.request.json
```
Expected behavior (once implemented):
- Returns a JSON response containing a `run_id`
- Creates `runs/<run_id>/` with `run.json`, `results.json`, `logs.jsonl`, and `artifacts/`

