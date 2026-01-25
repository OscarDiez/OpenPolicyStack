import json
import glob
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
import sqlite3
import logging
from psycopg2.extras import RealDictCursor
from pathlib import Path

from src.config.config import config
from src.data.data_manager import data_manager
from src.data.database import db
from src.data.postgres import PostgresManager
from src.data.models import Person, Relationship, RiskReport, RiskFactor

from src.core.social_analyzer import SocialAnalyzer
from src.core.external.social_scraper import SocialScraper

logger = logging.getLogger("RiskService")

class RiskService:
    def __init__(self):
        self.news_client = None  # Lazy
        self.social_scraper = SocialScraper() 
        self.social_analyzer = SocialAnalyzer()
        self.cache: Dict = {}
        self.pg = PostgresManager()  # Connect to Data Lake
        self._load_graphs()
        self._build_indices()

    # ... (skipping unchanged properties)

    def _get_deep_intelligence(self, name: str) -> Dict:
        """
        Gather deep intelligence from News (SocialAnalyzer) and Social Media (SocialScraper).
        """
        points = 0
        factors = []
        all_hits = []
        veracity_score = 0

        # 1. News Analysis (The "Official" Filter)
        # We reuse the logic already built in SocialAnalyzer for legal risks
        # This checks for "Caso Antipulpo", "PGR", etc.
        logger.info(f"Running News Analysis for {name}...")
        # Note: analyze_legal_risks returns a list of "associations" dicts
        news_risks = self.social_analyzer.analyze_legal_risks([name])
        
        for risk in news_risks:
            points += 25
            factors.append(f"Alerta de Prensa: {risk.get('context')} ({risk.get('article_title')})")
            all_hits.append(risk)
            veracity_score = max(veracity_score, 3)

        # 2. Social Media OSINT (The "Street" Filter)
        if points > 0: # Only check social if we already have some suspicion, or always if configured
             pass 
        
        # Let's always run a quick social scan for high-risk profiles
        logger.info(f"Running Social OSINT for {name}...")
        social_hits = self.social_scraper.get_social_intelligence(name, limit=3)
        
        if social_hits:
            points += 10
            factors.append(f"Menciones en Redes Sociales (posible denuncia): {len(social_hits)} hits")
            all_hits.extend(social_hits)
            
        return {
            "points": min(points, 60), # Cap intel risk at 60
            "factors": list(set(factors)),
            "hits": all_hits,
            "veracity": veracity_score
        }

    def _load_graphs(self):
        """Load graph data directly from the Data Lake (Postgres)."""
        logger.info("Connecting to Data Lake...")
        try:
            # Fetch from DB
            db_persons, db_rels, db_providers = self.pg.query_graph_data()
            
            # 1. Load Persons
            if db_persons:
                self.persons = {p['person_id']: p for p in db_persons}
                logger.info(f"Loaded {len(self.persons)} persons from DB.")
            else:
                logger.warning("Data Lake is empty (persons). Fallback to JSON.")
                self.persons = data_manager.load_latest('persons_*.json')

            # 2. Load Relationships
            if db_rels:
                self.relationships = db_rels
                logger.info(f"Loaded {len(self.relationships)} relationships from DB.")
            else:
                self.relationships = data_manager.load_latest('relationships_*.json')
            
            # 3. Cache Providers for Address Hubs
            self.cached_providers = db_providers

            self.forensic_risks = self._load_forensic_risks()
            
        except Exception as e:
            logger.error(f"Data Lake Connection Failed: {e}. Falling back to local files.")
            self.persons = data_manager.load_latest('persons_*.json')
            self.relationships = data_manager.load_latest('relationships_*.json')
            self.cached_providers = []

    def _build_indices(self):
        self.company_to_people: Dict[str, List[str]] = {}
        self.person_to_companies: Dict[str, Set[str]] = {}
        self.rpe_to_address: Dict[str, str] = {}
        self.hub_density: Dict[str, int] = {}
        self._build_relationship_indices()
        self._build_address_hubs()
        logger.info("Built indices")

    def _build_relationship_indices(self):
        for rel in self.relationships:
            rpe = str(rel['rpe'])
            pid = rel['person_id']
            if rpe not in self.company_to_people:
                self.company_to_people[rpe] = []
            self.company_to_people[rpe].append(pid)
            if pid not in self.person_to_companies:
                self.person_to_companies[pid] = set()
            self.person_to_companies[pid].add(rpe)

    def _build_address_hubs(self):
        # Use DB data if available, else load JSON
        if hasattr(self, 'cached_providers') and self.cached_providers:
            proveedores = self.cached_providers
        else:
            proveedores = data_manager.load_latest('proveedores_full_*.json')
            
        rpe_to_owner_count = {}
        for rel in self.relationships:
            # Handle DB dict vs JSON dict keys if different
            # DB returns RealDictCursor, so keys are strings
            rpe = str(rel.get('rpe'))
            pid = rel.get('person_id')
            if rpe not in rpe_to_owner_count:
                rpe_to_owner_count[rpe] = set()
            rpe_to_owner_count[rpe].add(pid)
        self.hub_density = {}
        for p in proveedores:
            rpe = str(p.get('rpe'))
            addr = (p.get('direccion') or "").strip().upper()
            if len(addr) > 10:
                self.rpe_to_address[rpe] = addr
                owners = rpe_to_owner_count.get(rpe, set())
                if addr not in self.hub_density:
                    self.hub_density[addr] = set()
                self.hub_density[addr].update(owners)
        self.hub_density = {k: len(v) for k, v in self.hub_density.items()}
        logger.info(f"Physical hubs: {len([h for h in self.hub_density.values() if h > 2])} high-density")

    def _load_forensic_risks(self):
        forensic_risks = {}
        if Path('data/versatility_hits.json').exists():
            with open('data/versatility_hits.json', 'r', encoding='utf-8') as f:
                hits = json.load(f)
            for hit in hits:
                rpe = hit['rpe']
                forensic_risks.setdefault(rpe, []).append({
                    'score': hit['risk_score'],
                    'factor': f"Versatilidad Sospechosa: {hit['reason']}",
                    'type': 'VERSATILITY'
                })
        # Activation spikes similar
        return forensic_risks

    def analyze_supplier(self, supplier_name: str, supplier_data: Dict) -> RiskReport:
        risk_score = 0
        risk_factors = []
        rpe = str(supplier_data.get('rpe'))
        # Static
        if self._is_new_company(supplier_data.get('fecha_creacion_empresa')):
            risk_score += config.get('risk.new_company_score', 15)
            risk_factors.append("Empresa de reciente creación")
        # Physical hub
        addr = self.rpe_to_address.get(rpe)
        if addr:
            owner_density = self.hub_density.get(addr, 0)
            if owner_density > config.get('risk.hub_density_high', 20):
                risk_score += config.get('risk.hub_high_score', 40)
                risk_factors.append(f"Hub Alta Densidad: {owner_density} propietarios")
            elif owner_density > config.get('risk.hub_density_medium', 5):
                risk_score += config.get('risk.hub_medium_score', 20)
                risk_factors.append(f"Hub compartido: {owner_density}")
        # Forensics
        for risk in self.forensic_risks.get(rpe, []):
            risk_score += risk['score']
            risk_factors.append(risk['factor'])
        # Network
        network_risk = self._calculate_network_risk(rpe)
        risk_score += network_risk['points']
        risk_factors.extend(network_risk['factors'])

        # PEP & Conflict of Interest (Data Lake Check)
        pep_data = self._check_pep_status(rpe)
        if pep_data['is_pep']:
            risk_score += pep_data['points']
            risk_factors.extend(pep_data['factors'])

        # Payroll Conflict (Active Verification)
        payroll_data = self._check_payroll_status(rpe)
        if payroll_data['is_official']:
            risk_score += 60 # Critical Base Score for Conflict
            risk_factors.extend(payroll_data['factors'])

        # Intel
        intel = self._get_deep_intelligence(supplier_name)
        risk_score += intel['points']
        risk_factors.extend(intel['factors'])

        # Multipliers (Non-Linear Scoring)
        multiplier = 1.0
        if payroll_data['is_official'] and pep_data['is_pep']:
            multiplier = 1.5
            risk_factors.append("ALERTA MÁXIMA: Funcionario Activo + PEP + Proveedor.")
        
        if payroll_data['is_official'] and intel['veracity'] > 2:
            multiplier = 1.3
            risk_factors.append("ALERTA ALTA: Funcionario Activo con Noticias Negativas.")

        risk_score = min(risk_score * multiplier, 100)
        risk_level = self._get_risk_level(risk_score)
        
        return RiskReport(
            entity=supplier_name,
            rpe=rpe,
            address=addr,
            risk_score=risk_score,
            risk_level=risk_level,
            factors=list(set(risk_factors)),
            evidence={
                'forensics': self.forensic_risks.get(rpe, []),
                'physical_hub': {'address': addr, 'unique_owner_count': owner_density if addr else 0},
                'pep': pep_data['details'] if pep_data['is_pep'] else None,
                'payroll': payroll_data['details'] if payroll_data['is_official'] else None
            }
        )

    def _check_pep_status(self, rpe: str) -> Dict:
        """Check if any representative of the company is a PEP or Omiso."""
        is_pep = False
        points = 0
        factors = []
        details = []
        
        person_ids = self.company_to_people.get(rpe, [])
        if not person_ids:
            return {"is_pep": False, "points": 0, "factors": [], "details": []}

        # Attempt to load PEP data (DB or JSON)
        pep_registry = self._load_pep_data()
        
        for pid in person_ids:
            person = self.persons.get(pid)
            if not person: continue
            
            norm_name = person['name'].strip().upper()
            
            # Match in registry
            pep_match = pep_registry.get(norm_name)
            if pep_match:
                is_pep = True
                status = pep_match['status']
                inst = pep_match['institution']
                pos = pep_match['position']
                
                if status == 'OMISO':
                    points += 50
                    factors.append(f"ALERTA CRÍTICA: Representante {person['name']} es FUNCIONARIO OMISO (No declaró patrimonio) en {inst}.")
                else:
                    points += 20
                    factors.append(f"PEP Detectado: Representante {person['name']} ocupa el cargo de {pos} en {inst}.")
                
                details.append(pep_match)

        return {
            "is_pep": is_pep,
            "points": min(points, 80),
            "factors": factors,
            "details": details
        }

    def _check_payroll_status(self, rpe: str) -> Dict:
        """Check if shareholders are active public officials."""
        is_official = False
        points = 0
        factors = []
        details = []
        
        person_ids = self.company_to_people.get(rpe, [])
        if not person_ids:
            return {"is_official": False, "points": 0, "factors": [], "details": []}

        # Load payroll registry (DB or JSON)
        payroll_registry = self._load_payroll_data()
        
        for pid in person_ids:
            person = self.persons.get(pid)
            if not person: continue
            
            norm_name = person['name'].strip().upper()
            
            # Check match
            official = payroll_registry.get(norm_name)
            if official:
                is_official = True
                factors.append(f"CONFLICTO DE INTERÉS: Representante {person['name']} figura en nómina de {official['institution']} como {official['position']}.")
                details.append(official)
                
        return {
            "is_official": is_official,
            "points": 50 if is_official else 0,
            "factors": factors,
            "details": details
        }

    def _load_payroll_data(self) -> Dict:
        """Load active payroll data from DB or JSON."""
        registry = {}
        # 1. DB
        try:
            self.pg.connect()
            cur = self.pg.conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM public_officials;")
            rows = cur.fetchall()
            cur.close()
            if rows:
                return {r['full_name']: r for r in rows}
        except:
            pass
        
        # 2. JSON Fallback
        try:
            dump_file = Path("data/raw/public_officials_dump.json")
            if dump_file.exists():
                with open(dump_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {item['full_name']: item for item in data}
        except Exception as e:
            logger.warning(f"Failed to load payroll fallback: {e}")
            
        return registry

    def _check_payroll_status(self, rpe: str) -> Dict:
        """Check if any representative is an active Public Official."""
        is_official = False
        points = 0
        factors = []
        details = []
        
        person_ids = self.company_to_people.get(rpe, [])
        if not person_ids:
            return {"is_official": False, "points": 0, "factors": [], "details": []}

        # Load payroll registry
        payroll_registry = self._load_payroll_data()
        
        for pid in person_ids:
            person = self.persons.get(pid)
            if not person: continue
            
            norm_name = person['name'].strip().upper()
            
            official = payroll_registry.get(norm_name)
            if official:
                is_official = True
                factors.append(f"CONFLICTO DE INTERÉS: Representante {person['name']} es Funcionario en {official['institution']} ({official['position']}).")
                details.append(official)
                
        return {
            "is_official": is_official,
            "points": 0, # Points added in main logic
            "factors": factors,
            "details": details
        }

    def _load_payroll_data(self) -> Dict:
        """Load active payroll data from DB or JSON."""
        registry = {}
        # 1. DB
        try:
            self.pg.connect()
            cur = self.pg.conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM public_officials;")
            rows = cur.fetchall()
            cur.close()
            if rows:
                return {r['full_name']: r for r in rows}
        except:
            pass
        
        # 2. JSON Fallback
        try:
            dump_file = Path("data/raw/public_officials_dump.json")
            if dump_file.exists():
                with open(dump_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {item['full_name']: item for item in data}
        except Exception as e:
            logger.warning(f"Failed to load payroll fallback: {e}")
            
        return registry

    def _load_pep_data(self) -> Dict:
        """Helper to load PEP data from DB or local JSON fallback."""
        registry = {}
        # 1. Try DB
        try:
            self.pg.connect()
            cur = self.pg.conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM pep_registry;")
            rows = cur.fetchall()
            cur.close()
            if rows:
                return {r['normalized_name']: r for r in rows}
        except:
            pass

        # 2. Try JSON Fallback
        pep_files = list(Path("data/raw/ccrd").glob("pep_extraction_*.json"))
        if pep_files:
            latest_file = max(pep_files, key=os.path.getctime)
            import json
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {item['normalized_name']: item for item in data}
            except:
                pass
        
        return registry

    # Other methods similar, using config thresholds

    def _is_new_company(self, date_str: str) -> bool:
        if not date_str:
            return False
        years = config.get('risk.new_company_years', ['2024-', '2025-', '2026-'])
        return any(year in str(date_str) for year in years)

    def _get_risk_level(self, score: int) -> str:
        thresholds = config.get('risk.thresholds', {'critical': 75, 'high': 50, 'medium': 25})
        if score >= thresholds['critical']:
            return "CRITICAL"
        if score >= thresholds['high']:
            return "HIGH"
        if score >= thresholds['medium']:
            return "MEDIUM"
        return "LOW"

    def _calculate_network_risk(self, rpe: str) -> Dict:
        points = 0
        factors = []
        details = []
        person_ids = self.company_to_people.get(rpe, [])
        
        for pid in person_ids:
            # Check for concentration risk
            linked_companies = self.person_to_companies.get(pid, set())
            if len(linked_companies) > 3: 
                weight = min(len(linked_companies) * 8, 30)
                points += weight
                p_name = self.persons.get(pid, {}).get('name', 'Unknown')
                factors.append(f"Representante en múltiples empresas ({len(linked_companies)}): {p_name}")
                details.append({"type": "CONCENTRATION_RISK", "person": p_name, "count": len(linked_companies)})
                
        return {
            "points": min(points, 75),
            "factors": list(set(factors)), 
            "details": details
        }

    def batch_analyze(self, limit: int = 10):
        """Analyzes a batch of suppliers and saves results."""
        logger.info(f"Starting batch analysis (limit={limit})...")
        proveedores = data_manager.load_latest('proveedores_full_*.json')
        if not proveedores:
            logger.error("No suppliers found for batch analysis.")
            return

        results = []
        for supplier in proveedores[:limit]:
            report = self.analyze_supplier(supplier.get('razon_social', 'Unknown'), supplier)
            results.append(report.dict())
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"data/risk_report_batch_{timestamp}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Batch analysis complete. Report saved to {output_file}")
        return results



if __name__ == "__main__":
    service = RiskService()
    # Test
    proveedores = data_manager.load_latest('proveedores_full_*.json')
    if proveedores:
        supplier = proveedores[0]
        report = service.analyze_supplier(supplier.get('razon_social', 'Unknown'), supplier)
        print(json.dumps(report.dict(), indent=2))
