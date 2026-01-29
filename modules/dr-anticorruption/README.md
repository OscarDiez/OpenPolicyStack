# DR Anti-Corruption Module (Dominican Republic)

This module provides an end-to-end pipeline for detecting corruption risks in public procurement in the Dominican Republic. It ingests official sources, connects entities, calculates risk scores, and generates evidence-backed policy briefs.

## 🚀 Overview
- **Lead:** Brian Collado
- **Scope:** DR procurement data -> Entity/Contract linking -> Risk indicators -> Evidence-linked briefs.
- **Status:** MVP Implementation.

## 📥 Inputs & 📤 Outputs

### Inputs
- **Procurement Data:** Official JSON/Excel files from DGCP (Dirección General de Contrataciones Públicas).
- **Target Entities:** RPE (Registro de Proveedores del Estado) or company names for tailored risk analysis.
- **Config Parameters:** Custom thresholds for activation spikes, bidder concentration, and flags for politically exposed persons (PEPs).

### Outputs
- **Risk Score:** Numerical score (0-100) indicating corruption risk.
- **Risk Level:** Categorical risk (LOW, MEDIUM, HIGH, CRITICAL).
- **Evidence Graph:** Relationship mapping between companies, owners, and contracts.
- **Policy Brief:** Contextual summary of findings with citations to specific contracts or legal violations.

## 🛠 How to Run

### Docker (Recommended)
The module is designed to run in a containerized environment.

```bash
docker-compose up -d
```
Access the API at `http://localhost:8000`.

### Local Development
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run ingestion pipeline:
   ```bash
   python src/cli.py ingest --target all
   ```
3. Start the API:
   ```bash
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000
   ```

## 🌐 API Interface (MVP)

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/ingest` | `POST` | Triggers background ingestion of official DR sources. |
| `/risk` | `POST` | Returns a detailed risk report for a specific entity. |
| `/graph` | `GET` | Returns JSON representation of the entity's network. |
| `/brief` | `POST` | Generates a 1-page PDF/Text brief with evidence. |

### Example Scenario
**Goal:** Analyze a suspicious supplier involved in multiple "emergency" contracts.
1. **Request:** `POST /risk` with `{"entity_id": "12345"}`.
2. **Response:** 
   ```json
   {
     "risk_score": 85.5,
     "level": "HIGH",
     "factors": ["Concentration of emergency contracts", "Shared ownership with public official"],
     "evidence": ["Contract #992-2023", "Public Gazette Ref ID: X"]
   }
   ```

## 📂 Project Structure
- `src/api/`: FastAPI implementation.
- `src/core/`: Risk engine, Forensic analyzers, and Brief generator.
- `src/data/`: Data management and persistence (SQLite/Postgres).
- `config/`: Configuration for thresholds and API keys.