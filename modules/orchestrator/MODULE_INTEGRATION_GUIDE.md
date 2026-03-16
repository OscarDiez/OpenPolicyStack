# OpenPolicyStack Module Integration Guide

**File:** `MODULE_INTEGRATION_GUIDE.md`

**Version:** 1.0

**Status:** Frozen Module Integration Guide

---

# 1. Overview

This guide explains how to prepare your module so that it can be integrated into the **OpenPolicyStack orchestration system**.

All modules in OpenPolicyStack operate as **independent containerized microservices** coordinated by a central orchestrator.

Your module will:

- run inside a Docker container
- expose a lightweight REST API
- receive execution requests from the orchestrator
- return structured outputs and artifact references

You **do not need to implement orchestration logic**.

Your module simply exposes a consistent interface and performs its analysis.

---

# 2. High-Level Integration Flow

When OpenPolicyStack runs a workflow, the following occurs:

1. The orchestrator generates a **run_id**.
2. The orchestrator calls your module via HTTP.
3. Your module performs its computation.
4. Your module returns structured JSON results.
5. Any large outputs are saved as artifacts.
6. The orchestrator records execution metadata.

Your module remains **analytically independent** but participates in the **shared execution environment**.

---

# 3. Module Repository Structure

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

Example:

```
modules/policy-simulator/
```

---

# 4. Naming Rules

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

- folder name
- Docker service name
- container hostname
- artifact directory name

---

# 5. Docker Container Requirement

Your module **must run inside a Docker container**.

Minimal example Dockerfile:

```
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ app/

CMD ["python", "app/main.py"]
```

The container must start a web server exposing the module API.

---

# 6. API Interface Requirements

Your module must expose three HTTP endpoints.

### Required endpoints

```
GET  /health
GET  /metadata
POST /execute
```

All endpoints must return JSON.

---

# 6.1 Health Endpoint

Used by the orchestrator to verify that your service is running.

```
GET /health
```

Example response:

```
{
  "status":"ok",
  "module_name":"policy-simulator",
  "version":"0.1.0"
}
```

---

# 6.2 Metadata Endpoint

Provides module information used for orchestration and debugging.

```
GET /metadata
```

Example:

```
{
  "module_name":"policy-simulator",
  "version":"0.1.0",
  "supported_tasks": [
"simulate_policy"
  ]
}
```

---

# 6.3 Execute Endpoint

This is the **main entry point** used by the orchestrator.

```
POST /execute
```

Example request:

```
{
  "run_id":"123e4567",
  "parameters": {
    "country":"DO"
  },
  "inputs": [],
  "metadata": {}
}
```

Example response:

```
{
  "module_name":"policy-simulator",
  "version":"0.1.0",
  "status":"success",
  "output": {
    "risk_score":0.41
  },
  "artifacts": []
}
```

Required response fields:

| Field | Description |
| --- | --- |
| module_name | name of the module |
| version | module version |
| status | success or failure |
| output | structured JSON result |
| artifacts | list of artifact references |

---

# 7. Service Port

Your API must listen on:

```
8080
```

Example FastAPI server:

```
uvicorn main:app --host 0.0.0.0 --port 8080
```

---

# 8. Environment Variables

All modules use environment variables prefixed with:

```
OPS_
```

Example variables:

```
OPS_MODULE_NAME=policy-simulator
OPS_PORT=8080
OPS_ARTIFACT_ROOT=/var/openpolicystack/artifacts
OPS_LOG_LEVEL=INFO
```

You must include a `.env.example` file documenting required variables.

---

# 9. Artifact Storage

Large outputs should be stored as **artifacts**.

Artifacts are saved in the shared directory:

```
/var/openpolicystack/artifacts
```

Directory structure:

```
artifacts/
└── runs/
    └── <run_id>/
        └── <module-name>/
            ├── inputs/
            ├── outputs/
            └── meta/
```

Example artifact:

```
artifacts/runs/abc123/policy-simulator/outputs/report.json
```

When returning artifacts in your response:

```
{
  "artifacts": [
    {
      "name":"simulation_report",
      "path":"artifacts/runs/abc123/policy-simulator/outputs/report.json"
    }
  ]
}
```

---

# 10. Logging

Modules must log to:

```
stdout
stderr
```

Use structured JSON logs.

Example:

```
{
  "timestamp":"2026-03-12T11:20:31Z",
  "level":"INFO",
  "service":"policy-simulator",
  "run_id":"abc123",
  "event":"simulation_started",
  "message":"Policy simulation initiated"
}
```

---

# 11. Module Manifest

Each module must include a `module.yaml`.

Example:

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

This allows automated module discovery.

---

# 12. Example Minimal FastAPI Module

Example `main.py`:

```
fromfastapiimportFastAPI
frompydanticimportBaseModel

app=FastAPI()

classExecuteRequest(BaseModel):
run_id:str
parameters:dict= {}
inputs:list= []
metadata:dict= {}

@app.get("/health")
defhealth():
return {
"status":"ok",
"module_name":"example-module",
"version":"0.1.0"
    }

@app.get("/metadata")
defmetadata():
return {
"module_name":"example-module",
"version":"0.1.0"
    }

@app.post("/execute")
defexecute(req:ExecuteRequest):
return {
"module_name":"example-module",
"version":"0.1.0",
"status":"success",
"output": {"example":True},
"artifacts": []
    }
```

---

# 13. Local Testing

You can test your module locally before integration.

Start your module:

```
docker build -t openpolicystack/example-module .
docker run -p 8080:8080 openpolicystack/example-module
```

Test endpoint:

```
curl http://localhost:8080/health
```

---

# 14. Integration Checklist

Before submitting your module for integration, verify:

✔ Module resides in `modules/<module-name>`

✔ Dockerfile builds successfully

✔ API listens on port `8080`

✔ `/health` endpoint works

✔ `/metadata` endpoint works

✔ `/execute` endpoint works

✔ module returns JSON response

✔ module returns version field

✔ `.env.example` included

✔ `module.yaml` included

✔ artifacts stored in correct directory

---

# 15. Common Mistakes

Avoid these common integration issues:

**Incorrect port**

```
5000
3000
```

Correct:

```
8080
```

---

**Using localhost for service calls**

Wrong:

```
http://localhost:8080
```

Correct:

```
http://data-layer:8080
```

---

**Returning non-JSON responses**

All API responses must be JSON.

---

# 16. Need Help?

If your module fails integration:

1. Check `docker logs`
2. Verify `/health` endpoint
3. Confirm port `8080`
4. Validate JSON responses