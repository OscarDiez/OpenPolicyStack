import sqlite3
import logging
from pathlib import Path

from .data_manager import data_manager
from .models import Proveedor, Contrato, Person, Relationship  # Validate later

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = Path('data') / 'dr_anticorruption.db'
        self.conn = None
        self._init_db()

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Proveedores
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS proveedores (
                    rpe TEXT PRIMARY KEY,
                    razon_social TEXT,
                    direccion TEXT,
                    contacto TEXT,
                    correo_contacto TEXT,
                    telefono_contacto TEXT,
                    fecha_creacion_empresa TEXT
                )
            ''')
            # Contratos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contratos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rpe TEXT,
                    razon_social TEXT,
                    fecha_creacion_contrato TEXT,
                    descripcion TEXT,
                    nombre_unidad_compra TEXT
                )
            ''')
            # Persons
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS persons (
                    person_id TEXT PRIMARY KEY,
                    name TEXT,
                    normalized_name TEXT,
                    emails TEXT,  -- JSON
                    phones TEXT,  -- JSON
                    positions TEXT  -- JSON
                )
            ''')
            # Relationships
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS relationships (
                    person_id TEXT,
                    rpe TEXT,
                    company_name TEXT,
                    relationship_type TEXT DEFAULT 'REPRESENTATIVE_FOR',
                    position TEXT,
                    email TEXT,
                    phone TEXT,
                    PRIMARY KEY (person_id, rpe)
                )
            ''')
            # Forensic Hits
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS forensic_hits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rpe TEXT,
                    type TEXT,
                    score REAL,
                    reason TEXT
                )
            ''')
            conn.commit()
            logger.info(f"DB initialized at {self.db_path}")

db = Database()
