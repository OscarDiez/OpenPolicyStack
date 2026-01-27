# Supply-Chain Risk (Quantum Tech)

**Owner:** Karl M. Kohler

## Scope
This module provides a **first-order supply-chain risk assessment** for quantum computing components and segments.  
It is designed as an **independent microservice** within the OpenPolicyStack ecosystem.

Given a region and a quantum component, the service returns:
- a simple risk score,
- the main drivers of risk,
- and a short policy-oriented brief suitable for dashboards or demos.

The MVP deliberately prioritizes **reproducibility, transparency, and a clear interface** over final data completeness or model sophistication.

---

## Inputs (MVP)
- **country_or_region**  
  Target economy or region (e.g. EU, US, China).

- **segment_or_component**  
  Quantum-technology segment or component  
  (e.g. cryogenics, photonics, ion-trap components, control electronics).

- **optional: scenario**  
  High-level disruption or policy scenario  
  (e.g. export restriction, supplier disruption).

- **optional: year / time window**  
  Included for forward compatibility; not yet used in the MVP logic.

---

## Outputs (MVP)
- **risk_score**  
  Relative risk score (0–1 in the current implementation).

- **confidence / risk_level**  
  Qualitative indicator (e.g. low / medium).

- **key_drivers**  
  Main contributing factors  
  (e.g. supplier concentration, low substitutability, policy exposure).

- **brief**  
  Short text explanation suitable for a policy dashboard or demo interface.

---

## How to Run (MVP)

The MVP exposes a **minimal API**.

### Local setup
```bash
cd modules/supplychain-risk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.app:app --reload
