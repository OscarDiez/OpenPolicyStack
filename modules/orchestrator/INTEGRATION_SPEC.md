# OpenPolicyStack Integration Specification

**File:** `INTEGRATION_SPEC.md`

**Version:** 1.0

**Status:** Frozen Integration Contract

---

# 1. Purpose

This document defines the **integration contract governing all modules within the OpenPolicyStack environment**.

The purpose of this specification is to ensure that independently developed analytical modules can be orchestrated in a **deterministic, reproducible, and traceable execution environment**.

The integration layer standardizes conventions for:

- service naming
- API interfaces
- port allocation
- environment configuration
- networking
- logging
- artifact management

By enforcing these conventions, the OpenPolicyStack orchestrator can coordinate heterogeneous modules while preserving **run-level reproducibility, structured provenance, and auditability**.

This document represents the **authoritative integration contract** against which all future integration decisions are evaluated.

---

# 2. Architectural Context

OpenPolicyStack implements a **centralized orchestration architecture** in which multiple analytical modules are coordinated by a single orchestrator service.

Each module:

- operates as an **independent microservice**
- exposes a **lightweight REST interface**
- runs inside a **Docker container**
- executes deterministically within a predefined workflow template.

The orchestrator performs:

- module sequencing
- metadata capture
- artifact tracking
- module version recording
- execution provenance reconstruction.

The MVP system integrates six modules:

- Data Layer
- DR Anticorruption
- Monitor
- Policy Simulator
- Strategy Agent
- Supply Chain Risk

Modules are treated as **black-box services**, allowing their internal analytical logic to remain independent while the orchestration layer enforces system-level governance guarantees.

---

# 3. Core Design Principles

All integration decisions must preserve the following architectural principles.

## Deterministic Execution

Workflows follow predefined templates specifying module order and execution structure.

## Reproducibility

Identical inputs and module versions must produce structurally identical execution runs.

## Traceability

All module invocations, inputs, outputs, and artifacts must be recorded in structured metadata.

## Modular Interoperability

Modules interact exclusively through standardized HTTP interfaces.

## Governance by Design

Accountability and auditability are enforced at the orchestration layer rather than within module internals.

---

# 4. Repository Structure

All modules must follow the repository layout:

```
/opt/openpolicystack
│
├── orchestrator
│
├── modules
│   ├── data-layer
│   ├── dr-anticorruption
│   ├── monitor
│   ├── policy-simulator
│   ├── strategy-agent
│   └── supplychain-risk
│
├── infrastructure
│
├── artifacts
│
└── compose.yaml
```

Each module must reside under:

```
modules/<module-name>
```

Module names must be unique within the system.

---

# 5. Module Naming Convention

All services use **lowercase kebab-case identifiers**.

Examples:

```
data-layer
policy-simulator
strategy-agent
monitor
```

The module identifier must be used consistently across:

- repository folder name
- Docker image name
- Docker Compose service name
- network hostname
- artifact directory
- log fields
- module metadata

Example:

```
modules/policy-simulator
service: policy-simulator
image: openpolicystack/policy-simulator
hostname: policy-simulator
```

---

# 6. Containerization Requirements

Every module must provide:

```
Dockerfile
.env.example
module.yaml
```

Modules must run as **standalone containers**.

The container must start an HTTP service exposing the module API.

---

# 7. Port Allocation Scheme

### Internal container port

All module APIs must listen on:

```
8080
```

Optional auxiliary ports:

```
9090   metrics
8081   admin/debug
```

---

### Service communication

Services communicate via Docker DNS using service names:

```
http://policy-simulator:8080
http://data-layer:8080
```

Modules must **not rely on static IP addresses**.

---

### Host port exposure

Host ports are used only for development or gateway access.

Reserved host port ranges:

| Module | Port Range |
| --- | --- |
| orchestrator | 8100–8109 |
| data-layer | 8200–8209 |
| strategy-agent | 8300–8309 |
| dr-anticorruption | 8400–8409 |
| supplychain-risk | 8500–8509 |
| policy-simulator | 8600–8609 |
| monitor | 8700–8709 |

---

# 8. API Integration Contract

Modules must expose a **REST API interface**.

### Required endpoints

```
GET  /health
GET  /metadata
POST /execute
```

These endpoints form the minimal integration surface.

---

# 8.1 Health Endpoint

```
GET /health
```

Response:

```json
{
  "status": "ok",
  "module_name": "policy-simulator",
  "version": "0.1.0"
}
```

Used for orchestrator readiness checks.

---

# 8.2 Metadata Endpoint

```
GET /metadata
```

Example response:

```json
{
  "module_name": "policy-simulator",
  "version": "0.1.0",
  "api_version": "1.0",
  "owner": "module_author",
  "supported_tasks": [
    "simulate_policy"
  ]
}
```

The orchestrator records module version metadata for reproducibility tracking.

---

# 8.3 Execution Endpoint

```
POST /execute
```

Request payload:

```json
{
  "run_id": "uuid",
  "parameters": {},
  "inputs": [],
  "metadata": {}
}
```

Response payload must include:

```json
{
  "module_name": "policy-simulator",
  "version": "0.1.0",
  "status": "success",
  "output": {},
  "artifacts": []
}
```

Required response fields:

- module_name
- version
- status
- output
- artifacts

This structure allows the orchestrator to capture module-level provenance.

---

# 9. Environment Variable Conventions

Global environment variables use the prefix:

```
OPS_
```

Required base variables:

```
OPS_ENV
OPS_MODULE_NAME
OPS_PORT
OPS_LOG_LEVEL
OPS_ARTIFACT_ROOT
OPS_ORCHESTRATOR_URL
```

Example:

```
OPS_MODULE_NAME=policy-simulator
OPS_PORT=8080
OPS_ARTIFACT_ROOT=/var/openpolicystack/artifacts
```

---

### Module-specific variables

Module-specific variables must use a namespace:

```
MODULEPREFIX__
```

Example:

```
POLICY_SIMULATOR__MODEL_PATH
DATA_LAYER__DB_PATH
```

---

# 10. Networking Model

The deployment uses two Docker networks.

### Internal network

```
ops-core
```

All modules and the orchestrator join this network.

---

### Edge network

```
ops-edge
```

Used only for services exposed externally.

Service discovery uses DNS names:

```
http://module-name:8080
```

---

# 11. Logging Convention

All services log to:

```
stdout
stderr
```

Logs must follow **structured JSON format**.

Example:

```json
{
  "timestamp": "2026-03-12T11:20:31Z",
  "level": "INFO",
  "service": "policy-simulator",
  "run_id": "uuid",
  "event": "simulation_started",
  "message": "Policy simulation initiated"
}
```

Required fields:

- timestamp
- level
- service
- run_id
- event
- message

---

# 12. Artifact Management

Artifacts are stored in a shared volume mounted at:

```
/var/openpolicystack/artifacts
```

Run directory structure:

```
artifacts/
└── runs/
    └── <run_id>/
        └── <module-name>/
            ├── inputs/
            ├── outputs/
            └── meta/
```

Example:

```
artifacts/runs/abc123/policy-simulator/outputs/report.json
```

Large outputs must be stored as artifacts with references returned to the orchestrator.

The orchestrator records:

- artifact path
- artifact hash
- producing module
- associated run

This enables integrity verification and reproducibility validation.

---

# 13. Module Manifest

Each module must provide:

```
modules/<module>/module.yaml
```

Example:

```yaml
module_name: policy-simulator
version: 0.1.0

interface:
  type: http
  port: 8080
  execute: /execute
  health: /health
```

This allows automated module discovery and integration validation.

---

# 14. Minimum Compliance Checklist

A module is considered **integration-ready** only if it satisfies:

- containerized via Docker
- resides under `modules/<module-name>`
- exposes `/health`
- exposes `/metadata`
- exposes `/execute`
- accepts `run_id`
- logs structured JSON
- returns module version
- stores outputs as artifacts
- includes `module.yaml`
- includes `.env.example`

---

# 15. Scope Boundaries

The integration specification intentionally excludes:

- distributed orchestration platforms
- ontology harmonization across modules
- semantic schema alignment
- adaptive runtime planning
- parallel execution scheduling

These elements are outside the MVP scope and may be explored in future research iterations.

---

# 16. Governance Role of the Orchestrator

Modules remain responsible for **analytical correctness**.

The orchestrator is responsible for:

- workflow coordination
- version capture
- metadata persistence
- artifact lineage tracking
- reproducibility guarantees
- execution trace reconstruction.

This separation ensures governance guarantees are **architectural system properties rather than implementation details of individual modules**.

---

# 17. Change Management

This specification represents the **baseline integration contract**.

Changes must follow:

```
proposal → review → version update
```

Breaking interface changes require:

```
spec version increment
```

---

# 18. Relationship to Deployment Architecture

This specification is the **foundation for the deployment architecture**.

The Docker Compose infrastructure will implement the conventions defined here, including:

- service names
- network topology
- environment variable schema
- artifact mounts
- inter-service communication

---

# 19. Next Integration Step

After freezing this specification, the integration process proceeds with:

1. Generate the **Compose deployment skeleton**
2. Integrate the **first pilot module**
3. Validate compliance
4. Refine integration procedures
5. Expand to the full module ecosystem