# OpenPolicyStack – Deployment & Validation Guide

## Purpose
This folder contains deployment-related artifacts for OpenPolicyStack, including the full architecture skeleton and basic validation instructions.

At this stage, the system is validated through a **minimal runnable pilot stack** composed of:
- `orchestrator` (system coordinator)
- `integration-pilot` (reference module)

---

## Deployment Files

- `../compose.yaml`  
  → Current **runnable pilot stack** (validated baseline)

- `compose.target-skeleton.yaml`  
  → **Full intended architecture** (not yet fully runnable; used as integration target)

---

## Pilot Validation Procedure

Run all commands from the repository root:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
```
Test the orchestrator:

```
curl http://localhost:8100/health
```

Execute a sample workflow:

```
curl-X POST http://localhost:8100/execute \
-H"Content-Type: application/json" \
-d'{"test":"hello","source":"vm-check"}'
```

Inspect shared artifacts:

```
docker compose exec orchestratorls-R /var/openpolicystack/artifacts
```

Inspect metadata:

```
docker compose exec orchestratorls-R /var/openpolicystack/metadata
```

---

## Expected Outcome

A successful validation should confirm:

- Both containers build and run successfully
- Both services report **healthy** status
- Orchestrator responds on `http://localhost:8100`
- Orchestrator can resolve `integration-pilot` via Docker network
- Shared artifact volume is written and visible across containers
- Metadata database (`orchestrator.db`) is created

---

## Current Scope

The pilot validates:

- Basic orchestration flow (`/execute`)
- Service-to-service communication
- Shared artifact storage
- Metadata persistence (SQLite)
- Contract-compliant module execution

Not yet covered:

- Multi-module integration
- Real module onboarding from teammates
- Full evaluation framework (E1–E5)
- Production deployment considerations

---

## Common Issues

- Missing `.env` files (must be created from `.env.example`)
- Incorrect file paths or build contexts
- Missing or incorrect Dockerfile
- Wrong application entrypoint (`app.main`)
- Running commands outside repo root

---

## Next Steps

- Expand orchestrator metadata layer (`runs`, `module_calls`, `artifacts`)
- Strengthen determinism and reproducibility guarantees
- Introduce evaluation tests (E1–E5)
- Onboard first real module into the stack
- Progressively align with `compose.target-skeleton.yaml`