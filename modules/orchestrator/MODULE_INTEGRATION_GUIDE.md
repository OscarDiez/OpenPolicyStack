# OpenPolicyStack Module Integration Guide

**File:** `MODULE_INTEGRATION_GUIDE.md`

**Version:** 1.0

**Status:** Frozen Module Integration Guide

---

# 1. Overview

This guide explains how to prepare your module so that it can be integrated into the **OpenPolicyStack Orchestration System**.

All modules in OpenPolicyStack operate as **independent containerized** microservices coordinated by a **central** orchestrator.

Your module will:

- Run inside a Docker container.
- Expose a lightweight REST API.
- Receive execution requests from the orchestrator.
- Return structured outputs and artifact references.

You **do not** need to implement orchestration logic**.**

Your module must simply **conform** to the Integration Contract defined in this guide.

---

# 2. Validated Integration Baseline

A working integration baseline has been implemented and validated.

The module:
```
modules/integration-pilot
```
Serves as the reference implementation for:

- API contract
- Artifact handling
- Environment variables
- Docker container behavior
- Orchestrator interaction

All modules must align with the integration-pilot pattern.
If in doubt, follow that implementation exactly.

---

# 3. High-Level Integration Flow

When OpenPolicyStack runs a workflow, the following occurs:

1. The orchestrator generates a **run_id**.
2. The orchestrator calls your module via HTTP.
3. Your module performs its computation.
4. Your module returns structured JSON.
5. Artifacts are written to the shared volume.
6. The orchestrator records execution metadata.

Your module remains **analytically independent** but participates in the **shared execution environment**.

---

# 4. Module Repository Structure

Your module must follow this directory structure:

```
modules/<module-name>/
│
├── app/
│   └── main.py
│
├── Dockerfile
├── requirements.txt
├── module.yaml
├── .env.example
└── README.md
```

---

# 5. Naming Rules

Module names must follow **lowercase kebab-case**.

Correct:

```
policy-simulator
strategy-agent
supplychain-risk
data-layer
```

Incorrect:

```
PolicySimulator
policy_simulator
policySimulator
```

Your module name must match:

- Folder name
- Docker service name
- Container hostname
- Artifact directory name

---

# 6. Docker Container Requirement

Your module **must run inside a Docker container**.

Validated minimal Dockerfile:

```
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

The container must start a web server exposing the module API.

---

# 7. API Interface Requirements

Each module must expose three HTTP endpoints.

### Required endpoints

```
GET  /health
GET  /metadata
POST /execute
```

All endpoints must return JSON.

---

# 7.1 Health Endpoint

Used by the orchestrator to verify that your service is running.

```
GET /health
```
Must:
- Return HTTP 200.
- Respond quickly (no heavy logic).
- Not depend on external services.


Example response:

```
{
  "status":"ok",
  "module_name":"policy-simulator",
  "version":"0.1.0"
}
```
This endpoint is used for:
- Container healthchecks
- Orchestration readiness

---

# 7.2 Metadata Endpoint

Provides module information used for orchestration and debugging.

```
GET /metadata
```

---

# 7.3 Execute Endpoint

This is the **main entry point** used by the orchestrator.

```
POST /execute
```
Your module must:
- Accept JSON input.
- Return structured JSON output.
- Never return raw text or HTML.

### Required Response Structure

```
{
  "module_name": "policy-simulator",
  "version": "0.1.0",
  "status": "success",
  "output": {},
  "artifacts": []
}
```
### Required Response Fields

| Field       | Description                 |
| ----------- | --------------------------- |
| module_name | name of the module          |
| version     | module version              |
| status      | success or failure          |
| output      | structured JSON result      |
| artifacts   | list of artifact references |

---

# 8. Service Port

All modules must listen on:

```
8080
```

---

# 9. Environment Variables

Each module must include:

```
.env.example
```
### Important Rule
- .env.example → committed to Git

- .env → NOT committed (local runtime only)

Each developer must create:

```
cp .env.example .env
```

### Important 
Add the following at the bottom of your .gitignore to allow Git to track your .env.example file. 

```
# Allow example env templates (must be AFTER any .env / .env.* ignores)
!.env.example
!**/.env.example
```

### Example env.example

```
OPS_ENV=dev
OPS_LOG_LEVEL=INFO
OPS_PORT=8080
OPS_ARTIFACT_ROOT=/var/openpolicystack/artifacts
OPS_MODULE_NAME=policy-simulator
```
### Why This Matters

This prevents;
- Missing environment variables in deployment.
- Inconsistent runtime configuration.
- Integration failures on the VM.

---

# 10. Artifact Storage (Validated Behavior)

Artifacts must be written to:

```
/var/openpolicystack/artifacts
```

Each module must create its own subdirectory:

```
/var/openpolicystack/artifacts/<module-name>/
```

Example:

```
/var/openpolicystack/artifacts/integration-pilot/<file>.json
```

---

### Artifact Response Format

```
{
  "artifacts": [
    {
      "module_name":"policy-simulator",
      "file_path":"/var/openpolicystack/artifacts/policy-simulator/output.json",
      "type":"output"
    }
  ]
}
```

---

### Important

- The orchestrator reads **references**, not raw files.
- All containers share the same mounted volume.
- Do not use local paths outside `/var/openpolicystack/artifacts`.

---

# 11. Logging

Modules must log to:

```
stdout / stderr
```
Use structured JSON logs.

---

# 12. Module Manifest

Each module must include a `module.yaml`.

```
module_name: policy-simulator
version: 0.1.0

interface:
  type: http
  port: 8080
  health: /health
  metadata: /metadata
  execute: /execute
```

---

# 13. Local Testing
Before integration:

```
docker build -t openpolicystack/<module-name> .
docker run -p 8080:8080 openpolicystack/<module-name>
```

Test endpoint:

```
curl http://localhost:8080/health
```

---

# 14. Integration Testing (Validated Workflow)
Once integrated with the orchestrator:

```
docker compose build
docker compose up-d
docker composeps
```

Test orchestrator:

```
curl http://localhost:8100/health
```

Test execution:

```
curl-X POST http://localhost:8100/execute \
-H"Content-Type: application/json" \
-d'{"test":"hello"}'
```

---


# 15. Integration Checklist

Before submitting your module for integration, verify:

✔ Docker builds successfully.

✔ Service runs on port 8080.

✔ /health returns 200.

✔ /execute returns valid JSON.

✔ .env.example included.

✔ artifacts written to shared volume.

✔ response includes artifacts field.

✔ module follows integration-pilot pattern.

---

# 16. Common Mistakes
### Using localhost for inter-service calls

Wrong:

```
http://localhost:8080
```

Correct:

```
http://orchestrator:8080
```

---

### Missing `.env.example`

This causes deployment failures on the VM.

---

### Health endpoint too slow

Healthchecks will fail → container marked unhealthy.

---

### Writing artifacts outside shared volume

Artifacts will not be visible to other services.

# 17. Final Note

The integration-pilot module is the single source of truth for:

- Correct module behavior.

- Correct response structure.

- Correct artifact handling.

- Correct environment configuration.

If your module behaves differently, it will fail integration.

