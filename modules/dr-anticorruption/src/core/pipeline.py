from src.core.ingestion import IngestionService
from src.core.risk_service import RiskService
from src.data.data_manager import data_manager

class RiskPipeline:
    def __init__(self):
        self.ingestion = IngestionService()
        self.risk = RiskService()

    def run_full(self, target='all', max_pages=None):
        """
        Executes the full anti-corruption pipeline:
        1. Ingest Data from Official Sources
        2. Perform Risk Analysis
        """
        # 1. Ingestion
        self.ingestion.ingest(target, max_pages)
        
        # 2. Risk Analysis (Batch)
        # Note: In a production environment, this might be triggered per entity
        self.risk.batch_analyze(limit=10)

    def analyze_entity(self, entity_id: str):
        """Analyzes a specific entity."""
        # Find supplier in database/files
        proveedores = self.risk.pg.query_graph_data()[2] if hasattr(self.risk, 'pg') else []
        if not proveedores:
            proveedores = data_manager.load_latest('proveedores_full_*.json')
        
        supplier = next((p for p in proveedores if str(p.get('rpe')) == entity_id), None)
        if supplier:
            return self.risk.analyze_supplier(supplier.get('razon_social', 'Unknown'), supplier)
        return None
