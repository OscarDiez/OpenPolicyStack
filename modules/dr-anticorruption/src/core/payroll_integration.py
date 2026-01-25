
import pandas as pd
import logging
from typing import List, Dict
from pathlib import Path
from src.data.postgres import PostgresManager

logger = logging.getLogger("PayrollIntegrator")

class PayrollIntegrator:
    """
    Parses standard 'Nómina Publica' Excel/CSV files to enrich the connection graph.
    Source: map.gob.do / datos.gob.do
    """
    def __init__(self):
        self.pg = PostgresManager()
        self._init_schema()

    def _init_schema(self):
        try:
            self.pg.connect()
            cur = self.pg.conn.cursor()
            # New Graph Nodes: Public Officials
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public_officials (
                    cedula TEXT PRIMARY KEY,
                    full_name TEXT,
                    institution TEXT,
                    position TEXT,
                    salary NUMERIC,
                    status TEXT, -- 'FIJO', 'TEMPORAL', 'CONTRATADO'
                    last_updated TIMESTAMP DEFAULT NOW()
                );
            """)
            # Graph Edges: We will link 'risk_persons' to 'public_officials' by Name matching
            # This allows us to see if a Contractor (Risk Person) is also a Public Official.
            self.pg.conn.commit()
            cur.close()
        except Exception as e:
            logger.warning(f"DB Init failed: {e}")

    def parse_payroll_file(self, filepath: str, institution_name: str) -> List[Dict]:
        """
        Reads a standard DIGEIG Payroll Excel file.
        Columns usually: 'Nombre', 'Cargo', 'Estatus', 'Sueldo Bruto'
        """
        records = []
        try:
            df = pd.read_excel(filepath)
            # Normalizing column names
            df.columns = [c.upper().strip() for c in df.columns]
            
            # Common column mappings
            col_map = {
                'NOMBRE': 'full_name',
                'EMPLEADO': 'full_name',
                'CARGO': 'position',
                'FUNCION': 'position',
                'SUELDO BRUTO': 'salary',
                'SALARIO': 'salary',
                'ESTATUS': 'status'
            }
            
            # Identify valid columns
            valid_cols = {k: v for k, v in col_map.items() if k in df.columns}
            if not valid_cols:
                logger.error(f"No recognizing columns in {filepath}. Columns: {df.columns}")
                return []

            for _, row in df.iterrows():
                # Extract data
                name = row.get(next((k for k,v in valid_cols.items() if v == 'full_name'), None))
                pos = row.get(next((k for k,v in valid_cols.items() if v == 'position'), None))
                sal = row.get(next((k for k,v in valid_cols.items() if v == 'salary'), 0))
                
                if name and isinstance(name, str):
                    records.append({
                        "full_name": name.strip().upper(),
                        "institution": institution_name,
                        "position": pos,
                        "salary": sal,
                        "status": "ACTIVE" 
                    })
            
            logger.info(f"Extracted {len(records)} officials from {institution_name}")
            return records

        except Exception as e:
            logger.error(f"Parsing failed: {e}")
            return []

    def load_into_graph(self, officials: List[Dict]):
        """
        Syncs officials to DB and runs a conflict check against RiskPersons.
        """
        # Fallback: Dump to JSON for RiskService to pick up if DB is down
        try:
            import json
            dump_path = Path("data/raw/public_officials_dump.json")
            with open(dump_path, 'w', encoding='utf-8') as f:
                json.dump(officials, f, indent=2, default=str)
            logger.info(f"Dumped {len(officials)} officials to {dump_path}")
        except Exception as e:
            logger.warning(f"Failed to dump JSON: {e}")

        try:
            self.pg.connect()
            cur = self.pg.conn.cursor()
            
            for off in officials:
                # 1. Insert/Update Official
                cur.execute("""
                    INSERT INTO public_officials (cedula, full_name, institution, position, salary, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cedula) DO UPDATE SET
                        position = EXCLUDED.position,
                        salary = EXCLUDED.salary,
                        last_updated = NOW();
                """, ('generate_hash_' + off['full_name'], off['full_name'], off['institution'], off['position'], off['salary'], off['status']))
                
                # 2. Influence Analysis: Link back to Graph
                # If this name exists in 'risk_persons' (contractors), we have a DIRECT HIT.
                cur.execute("SELECT person_id FROM risk_persons WHERE normalized_name = %s", (off['full_name'],))
                match = cur.fetchone()
                if match:
                    logger.warning(f"CONFLICT OF INTEREST: {off['full_name']} is an Official at {off['institution']} and a Registered Supplier Representative!")
                    # Create graph edge: Person -> [HAS_JOB] -> Institution
            
            self.pg.conn.commit()
            cur.close()
        except Exception as e:
            logger.error(f"Graph Sync failed: {e}")

if __name__ == "__main__":
    # Test Stub
    logging.basicConfig(level=logging.INFO)
    integrator = PayrollIntegrator()
    print("Payroll Integrator Ready. Feed me Excel files.")
