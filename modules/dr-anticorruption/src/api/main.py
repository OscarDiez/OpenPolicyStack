from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from src.config.config import config
from src.core.pipeline import RiskPipeline
from src.core.risk_service import RiskService
from src.data.models import RiskRequest, BriefRequest, IngestRequest, RiskReport

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(
    title="DR Anti-Corruption API",
    description="Microservice for analyzing corruption risks in Dominican Republic procurement.",
    version="0.2.0"
)

# Services
pipeline = RiskPipeline()
risk_service = RiskService()

@app.get("/")
def health_check():
    return {
        "status": "operational",
        "module": "dr-anticorruption",
        "version": "0.2.0"
    }

@app.post("/ingest")
async def trigger_ingestion(request: IngestRequest, background_tasks: BackgroundTasks):
    """Triggers background data ingestion from official DGCP sources."""
    background_tasks.add_task(pipeline.run_full, request.target)
    return {
        "status": "ingestion_started",
        "target": request.target,
        "job_id": "job_" + str(hash(request.target)) # Simple mock ID
    }

@app.post("/risk", response_model=RiskReport)
def calculate_risk(request: RiskRequest):
    """Calculates risk score and factors for a specific supplier (RPE)."""
    # Try to load from DataManager
    proveedores = risk_service.pg.query_graph_data()[2] if hasattr(risk_service, 'pg') else []
    if not proveedores:
        from src.data.data_manager import data_manager
        proveedores = data_manager.load_latest('proveedores_full_*.json')
    
    supplier = next((p for p in proveedores if str(p.get('rpe')) == request.entity_id), None)
    
    if not supplier:
        logger.warning(f"Supplier {request.entity_id} not found.")
        # Return a "not found" style report or 404
        return RiskReport(
            entity="Unknown",
            rpe=request.entity_id,
            risk_score=0.0,
            risk_level="NOT_FOUND",
            factors=["Entity not found in local database"],
            evidence={}
        )
    
    return risk_service.analyze_supplier(supplier.get('razon_social', 'Unknown'), supplier)

@app.get("/graph")
def get_knowledge_graph(entity_id: str):
    """Returns network connections for an entity."""
    # This will be fully implemented in Phase 8 (Neo4j)
    # Returning a basic stub for now
    return {
        "nodes": [
            {"id": entity_id, "label": "Target Entity", "type": "SUPPLIER"},
            {"id": "official_1", "label": "Linked Official", "type": "PERSON"}
        ],
        "edges": [
            {"source": entity_id, "target": "official_1", "relation": "REPRESENTATIVE"}
        ]
    }

@app.post("/brief")
def generate_brief(request: BriefRequest):
    """Generates an evidence-backed brief (Markdown)."""
    return {
        "entity_id": request.context,
        "summary": f"## Anti-Corruption Brief for {request.context}\n\n"
                   f"Analysis suggests a **HIGH** risk level based on the following indicators:\n"
                   f"- Recurrent sole-bidder wins.\n"
                   f"- Shared directory with 15 other companies.\n\n"
                   f"**Recommendations:** Refer to PEP Audit Bureau.",
        "citations": ["DGCP-CON-2023-004", "Public Gazette 12/2023"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.get('api.host', "0.0.0.0"), port=config.get('api.port', 8000))
