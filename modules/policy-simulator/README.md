# Policy Simulator / Fiscal Evaluation
Owner: Andrés Gerli Milian
Goal: run_scenario → KPIs/plots/brief + 2–3 demo scenarios.

This module is a **policy scenario simulator microservice** focused on business taxation and its effects on **firm dynamics** and **labour outcomes**. 

---

## 1) Overview & scope

### What this module does (MVP)
The MVP provides a Dockerised FastAPI service that:

- Accepts a **scenario JSON** (country, sector, time window, tax parameters, run params).
- Returns:
  - a **KPI table** (birth/death/net formation, employment index, salary index),
  - **artifact paths** (at least one PNG plot, plus a JSON/Markdown brief),
  - a structured **policy brief** (JSON object).

**Important:** The MVP uses **deterministic dummy logic** (not the final ABM). The goal is to lock the **interface contract** and enable early integration into OpenPolicyStack.

### Out of scope (later; not implemented in MVP)
- Real ETL from Eurostat / DG TAXUD / OECD / ECB.
- The full ABM of firm entry/exit and hiring.
- DiD/event-study validation around real reforms.

(These items are intentionally excluded from this MVP to keep it integration-ready and realistic.)

---

## 2) Inputs

### 2.1 Scenario parameters (required)
`POST /run_scenario` expects a JSON request body:

| Field | Type | Required | Default | Notes |
|---|---:|---:|---:|---|
| `country` | string | yes | — | ISO 3166-1 alpha-2 (e.g., `"FR"`, `"SE"`, `"DE"`, `"NL"`). MVP accepts any 2-letter string. |
| `sector` | string | yes | — | MVP: `"manufacturing"` or `"market_services"`. |
| `start_year` | int | yes | — | Analysis window start year (metadata + future ETL slice). |
| `end_year` | int | yes | — | Analysis window end year (metadata + future ETL slice). |
| `employer_payroll_tax_rate` | float | yes | — | Employer social contributions as a share of gross wage (0–1). |
| `employee_payroll_tax_rate` | float | yes | — | Employee social contributions as a share of gross wage (0–1). |
| `cit_rate` | float | yes | — | Corporate income tax rate (0–1). |
| `seed` | int | no | 42 | Ensures deterministic simulation and artifacts. |
| `timesteps` | int | no | 12 | Number of simulated periods (MVP: for plotting only). |

### 2.2 Optional calibration reference (MVP accepts; does not use yet)
The request may include an optional `calibration` object to align with future integration:

```json
"calibration": {
  "baseline_year": 2010,
  "tax_source": "dummy",
  "kpi_source": "dummy"
}
