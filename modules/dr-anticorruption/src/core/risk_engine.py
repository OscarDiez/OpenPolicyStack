import logging
import json
import glob
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
from core.external.news_client import NewsClient
from core.external.social_client import SocialClient
from core.external.social_scraper import SocialScraper

# Configure logger
logger = logging.getLogger("RiskEngine")

class RiskEngine:
    def __init__(self):
        self.news_client = NewsClient()
        self.social_scraper = SocialScraper()
        self.cache = {} 
        
        # Internal Data Graph
        self.persons = {}        
        self.relationships = []  
        self.company_to_people = {} 
        self.person_to_companies = {} 
        self.rm_to_companies = {} 
        self.legal_hits = {}
        self.rpe_to_address = {}

        # Load the graph
        self._load_internal_data()

    def _load_internal_data(self):
        """Discover and load entity data, legal hits, and physical address clusters."""
        try:
            p_files = glob.glob("data/persons_*.json")
            r_files = glob.glob("data/relationships_*.json")
            l_files = glob.glob("data/legal_social_hits_*.json")
            
            # Load basic graph
            if p_files and r_files:
                latest_p = max(p_files, key=os.path.getmtime)
                latest_r = max(r_files, key=os.path.getmtime)
                with open(latest_p, 'r', encoding='utf-8') as f:
                    persons_list = json.load(f)
                    self.persons = {p['person_id']: p for p in persons_list}
                with open(latest_r, 'r', encoding='utf-8') as f:
                    self.relationships = json.load(f)
                
                # 1. Identity & Relationship Index
                for rel in self.relationships:
                    rpe = str(rel['rpe'])
                    pid = rel['person_id']
                    if rpe not in self.company_to_people: self.company_to_people[rpe] = []
                    self.company_to_people[rpe].append(pid)
                    if pid not in self.person_to_companies: self.person_to_companies[pid] = set()
                    self.person_to_companies[pid].add(rpe)

            # 2. Advanced Physical & Owner Cluster Brain
            self.hub_density = {} # address -> count of UNIQUE owners
            try:
                # Map RPE to its owners first
                rpe_to_owner_count = {}
                for rel in self.relationships:
                    rpe = str(rel['rpe'])
                    if rpe not in rpe_to_owner_count: rpe_to_owner_count[rpe] = set()
                    rpe_to_owner_count[rpe].add(rel['person_id'])

                # Use full registry to map addresses to unique owners
                latest_full = max(glob.glob("data/proveedores_full_*.json"), key=os.path.getmtime)
                with open(latest_full, 'r', encoding='utf-8') as f:
                    reg_data = json.load(f)
                    for s in reg_data.get('payload', {}).get('content', []):
                        rpe = str(s.get('rpe'))
                        addr = (s.get('direccion') or "").strip().upper()
                        if len(addr) > 10:
                            self.rpe_to_address[rpe] = addr
                            owners = rpe_to_owner_count.get(rpe, set())
                            if addr not in self.hub_density: self.hub_density[addr] = set()
                            self.hub_density[addr].update(owners)
                            
                # Convert sets to counts for faster lookups
                self.hub_density = {k: len(v) for k, v in self.hub_density.items()}
                logger.info(f"Physical Brain: Identified {len([h for h in self.hub_density.values() if h > 2])} High-Density Hubs.")
            except: logger.warning("Could not build physical-owner hub index.")

            # 3. Load Forensic signals (Versatility & Activation)
            self.forensic_risks = {}
            
            # Versatility
            if os.path.exists("data/versatility_hits.json"):
                with open("data/versatility_hits.json", 'r', encoding='utf-8') as f:
                    hits = json.load(f)
                    for hit in hits:
                        self.forensic_risks[hit['rpe']] = self.forensic_risks.get(hit['rpe'], [])
                        self.forensic_risks[hit['rpe']].append({
                            'score': hit['risk_score'],
                            'factor': f"Versatilidad Sospechosa: {hit['reason']}",
                            'type': 'VERSATILITY'
                        })

            # Activation Spikes
            if os.path.exists("data/activation_spikes.json"):
                with open("data/activation_spikes.json", 'r', encoding='utf-8') as f:
                    hits = json.load(f)
                    for hit in hits:
                        # Assuming structure: {'rpe': ..., 'spike_in_30d': ..., 'concentration': ...}
                        score = 40 if hit['concentration'] > 80 else 20
                        reason = f"Activación Súbita: {hit['spike_in_30d']} contratos en 30 días ({hit['concentration']}% del total)"
                        self.forensic_risks[hit['rpe']] = self.forensic_risks.get(hit['rpe'], [])
                        self.forensic_risks[hit['rpe']].append({
                            'score': score,
                            'factor': reason,
                            'type': 'ACTIVATION_SPIKE'
                        })

        except Exception as e:
            logger.error(f"Error loading internal data: {e}")

    def analyze_supplier(self, supplier_name: str, supplier_data: Dict) -> Dict:
        """
        Comprehensive forensic analysis including Physical, Social, and Transactional layers.
        """
        risk_score = 0
        risk_factors = []
        rpe = str(supplier_data.get('rpe'))
        
        # 1. Internal/Static
        if self._is_new_company(supplier_data.get('fecha_creacion_empresa')):
            risk_score += 15
            risk_factors.append("Empresa de reciente creación (Riesgo de maletín)")

        # 2. Physical Hub Forensics (Density of Owners)
        addr = self.rpe_to_address.get(rpe)
        if addr:
            owner_density = self.hub_density.get(addr, 0)
            if owner_density > 20:
                risk_score += 40
                risk_factors.append(f"Hub de Alta Densidad: {owner_density} propietarios únicos registrados aquí (Riesgo de Camuflaje)")
            elif owner_density > 5:
                risk_score += 20
                risk_factors.append(f"Hub compartido identificada: {owner_density} propietarios en este bloque")
        else:
            owner_density = 0

        # 3. Transactional Forensics (Versatility & Activation)
        if rpe in self.forensic_risks:
            for risk in self.forensic_risks[rpe]:
                risk_score += risk['score']
                risk_factors.append(risk['factor'])

        # 4. Network Analysis (Graph)
        network_risk = self._calculate_network_risk(rpe)
        risk_score += network_risk['points']
        risk_factors.extend(network_risk['factors'])

        # 5. Intelligence (News/Social)
        # Only run deep int if risk is already moderate to save API calls
        veracity = 0 
        news_intelligence = {'hits': []}
        
        # Always run basic news check if we have data
        if risk_score > 20 or self.news_client: # Only if we have client
             news_intelligence = self._get_deep_intelligence(supplier_name)
             risk_score += news_intelligence['points']
             risk_factors.extend(news_intelligence['factors'])
             veracity = max(network_risk.get('max_veracity', 0), news_intelligence.get('veracity', 0))

        if owner_density > 10: veracity = max(veracity, 3) 

        return {
            "entity": supplier_name,
            "rpe": rpe,
            "address": addr,
            "risk_score": min(risk_score, 100),
            "risk_level": self._get_risk_level(risk_score),
            "veracity_rank": veracity, 
            "factors": list(set(risk_factors)),
            "evidence": {
                "news": news_intelligence['hits'],
                "forensics": self.forensic_risks.get(rpe, []),
                "physical_hub": {"address": addr, "unique_owner_count": owner_density}
            }
        }

    def _get_deep_intelligence(self, name: str) -> Dict:
        """Fetch news and calculate veracity across multiple tiers."""
        points = 0
        factors = []
        
        # Tier 1: Local Media & Legal
        hits = self.news_client.search_entity(name)
        
        # Tier 2: Social Activity
        social_mentions = self.social_scraper.get_social_intelligence(name)
        
        veracity = 0
        is_giant_match = False
        
        # Scoring Tier 1
        if hits:
            total_news_risk = 0
            for h in hits:
                h_title = h['title'].lower()
                h_score = h['risk_score']
                
                # Check for DR Investigative Giants (Nuria, Alicia Ortega, etc.)
                for giant in ["nuria", "alicia ortega", "acento", "sin"]:
                    if giant in h_title:
                        h_score += 50 # Massive boost
                        veracity = 5
                        is_giant_match = True
                        factors.append(f"Investigación de alto perfil detectada ({giant.upper()})")
                
                total_news_risk += h_score
            
            points += min(total_news_risk, 60)
            factors.append(f"Menciones en prensa dominicana ({len(hits)} artículos)")
            if veracity < 3: veracity = 3
            
        # Scoring Tier 2
        if social_mentions:
            total_social_risk = 10
            for s in social_mentions:
                s_title = s['title'].lower()
                # Check for Whistleblowers
                for wb in ["somos pueblo", "tolentino", "cavada", "espresate"]:
                    if wb in s_title:
                        total_social_risk += 15
                        if veracity < 3: veracity = 3
                        factors.append(f"Alerta de denunciante social detectada ({wb.upper()})")
            
            points += min(total_social_risk, 30)
            factors.append(f"Actividad en redes sociales ({len(social_mentions)} posts)")
            if veracity < 1: veracity = 1

        return {
            "points": points,
            "factors": list(set(factors)),
            "hits": hits + social_mentions,
            "veracity": veracity
        }

    def _calculate_network_risk(self, rpe: str) -> Dict:
        points = 0
        factors = []
        details = []
        person_ids = self.company_to_people.get(rpe, [])
        
        for pid in person_ids:
            person = self.persons.get(pid)
            if not person: continue
            p_name = person['name']
            
            # Legal Association (The Strongest Signal)
            if p_name in self.legal_hits:
                hits = self.legal_hits[p_name]
                points += 50 
                factors.append(f"Vínculo con investigaciones: {p_name}")
                details.append({"type": "LEGAL_HIT", "person": p_name, "hits": hits})

            # Concentration
            linked_companies = self.person_to_companies.get(pid, set())
            if len(linked_companies) > 3: 
                weight = min(len(linked_companies) * 8, 30)
                points += weight
                factors.append(f"Representante en múltiples empresas ({len(linked_companies)}): {p_name}")
                details.append({"type": "CONCENTRATION_RISK", "person": p_name, "count": len(linked_companies)})
                
        return {
            "points": min(points, 75),
            "factors": list(set(factors)), 
            "details": details
        }

    def _is_new_company(self, date_str: str) -> bool:
        if not date_str: return False
        return any(year in str(date_str) for year in ["2024-", "2025-", "2026-"])

    def _get_risk_level(self, score: int) -> str:
        if score >= 75: return "CRITICAL"
        if score >= 50: return "HIGH"
        if score >= 25: return "MEDIUM"
        return "LOW"

    def _get_news_intelligence(self, name: str) -> List[Dict]:
        """Fetch news with caching to avoid API overuse."""
        if name in self.cache:
            return self.cache[name]
            
        hits = self.news_client.search_entity(name)
        risky_hits = [h for h in hits if h['risk_score'] > 0]
        self.cache[name] = risky_hits
        return risky_hits

    def _is_new_company(self, date_str: str) -> bool:
        """Check if company was created recently (e.g., 2024-2026)."""
        if not date_str:
            return False
        return any(year in str(date_str) for year in ["2024-", "2025-", "2026-"])

    def _get_risk_level(self, score: int) -> str:
        if score >= 75: return "CRITICAL"
        if score >= 50: return "HIGH"
        if score >= 25: return "MEDIUM"
        return "LOW"

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    engine = RiskEngine()
    # Test with a known "representative" from the sample
    # Search for an RPE in the index
    if engine.company_to_people:
        test_rpe = list(engine.company_to_people.keys())[0]
        print(f"\n🔍 Testing Risk Analysis for RPE: {test_rpe}")
        # We need the full object for analyze_supplier
        report = engine.analyze_supplier("Test Entity", {"rpe": test_rpe, "fecha_creacion_empresa": "2025-01-01"})
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("No graph data to test.")
