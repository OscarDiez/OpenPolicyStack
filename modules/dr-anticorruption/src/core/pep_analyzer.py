
import logging
import requests
import pdfplumber
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from src.data.postgres import PostgresManager
from src.config.config import config

logger = logging.getLogger("PEPAnalyzer")

class PEPAnalyzer:
    def __init__(self):
        self.raw_dir = Path("data/raw/ccrd")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.pg = PostgresManager()
        try:
            self._init_tables()
        except Exception as e:
            logger.warning(f"Skipping table initialization (DB down): {e}")

    def _init_tables(self):
        """Initialize PEP related tables in Postgres."""
        self.pg.connect()
        cur = self.pg.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pep_registry (
                pep_id SERIAL PRIMARY KEY,
                name TEXT,
                normalized_name TEXT UNIQUE,
                institution TEXT,
                position TEXT,
                status TEXT, -- e.g., 'OMISO', 'CUMPLIO', 'EXTEMPORANEO'
                report_source TEXT,
                last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.pg.conn.commit()
        cur.close()

    def download_report(self, url: str, filename: str) -> Path:
        """Download a PDF report from Cámara de Cuentas."""
        filepath = self.raw_dir / filename
        logger.info(f"Downloading report from {url}...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(filepath, 'wb') as f:
                f.write(response.content)
            logger.info(f"Report saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to download report: {e}")
            return None

    def parse_omisos_pdf(self, filepath: Path):
        """Parse the 'Omisos' PDF and extract data."""
        peps = []
        logger.info(f"Parsing PDF: {filepath}")
        try:
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if not table:
                        continue
                    
                    # Assume table structure: [Name, Institution, Position, ...]
                    # We might need to handle headers on each page
                    for row in table:
                        # Clean row data
                        row = [str(cell).strip() for cell in row if cell]
                        
                        if not row: continue

                        # Header detection
                        if "NOMBRE" in row[0] or "INSTITUCIÓN" in row[0]:
                            continue
                        
                        name, institution, position = "UNKNOWN", "UNKNOWN", "UNKNOWN"

                        # Heuristic V2:
                        # Sometimes PDF extraction merges everything into one cell:
                        # "2 LAUREANO GUERRERO SANCHEZ ... 339-20 ... OFICINA ..."
                        if len(row) == 1:
                            parts = row[0].split()
                            # It's hard to split perfectly without separators, but let's try basic heuristics
                            if len(parts) > 5:
                                name = " ".join(parts[1:5]) # Guess name is first few words after index
                                institution = "Check PDF Manual"
                                position = "Check PDF Manual"
                            else:
                                continue # Garbage row
                        
                        elif len(row) >= 3:
                            # 0: Index/Name mixed? 1: Decree? 2: Institution/Position?
                            # Standard format: [Index Name, Decree, Institution Position Status]
                            # Or: [Name, Institution, Position]
                            
                            # Let's assume indices are in the first column "1 NAME NAME"
                            col0 = row[0]
                            # Remove leading number "1 "
                            import re
                            name = re.sub(r'^\d+\s+', '', col0)
                            
                            institution = row[1]
                            position = row[2]

                        if len(name) < 4 or "UNKNOWN" in name:
                            continue

                        peps.append({
                            "name": name,
                            "normalized_name": name.upper(),
                            "institution": institution,
                            "position": position,
                            "status": "OMISO",
                            "report_source": filepath.name
                        })
            
            logger.info(f"Extracted {len(peps)} records from PDF.")
            return peps
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            return []

    def sync_to_db(self, peps: List[Dict]):
        """Upsert PEP records into the database."""
        try:
            self.pg.connect()
            cur = self.pg.conn.cursor()
            count = 0
            for pep in peps:
                try:
                    cur.execute("""
                        INSERT INTO pep_registry (name, normalized_name, institution, position, status, report_source)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (normalized_name) DO UPDATE SET
                            status = EXCLUDED.status,
                            report_source = EXCLUDED.report_source,
                            last_updated = CURRENT_TIMESTAMP;
                    """, (pep['name'], pep['normalized_name'], pep['institution'], 
                          pep['position'], pep['status'], pep['report_source']))
                    count += 1
                except Exception as e:
                    logger.error(f"Error syncing PEP {pep['name']}: {e}")
                    self.pg.conn.rollback()
            
            self.pg.conn.commit()
            cur.close()
            logger.info(f"Synced {count} PEP records to Data Lake.")
        except Exception as e:
            logger.error(f"Failed to connect to Data Lake for sync: {e}")
            self.save_to_json(peps)

    def save_to_json(self, peps: List[Dict]):
        """Fallback: Save extraction to JSON if DB is down."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pep_extraction_{timestamp}.json"
        filepath = self.raw_dir / filename
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(peps, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(peps)} PEP records to fallback JSON: {filepath}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyzer = PEPAnalyzer()
    
    # Example: List of designados omisos 2024
    url = "https://camaradecuentas.gob.do/phocadownload/Area_sustantivas/Declaracion_Jurada/Reportes/OMISOS/2024/HIST%C3%93RICO%20%28+%29/Hist%C3%B3rico-Listado%20omisos%20designados%20identificados.pdf"
    filename = "omisos_designados_2024.pdf"
    
    # Step 1: Download
    pdf_path = analyzer.download_report(url, filename)
    
    # Step 2: Parse if successful
    if pdf_path and pdf_path.exists():
        extracted_data = analyzer.parse_omisos_pdf(pdf_path)
        
        # Step 3: Sync
        if extracted_data:
            analyzer.sync_to_db(extracted_data)
