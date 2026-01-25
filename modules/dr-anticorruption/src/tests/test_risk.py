import pytest
from src.core.risk_service import RiskService
from src.data.data_manager import data_manager

def test_analyze_supplier():
    service = RiskService()
    proveedores = data_manager.load_latest('proveedores_full_*.json')
    if proveedores:
        supplier = proveedores[0]
        report = service.analyze_supplier(supplier['razon_social'], supplier)
        assert report.risk_score >= 0
        assert report.risk_level in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    else:
        pytest.skip("No proveedores data")

if __name__ == "__main__":
    pytest.main([__file__])
