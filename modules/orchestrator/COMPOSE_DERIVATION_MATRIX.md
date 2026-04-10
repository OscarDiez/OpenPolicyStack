# OpenPolicyStack Compose Derivation Matrix

**File:** `COMPOSE_DERIVATION_MATRIX.md`

**Version:** 1.0

**Status:** Compose Derivation Matrix - MVP Draft

---

| Service Name        | Build Context                 | Image Name                              | Internal Port | Host Port | Networks   | Volumes                                                                                      | Env Source                         | Healthcheck   | Role / Notes                                                                              |
| ------------------- | ----------------------------- | --------------------------------------- | ------------- | --------- | ---------- | -------------------------------------------------------------------------------------------- | ---------------------------------- | ------------- | ----------------------------------------------------------------------------------------- |
| `orchestrator`      | `./orchestrator`              | `openpolicystack/orchestrator:dev`      | `8080`        | `8100`    | `ops-core` | `ops-artifacts:/var/openpolicystack/artifacts`, `ops-metadata:/var/openpolicystack/metadata` | `./orchestrator/.env`              | `GET /health` | Central coordination service; invokes modules, records run metadata, persists SQLite data |
| `data-layer`        | `./modules/data-layer`        | `openpolicystack/data-layer:dev`        | `8080`        | —         | `ops-core` | `ops-artifacts:/var/openpolicystack/artifacts`                                               | `./modules/data-layer/.env`        | `GET /health` | Provides data access / preprocessing service to workflows                                 |
| `dr-anticorruption` | `./modules/dr-anticorruption` | `openpolicystack/dr-anticorruption:dev` | `8080`        | —         | `ops-core` | `ops-artifacts:/var/openpolicystack/artifacts`                                               | `./modules/dr-anticorruption/.env` | `GET /health` | Domain analysis module integrated as black-box HTTP service                               |
| `monitor`           | `./modules/monitor`           | `openpolicystack/monitor:dev`           | `8080`        | —         | `ops-core` | `ops-artifacts:/var/openpolicystack/artifacts`                                               | `./modules/monitor/.env`           | `GET /health` | Monitoring / tracking module integrated through standard module contract                  |
| `policy-simulator`  | `./modules/policy-simulator`  | `openpolicystack/policy-simulator:dev`  | `8080`        | —         | `ops-core` | `ops-artifacts:/var/openpolicystack/artifacts`                                               | `./modules/policy-simulator/.env`  | `GET /health` | Simulation module invoked by deterministic workflow templates                             |
| `strategy-agent`    | `./modules/strategy-agent`    | `openpolicystack/strategy-agent:dev`    | `8080`        | —         | `ops-core` | `ops-artifacts:/var/openpolicystack/artifacts`                                               | `./modules/strategy-agent/.env`    | `GET /health` | Strategy support module exposed as standardized REST service                              |
| `supplychain-risk`  | `./modules/supplychain-risk`  | `openpolicystack/supplychain-risk:dev`  | `8080`        | —         | `ops-core` | `ops-artifacts:/var/openpolicystack/artifacts`                                               | `./modules/supplychain-risk/.env`  | `GET /health` | Risk analysis module integrated as independent microservice                               |


