from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class Proveedor(BaseModel):
    rpe: str = Field(..., alias='rpe')
    razon_social: Optional[str] = Field(None, alias='razon_social')
    direccion: Optional[str] = Field(None, alias='direccion')
    contacto: Optional[str] = Field(None, alias='contacto')
    correo_contacto: Optional[str] = Field(None, alias='correo_contacto')
    telefono_contacto: Optional[str] = Field(None, alias='telefono_contacto')
    celular_contacto: Optional[str] = Field(None, alias='celular_contacto')
    posicion_contacto: Optional[str] = Field(None, alias='posicion_contacto')
    fecha_creacion_empresa: Optional[str] = Field(None, alias='fecha_creacion_empresa')

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class Contrato(BaseModel):
    rpe: Optional[str] = Field(None, alias='rpe')
    rpe_proveedor: Optional[str] = Field(None, alias='rpe_proveedor')
    razon_social: Optional[str] = Field(None, alias='razon_social')
    fecha_creacion_contrato: Optional[str] = Field(None, alias='fecha_creacion_contrato')
    descripcion: Optional[str] = Field(None, alias='descripcion')
    nombre_unidad_compra: Optional[str] = Field(None, alias='nombre_unidad_compra')
    codigo_item: Optional[str] = Field(None, alias='codigo_item')

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class Person(BaseModel):
    person_id: str
    name: str
    normalized_name: Optional[str] = None
    emails: List[str] = []
    phones: List[str] = []
    positions: List[str] = []
    companies: List[Dict[str, Any]] = []

class Relationship(BaseModel):
    person_id: str
    person_name: str
    rpe: str
    company_name: str
    relationship_type: str = 'REPRESENTATIVE_FOR'
    position: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class RiskFactor(BaseModel):
    factor: str
    score: Optional[float] = None
    type: Optional[str] = None

class RiskReport(BaseModel):
    entity: str
    rpe: str
    risk_score: float
    risk_level: str
    factors: List[str]
    evidence: Dict[str, Any]

class ForensicHit(BaseModel):
    rpe: str
    risk_score: float
    reason: str

# --- API Request/Response Models ---

class IngestRequest(BaseModel):
    target: str = "all"  # 'all', 'contratos', 'proveedores', etc.

class RiskRequest(BaseModel):
    entity_id: str
    context: Optional[str] = None

class BriefRequest(BaseModel):
    context: str
    template: str = "standard"