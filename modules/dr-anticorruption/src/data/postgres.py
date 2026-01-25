import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
from typing import List, Dict, Any
from src.config.config import config

logger = logging.getLogger(__name__)

class PostgresManager:
    def __init__(self):
        self.dsn = config.get('postgres.dsn', 'postgresql://postgres:postgres@localhost:5432/datalake')
        self.conn = None
        try:
            self.connect()
        except Exception as e:
            logger.warning(f"Could not connect to Postgres on init: {e}. System will use local fallback.")

    def connect(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(self.dsn)

    def _init_db(self):
        self.connect()
        cur = self.conn.cursor()
        # cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        self.conn.commit()

        # Hypertable stub for contratos (time-partitioned)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dgcp_contratos (
                ingest_time TIMESTAMPTZ NOT NULL,
                rpe TEXT,
                razon_social TEXT,
                monto_total NUMERIC,
                fecha_aprobacion DATE,
                descripcion TEXT
            );
        """)
        # cur.execute("SELECT create_hypertable('dgcp_contratos', 'ingest_time', if_not_exists => TRUE);")

        # Regular table for proveedores (static master data)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dgcp_proveedores (
                rpe TEXT PRIMARY KEY,
                razon_social TEXT,
                direccion TEXT,
                fecha_creacion_empresa DATE
            );
        """)

        # Tables for Graph/Entity Analysis
        cur.execute("""
            CREATE TABLE IF NOT EXISTS risk_persons (
                person_id TEXT PRIMARY KEY,
                name TEXT,
                normalized_name TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS risk_relationships (
                id SERIAL PRIMARY KEY,
                person_id TEXT REFERENCES risk_persons(person_id),
                rpe TEXT,
                company_name TEXT,
                relationship_type TEXT,
                position TEXT
            );
        """)

        self.conn.commit()
        cur.close()
        logger.info("Postgres hypertables and graph tables initialized.")

    def insert_batch(self, data: List[Dict[str, Any]], table: str):
        """Stub for batch insert/upsert."""
        self.connect()
        cur = self.conn.cursor()
        for item in data:
            item['ingest_time'] = datetime.now()
            
            if table == 'dgcp_contratos':
                cur.execute("""
                    INSERT INTO dgcp_contratos (ingest_time, rpe, razon_social, monto_total, fecha_aprobacion, descripcion)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (rpe) DO NOTHING;
                """, (item.get('ingest_time'), item.get('rpe'), item.get('razon_social'), 
                      item.get('monto_total'), item.get('fecha_aprobacion'), item.get('descripcion')))
            
            elif table == 'risk_persons':
                cur.execute("""
                    INSERT INTO risk_persons (person_id, name, normalized_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (person_id) DO NOTHING;
                """, (item.get('person_id'), item.get('name'), item.get('normalized_name')))
                
            elif table == 'risk_relationships':
                cur.execute("""
                    INSERT INTO risk_relationships (person_id, rpe, company_name, relationship_type, position)
                    VALUES (%s, %s, %s, %s, %s);
                """, (item.get('person_id'), item.get('rpe'), item.get('company_name'), 
                      item.get('relationship_type'), item.get('position')))
        self.conn.commit()
        cur.close()
        logger.info(f"Inserted {len(data)} records to {table}")

    def query_last_ingest(self, table: str) -> str:
        """Get timestamp of last ingest for delta logic."""
        self.connect()
        cur = self.conn.cursor()
        cur.execute(f"SELECT max(ingest_time) FROM {table};")
        result = cur.fetchone()
        cur.close()
        return result[0].isoformat() if result[0] else None

    def query_graph_data(self):
        """Fetch all graph nodes and edges for in-memory analysis."""
        self.connect()
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        
        # Ensure tables exist (lazy init for demo)
        self._init_db()

        try:
            cur.execute("SELECT * FROM risk_persons;")
            persons = cur.fetchall()
            
            cur.execute("SELECT * FROM risk_relationships;")
            relationships = cur.fetchall()
            
            # dgcp_proveedores might be empty if we haven't ingested it into DB yet
            # return empty list if table empty or not found
            try:
                cur.execute("SELECT rpe, razon_social, direccion FROM dgcp_proveedores;")
                providers = cur.fetchall()
            except:
                self.conn.rollback()
                providers = []
            
            return persons, relationships, providers
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error querying graph data: {e}")
            return [], [], []
        finally:
            cur.close()

    def close(self):
        if self.conn:
            self.conn.close()