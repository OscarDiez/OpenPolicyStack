# Thesis Scope – Adrian Con García

This repository is part of the broader OpenPolicyStack project.  
This document clarifies the scope of the work developed and evaluated in the corresponding thesis.

## Scope of Contribution

The thesis focuses specifically on the design, implementation, and evaluation of the **orchestration layer** and its integration interface.

The evaluated software artifact consists of:

- `modules/orchestrator/` → central orchestration service (primary contribution)
- `modules/integration-pilot/` → controlled validation module used to test integration and evaluation conditions
- `compose.yaml` → minimal deployment configuration used to run the system

Other modules present in the repository are part of the wider collaborative project and are **not part of the evaluated contribution**.

## Evaluated System State

The version contained in this branch corresponds to the **instrumented evaluation state** of the system.

Starting from a working end-to-end orchestration prototype (baseline MVP), the system was incrementally extended to enable empirical evaluation of the following properties:

- reproducibility
- traceability
- artifact integrity
- execution trace reconstruction
- failure handling robustness

These properties were evaluated through a structured experimental framework (E1–E5) as described in the thesis.

## Important Notes

- The orchestrator was extended with structured metadata capture and hashing mechanisms to support empirical validation.
- The integration-pilot module was intentionally used as a controlled environment to isolate and test orchestration behavior before integrating external modules.
- A controlled failure trigger used exclusively for evaluation purposes has been disabled in this version.

## How to Navigate

For reviewers interested in the evaluated artifact:

1. Start with: `modules/orchestrator/`
2. See integration behavior in: `modules/integration-pilot/`
3. Use `compose.yaml` to understand how services are connected

This subset of the repository corresponds to the system evaluated in the thesis.