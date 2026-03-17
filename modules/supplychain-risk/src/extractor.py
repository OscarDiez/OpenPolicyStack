#!/usr/bin/env python3
"""
Supply-Chain Intelligence Extractor
====================================
Universal extraction pipeline for quantum technology components.

Usage:
    python extractor.py --component "Helium-3"
    python extractor.py --batch --segment cryogenics
"""

import os
import json
import httpx
from bs4 import BeautifulSoup
import io
import PyPDF2
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import argparse

# Load environment variables from .env file
load_dotenv(override=True)

try:
    from .comtrade_client import ComtradeClient
except ImportError:
    from comtrade_client import ComtradeClient

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None
        print("[!] Warning: ddgs not installed. Install with: pip install ddgs")

try:
    from groq import Groq
except ImportError:
    Groq = None
    print("[!] Warning: groq not installed. Install with: pip install groq")


class SupplyChainExtractor:
    """
    Generalized extractor for supply-chain intelligence.
    Works for ANY component in the quantum technology taxonomy.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.data_dir = Path(__file__).resolve().parents[1] / "data"
        self.comtrade = ComtradeClient()
        
        if not self.groq_api_key:
            print("[!] No GROQ_API_KEY found. Set it via environment variable or pass as argument.")
            print("    Get a free key at: https://console.groq.com/keys")

    def _safe_name(self, text: str) -> str:
        import re
        s = text.lower()
        for ch in [" ", "/", "-", "\u2014", "\u2013", "(", ")", "."]:
            s = s.replace(ch, "_")
        return re.sub(r"_+", "_", s).strip("_")

    def _get_sector_dir(self, sector: str, segment: str) -> Path:
        p = self.data_dir / "sectors" / self._safe_name(sector) / self._safe_name(segment)
        p.mkdir(parents=True, exist_ok=True)
        return p

    
    def _call_groq_with_retry(self, client, model, messages, temperature=0.0):
        """
        Wrapper for Groq API calls with exponential backoff for rate limits.
        """
        import time
        max_retries = 5
        base_delay = 5
        
        for attempt in range(max_retries):
            try:
                return client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature
                )
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate limit" in err_str.lower():
                    wait_time = base_delay * (2 ** attempt)
                    print(f"    [*] Rate Limit Reached. Pausing operation for {wait_time}s to cooldown...")
                    time.sleep(wait_time)
                else:
                    raise e
        raise Exception("Max retries exceeded for Groq API")

    def update_taxonomy(self, component: str, hs_code: str, sector: str, segment: str):
        """
        Learns where to place a new component in the taxonomy using LLM.
        """
        if not self.groq_api_key or Groq is None: return

        print(f"[*] Taxonomy Learning: Deciding where '{component}' fits in the hierarchy...")
        
        # Load existing taxonomy structure (skeleton only)
        taxonomy_file = self._get_sector_dir(sector, segment) / "taxonomy.json"
        try:
            with open(taxonomy_file, "r") as f:
                tax = json.load(f)
        except FileNotFoundError:
            print(f"[!] Taxonomy file not found for sector '{sector}', segment '{segment}'. Skipping taxonomy update.")
            return
        except json.JSONDecodeError:
            print(f"[!] Error decoding taxonomy JSON for sector '{sector}', segment '{segment}'. Skipping taxonomy update.")
            return
        
        categories = [sub['name'] for sub in tax['subsystems'][0]['subsystems']]
        
        prompt = f"""You are a taxonomy classifier.
Item: "{component}"
Categories: {json.dumps(categories)}

Task: classify the Item into one of the Categories.

CRITICAL RULES:
1. Return ONLY the category name.
2. NO explanations. NO punctuation. NO "The category is...".
3. If unsure, return "Materials".

Output:"""
        try:
            client = Groq(api_key=self.groq_api_key)
            response = self._call_groq_with_retry(
                client,
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            # Clean up potential extra quotes or whitespace
            category_name = response.choices[0].message.content.strip().replace('"', '').replace("'", "").split('\n')[0]
            
            # Update the file safely
            for subsystem in tax['subsystems'][0]['subsystems']:
                if subsystem['name'].lower() == category_name.lower():
                    # Check if already exists
                    if any(c['name'].lower() == component.lower() for c in subsystem['components']):
                        print(f"[-] Component {component} already in taxonomy.")
                        return

                    new_entry = {
                        "name": component,
                        "leaf_id": f"CRYO.AUTO.{component.upper().replace(' ', '_')}",
                        "hs_code": hs_code
                    }
                    subsystem['components'].append(new_entry)
                    
                    with open(taxonomy_file, "w") as f:
                        json.dump(tax, f, indent=4)
                    print(f"[+] Taxonomy Updated: Added '{component}' to '{subsystem['name']}'")
                    return
            
            print(f"[!] Could not match '{category_name}' to existing categories.")

        except Exception as e:
            print(f"[!] Taxonomy Update failed: {e}")

    def backfill_missing_trade_data(self):
        """
        Iterate through all existing supplier files. 
        If corresponding trade data is missing, run autonomous trade discovery.
        """
        print(f"\n{'='*60}\nStarting Trade Data Backfill\n{'='*60}\n")
        
        supplier_files = list(self.suppliers_dir.glob("*_suppliers.json"))
        print(f"[*] Found {len(supplier_files)} supplier records. Checking for missing trade data...")
        
        for f in supplier_files:
            try:
                data = json.load(open(f))
                component = data.get("component")
                if not component: continue
                
                safe_name = f.stem.replace("_suppliers", "")
                trade_file = self.data_dir / "trade" / f"{safe_name}_trade_flows.json"
                
                if not trade_file.exists():
                    print(f"[+] Backfilling trade data for: {component}")
                    
                    # 1. Try to find HS Code in existing file or discover it
                    hs_code = self._lookup_hs_code_in_taxonomies(component)
                    if not hs_code:
                        hs_code = self.discover_hs_code(component)
                    
                    if hs_code:
                        # 2. Try Official API
                        api_data = self.comtrade.get_trade_data(hs_code)
                        if api_data and api_data.get("data"):
                            self.save_trade_flows(component, api_data)
                            continue
                            
                    # 3. Fallback to Estimation
                    print(f"[*] API data unavailable. Running AI Estimation for {component}...")
                    # We need some context. Quick search.
                    results = self.search_web(f"{component} global market share export import", max_results=3)
                    context = "\n".join([f"{r['title']}: {r['snippet']}" for r in results])
                    estimated = self.estimate_trade_flows_with_llm(component, context)
                    if estimated:
                        self.save_estimated_trade_flows(component, estimated)
                
                # Add a politeness delay to avoid hammering the API
                print(f"[*] Cooldown: Waiting 5s before next component...")
                import time
                time.sleep(5)
                
            except Exception as e:
                print(f"[!] Error backfilling {f.name}: {e}")

    def search_web(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """
        Search the web using DuckDuckGo.
        """
        if DDGS is None:
            return []
        
        print(f"[*] Searching: {query}")
        try:
            results = []
            with DDGS() as ddgs:
                ddgs_gen = ddgs.text(query, max_results=max_results)
                if ddgs_gen:
                    for r in ddgs_gen:
                        results.append({
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                            "url": r.get("href", "")
                        })
            
            if results:
                # Filter out likely low-quality/non-technical noise
                noise_patterns = ["linkedin.com", "pinterest.com", "tiktok.com", "facebook.com", "alibaba.com", "made-in-china.com", "youtube.com"]
                filtered = [r for r in results if not any(p in r['url'].lower() for p in noise_patterns)]
                print(f"[+] Found {len(results)} results (Filtered to {len(filtered)} technical hits)")
                return filtered
            return results
        except Exception as e:
            print(f"[!] Search error: {e}")
            return []

    def fetch_page_content(self, url: str) -> Optional[str]:
        """
        Fetch and clean textual content from a URL, supporting HTML and PDF.
        """
        print(f"[*] Fetching: {url}")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            }
            timeout = 30.0 if url.lower().endswith(".pdf") else 15.0
            
            response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "").lower()
            
            if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                print(f"[*] Parsing PDF content ({len(response.content)} bytes)")
                pdf_file = io.BytesIO(response.content)
                reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for i in range(min(30, len(reader.pages))):
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text[:35000]
            else:
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "nav", "header", "footer", "form"]):
                    tag.decompose()
                return soup.get_text(separator=" ", strip=True)[:12000]
        except Exception as e:
            print(f"[!] Fetch error: {e}")
            return None

    def _lookup_hs_code_in_taxonomies(self, component: str) -> Optional[str]:
        """
        Searches built taxonomies to find if we already know the HS code for this component.
        """
        safe_comp = self._safe_name(component)
        
        # First check if we've already extracted it (in any sector)
        for supplier_file in self.data_dir.glob("sectors/*/*/suppliers/*_suppliers.json"):
            if supplier_file.stem == f"{safe_comp}_suppliers":
                try:
                    with open(supplier_file, "r") as f:
                        data = json.load(f)
                        from_suppliers = data.get("official_trade_stats")
                        if from_suppliers and not from_suppliers.get("estimated", False) and from_suppliers.get("data"):
                            code = from_suppliers["data"][0].get("cmdCode")
                            if code: 
                                print(f"[*] Found HS code {code} in existing supplier registry.")
                                return code
                except Exception:
                    pass

                trade_file = supplier_file.parent.parent / "trade" / f"{safe_comp}_trade_flows.json"
                if trade_file.exists():
                    try:
                        with open(trade_file, "r") as f:
                            data = json.load(f)
                            if data.get("hs_code"):
                                return data["hs_code"]
                    except Exception:
                        pass
                        
        # Check taxonomies
        for tax_file in self.data_dir.glob("sectors/*/*/taxonomy.json"):
            try:
                with open(tax_file, "r") as f:
                    tax = json.load(f)
                for cat in tax.get("subsystems", []):
                    for sub in cat.get("subsystems", []):
                        for comp in sub.get("components", []):
                            if comp.get("name", "").lower() == component.lower() and comp.get("hs_code"):
                                print(f"[*] Found HS code {comp['hs_code']} in taxonomy.")
                                return comp["hs_code"]
            except Exception:
                continue
        return None

    def discover_hs_code(self, component: str) -> Optional[str]:
        """
        Autonomous Discovery: Uses LLM + Web Search to find the 6-digit HS Code for any component.
        """
        if not self.groq_api_key or Groq is None:
            return None

        print(f"[*] Autonomous Discovery: Finding HS Code for '{component}'...")
        
        # 1. Search for the HS Code
        search_results = self.search_web(f"{component} 6-digit HS code Harmonized System code global", max_results=5)
        context = "\n".join([f"{r['title']}: {r['snippet']}" for r in search_results])
        
        # 2. Ask LLM to extract the most likely 6-digit code
        prompt = f"""You are a global trade and customs expert.
Component: {component}

CONTEXT:
{context}

GOAL: Identify the standard 6-digit Harmonized System (HS) code that best matches this component for international trade.
Rules:
1. Return ONLY the 6-digit numeric code (e.g., 854411).
2. If uncertain, return the most likely parent category code.
3. If totally unknown, return "UNKNOWN".

RETURN ONLY THE CODE OR "UNKNOWN". No explanation.
"""
        try:
            client = Groq(api_key=self.groq_api_key)
            response = self._call_groq_with_retry(
                client,
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            code = response.choices[0].message.content.strip()
            # Clean non-numeric characters if any
            import re
            numeric_code = re.sub(r"\D", "", code)
            if len(numeric_code) >= 6:
                final_code = numeric_code[:6]
                print(f"[+] Discovered HS Code: {final_code}")
                return final_code
            print(f"[!] Could not reliably discover HS code for {component}")
            return None
        except Exception as e:
            print(f"[!] HS Discovery error: {e}")
            return None

    def extract_entities_with_llm(self, component: str, search_results: List[Dict[str, str]], deep_dive: bool = False) -> List[Dict[str, Any]]:
        """
        Use Groq's Llama 3.3 70B to extract structured supplier data.
        """
        if not self.groq_api_key or Groq is None:
            return []
        
        context_blocks = []
        for r in search_results[:5]:
            block = f"Source: {r['title']}\nSnippet: {r['snippet']}\nURL: {r['url']}"
            if deep_dive:
                full_text = self.fetch_page_content(r['url'])
                if full_text:
                    block += f"\nFull Content (Truncated): {full_text[:8000]}"
            context_blocks.append(block)
        
        context = "\n\n---\n\n".join(context_blocks)
        prompt = f"""You are a senior supply-chain intelligence analyst and industrial physicist.
Component: {component}

GOAL: Extract a detailed database of entities (COMPANIES, STATE AGENCIES, CONSORTIUMS, SPECIALIZED DISTRIBUTORS).

HYPER-PRECISION RULES:
1. **NEVER Generalize**: Do not use words like 'thousands', 'many', or 'most' if a specific number is available.
2. **GLOBAL INDUSTRY TOTALS**: Record global figures as "GLOBAL_INDUSTRY_TOTAL".
3. **STRICT UNIT VALIDATION**: A unit must be a physical measurement.
4. **COMPREHENSIVE DISCOVERY**: Extract EVERY company mentioned that plays a role in production, enrichment, specialized distribution, or supply-chain logistics for this component. Specialized gas leaders and industrial isotope providers (e.g., specialists in isotopic enrichment or rare gas supply) are high priority.
5. **Context Analysis**: Analyze the context below from multiple sources.

INSTRUCTIONS:
1. Extract entity name, country, and role.
2. For production_volume, you MUST return a JSON object. If a number is found, return it.
3. INTRICACY UPGRADE: Search deep for:
   - Technical Capacity: Identify specific hardware naming (e.g., 'Boson 4 chip'), technical modalities (e.g., 'Cat Qubits'), and engineering metrics.
   - Financials: Capture total funding, latest round (e.g., 'Series B Jan 2025'), and lead investors.
   - Ecosystem: List strategic partnerships (e.g., 'Bluefors', 'Quantum Machines') and government programs (e.g., 'PROQCIMA').
   - Leadership: Identify founders and key executives.

SCHEMA: 
```json
{{
  "name": "string",
  "country": "string",
  "role": "string",
  "production_volume": {{"value": float or null, "unit": "string or null", "year": int or null, "source": "string or null"}},
  "technical_capacity": {{
    "specs": ["specific hardware/versions", "performance metrics"],
    "modality": "string (e.g. Cat Qubit)"
  }},
  "financials": {{
    "total_funding": "string or null",
    "last_round": "string or null",
    "lead_investors": ["string"]
  }},
  "ecosystem": {{
    "partnerships": ["string"],
    "programs": ["string"]
  }},
  "leadership": {{
    "founders": ["string"],
    "key_people": ["string"]
  }},
  "strategic_notes": "string"
}}
```

SEARCH RESULTS/CONTEXT:
{{context}}

RETURN ONLY A VALID JSON ARRAY. No chat.
"""
        try:
            client = Groq(api_key=self.groq_api_key)
            print(f"[*] Calling LLM (llama-3.3-70b-versatile) for extraction...")
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": "You are a precise JSON extraction assistant."},
                              {"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=2000
                )
            except Exception as e:
                if "429" in str(e) or "413" in str(e):
                    print(f"[!] Rate/Size limit hit. Sampling context and falling back to llama-3.1-8b-instant...")
                    # Smart sampling: take head and tail to preserve both top results and totals
                    if len(context) > 15000:
                        short_context = context[:7500] + "\n[...]\n" + context[-7500:]
                    else:
                        short_context = context
                    small_prompt = prompt.replace(context, short_context)
                    response = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "system", "content": "You are a precise JSON extraction assistant."},
                                  {"role": "user", "content": small_prompt}],
                        temperature=0.1,
                        max_tokens=2000
                    )
                else:
                    raise e

            raw_output = response.choices[0].message.content.strip()
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                raw_output = raw_output.split("```")[1].split("```")[0].strip()
            entities = json.loads(raw_output)
            # Ensure structure
            for ent in entities:
                if "production_volume" not in ent or not isinstance(ent["production_volume"], dict):
                    ent["production_volume"] = {"value": None, "unit": None, "year": None, "source": None}
            return entities
        except Exception as e:
            print(f"[!] LLM extraction error: {e}")
            return []

    def refine_entity_data(self, entity: Dict[str, Any], component: str, context: str) -> Dict[str, Any]:
        """
        Refine a single entity's data using targeted context.
        """
        prompt = f"""Update the data for '{entity['name']}' regarding '{component}'.
Search the context below for EXACT numerical values (capacity, output, share).

HYPER-PRECISION RULE:
- Record exact numbers (e.g. 8200) only.
- If not found, do not guess.
- SCHEMA MUST MATCH: 
```json
{{
  "name": "string",
  "country": "string",
  "role": "string",
  "production_volume": {{"value": float or null, "unit": "string or null", "year": int or null, "source": "string or null"}},
  "technical_capacity": {{"specs": [str], "modality": str}},
  "financials": {{"total_funding": str, "last_round": str, "lead_investors": [str]}},
  "ecosystem": {{"partnerships": [str], "programs": [str]}},
  "leadership": {{"founders": [str], "key_people": [str]}},
  "strategic_notes": "string"
}}
```

CONTEXT:
{{context}}

RETURN the updated JSON for THIS ENTITY ONLY.
"""
        try:
            client = Groq(api_key=self.groq_api_key)
            try:
                response = self._call_groq_with_retry(
                    client,
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": "You are a precise data analyst. Return only valid JSON for the entity."},
                              {"role": "user", "content": prompt}],
                    temperature=0.0
                )
            except Exception as e:
                # Fallback logic for context length is handled here manually or we could just let retry handle 429
                # But for 413 (too large), we need truncation.
                if "429" in str(e) or "413" in str(e) or "rate limit" in str(e).lower():
                    print(f"    [!] Context limit or rate limit hit. Truncating context...")
                    short_context = context[:4000]
                    small_prompt = prompt.replace(context, short_context)
                    response = self._call_groq_with_retry(
                        client,
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "system", "content": "You are a precise data analyst. Return only valid JSON for the entity."},
                                  {"role": "user", "content": small_prompt}],
                        temperature=0.0
                    )
                else:
                    raise e
                    
            raw_output = response.choices[0].message.content.strip()
            if not raw_output:
                print(f"[!] Refinement returned empty string for {entity['name']}")
                return entity
                
            if "```json" in raw_output:
                raw_output = raw_output.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_output:
                raw_output = raw_output.split("```")[1].split("```")[0].strip()
            
            try:
                return json.loads(raw_output)
            except Exception as e:
                print(f"[!] Refinement JSON error: {e}")
                print(f"    Raw Output: {raw_output[:200]}...")
                return entity
        except Exception as e:
            print(f"[!] Refinement API error: {e}")
            return entity


    def estimate_trade_flows_with_llm(self, component: str, context: str) -> Dict[str, Any]:
        """
        Fallback: Use LLM to estimate trade flows if API fails.
        """
        print(f"[*] Autonomous Fallback: Estimating trade flows via LLM for '{component}'...")
        
        prompt = f"""You are a global trade analyst.
Component: {component}

CONTEXT from Search:
{context}

GOAL: Estimate the global market structure for this component based on the context and general knowledge.
1. Estimate the Total Global Market Value (in USD).
2. List the Top 5 Exporter Countries with their ESTIMATED market share (0.0 to 1.0).
3. List the Top 5 Importer Countries.

RETURN JSON ONLY:
{{
  "year": 2024,
  "commodity": "{component}",
  "global_trade_value": float (estimated USD),
  "exporters": [ {{"country": str, "share": float}}, ... ],
  "importers": [ {{"country": str, "share": float}}, ... ],
  "sources": ["AI-Estimated based on search context"]
}}
"""
        try:
            client = Groq(api_key=self.groq_api_key)
            response = self._call_groq_with_retry(
                client,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "Return valid JSON only."},
                          {"role": "user", "content": prompt}],
                temperature=0.2
            )
            raw = response.choices[0].message.content.strip()
            if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw: raw = raw.split("```")[1].split("```")[0].strip()
            
            data = json.loads(raw)
            # Ensure value is present for consistency
            if "global_trade_value" in data:
                val = data["global_trade_value"]
                for e in data.get("exporters", []):
                    if "value" not in e: e["value"] = val * e.get("share", 0)
                for i in data.get("importers", []):
                    if "value" not in i: i["value"] = val * i.get("share", 0)
            
            return data
        except Exception as e:
            print(f"[!] LLM Trade Estimation failed: {e}")
            return None

    def save_estimated_trade_flows(self, component: str, data: Dict[str, Any], sector: str, segment: str):
        trade_dir = self._get_sector_dir(sector, segment) / "trade"
        trade_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_name(component)
        output_path = trade_dir / f"{safe_name}_trade_flows.json"
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[+] Saved ESTIMATED trade flows to: {output_path}")

    def save_trade_flows(self, component: str, api_data: Dict[str, Any], sector: str, segment: str):
        """
        Converts Comtrade API results into a standardized trade flow JSON.
        """
        trade_dir = self._get_sector_dir(sector, segment) / "trade"
        trade_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_name(component)
        output_path = trade_dir / f"{safe_name}_trade_flows.json"
        
        data_records = api_data.get("data", [])
        if not data_records: return
        
        # Organize by year and country
        # We'll take the most recent year's data
        latest_year = max([r.get("period") for r in data_records if r.get("period")])
        year_data = [r for r in data_records if r.get("period") == latest_year]
        
        exporters = []
        importers = []
        global_value = 0
        
        for r in year_data:
            flow = r.get("flowCode")
            country = r.get("reporterDesc")
            value = r.get("primaryValue", 0)
            
            if flow == "X": # Export
                exporters.append({"country": country, "value": value})
                global_value += value
            elif flow == "M": # Import
                importers.append({"country": country, "value": value})

        # Calculate shares
        for e in exporters: e["share"] = round(e["value"] / global_value, 4) if global_value > 0 else 0
        for i in importers: i["share"] = round(i["value"] / global_value, 4) if global_value > 0 else 0
        
        # Sort by value
        exporters = sorted(exporters, key=lambda x: x["value"], reverse=True)
        importers = sorted(importers, key=lambda x: x["value"], reverse=True)

        flow_data = {
            "year": latest_year,
            "commodity": component,
            "unit": "USD",
            "global_trade_value": global_value,
            "exporters": exporters[:10],
            "importers": importers[:10],
            "sources": ["UN Comtrade API (Automated)"]
        }
        
        with open(output_path, "w") as f:
            json.dump(flow_data, f, indent=2)
        print(f"[+] Saved trade flows to: {output_path}")

    def save_suppliers(self, component: str, entities: List[Dict[str, Any]], search_query: str, sector: str, segment: str, sources: List[str], api_data: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        suppliers_dir = self._get_sector_dir(sector, segment) / "suppliers"
        suppliers_dir.mkdir(parents=True, exist_ok=True)
        safe_component = self._safe_name(component)
        filename = f"{safe_component}_suppliers.json"
        output_path = suppliers_dir / filename
        
        output_data = {
            "component": component,
            "extraction_metadata": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "search_query": search_query,
                "llm_model": "llama-3.3-70b-versatile",
                "entity_count": len(entities),
                "has_api_data": api_data is not None
            },
            "sources": sources,
            "official_trade_stats": api_data,
            "suppliers": entities
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"[+] Saved to: {output_path}")
        return output_path

    def extract_component(self, component: str, sector: str, segment: str, deep_dive: bool = False, hs_code: Optional[str] = None) -> Optional[Path]:
        print(f"\n{'='*60}\nExtracting: {component} {'(DEEP DIVE)' if deep_dive else ''}\n{'='*60}\n")
        
        # --- STAGE 1: Autonomous HS Discovery & Trade Data ---
        if hs_code is None:
            hs_code = self._lookup_hs_code_in_taxonomies(component)
            if not hs_code:
                hs_code = self.discover_hs_code(component)
                # If we discovered a new code, let's learn it!
                if hs_code:
                    self.update_taxonomy(component, hs_code, sector, segment)
            
        api_data = None
        if hs_code:
            print(f"[*] Querying Official API (UN Comtrade) for HS Code: {hs_code}")
            api_data = self.comtrade.get_trade_data(hs_code)
            
            
            # If we got trade data, let's cache it as a trade flow file for the risk engine
            if api_data and api_data.get("data"):
                self.save_trade_flows(component, api_data, sector, segment)
            else:
                api_data = None # Reset if empty
        
        # --- STAGE 2: Web Extraction ---
        
        # Diverse search queries for better coverage
        queries = [
            f"{component} best producers manufacturers list 2024",
            f"{component} top suppliers companies global market share",
            f"{component} industrial production volume by company"
        ]
        
        all_results = []
        for q in queries:
            print(f"[*] Searching: {q}")
            results = self.search_web(q, max_results=5)
            all_results.extend(results)
            
        # Deduplicate results by URL
        seen_urls = set()
        unique_results = []
        for r in all_results:
            url = r.get('href') or r.get('link') or r.get('url')
            if url and url not in seen_urls:
                unique_results.append(r)
                seen_urls.add(url)
        
        print(f"[+] Found {len(unique_results)} unique results")
        
        # If API failed, use the search context to estimate trade flows
        if not api_data:
            context = "\n".join([f"{r['title']}: {r['snippet']}" for r in unique_results[:10]])
            estimated_trade = self.estimate_trade_flows_with_llm(component, context)
            if estimated_trade:
                self.save_estimated_trade_flows(component, estimated_trade, sector, segment)
                # We treat this as "official" enough for the risk engine
                api_data = {"estimated": True, "data": estimated_trade}

        # Extract entities using LLM
        print(f"[*] Calling LLM (llama-3.3-70b-versatile) for extraction...")
        entities = self.extract_entities_with_llm(component, unique_results, deep_dive=deep_dive)
        
        # Use first query for metadata
        search_query = queries[0]
        
        if not entities:
            print("[!] No entities extracted.")
            return None
            
        if deep_dive:
            print("\n[*] Performing recursive entity deep-dive for top entities...")
            refined_entities = []
            for entity in entities:
                # Targeted search for production volume if it's a Producer
                role = str(entity.get("role", "")).lower()
                if "producer" in role or "agency" in role or "facility" in role:
                    name = entity.get('name', 'Unknown')
                    print(f"[*] Statistical Deep-Dive for: {name}")
                    # Specific unit-aware query
                    comp_query = f"\"{name}\" {component} production volume statistics liters grams kg per year 2023 2024"
                    comp_results = self.search_web(comp_query, max_results=3)
                    
                    company_context = ""
                    for cr in comp_results:
                        text = self.fetch_page_content(cr['url'])
                        if text:
                            company_context += f"\nSource: {cr['url']}\nContent: {text[:15000]}\n"
                    
                    if company_context:
                        # Refine the entity
                        refined = self.refine_entity_data(entity, component, company_context)
                        refined_entities.append(refined)
                    else:
                        refined_entities.append(entity)
                else:
                    refined_entities.append(entity)
            entities = refined_entities
            
        source_urls = [r.get('href') or r.get('link') or r.get('url') for r in unique_results]
        source_urls = [u for u in source_urls if u]
            
        return self.save_suppliers(component, entities, search_query, sector, segment, source_urls, api_data=api_data)

    def batch_extract_from_taxonomy(self, segment: str, sector: str, deep_dive: bool = False):
        taxonomy_file = self._get_sector_dir(sector, segment) / "taxonomy.json"
        if not taxonomy_file.exists():
            return
        
        with open(taxonomy_file, "r") as f:
            taxonomy = json.load(f)
        
        components = []
        for category in taxonomy.get("subsystems", []):
            for sub in category.get("subsystems", []):
                for comp in sub.get("components", []):
                    components.append({"name": comp.get("name"), "hs_code": comp.get("hs_code")})
        
        for i, comp_info in enumerate(components, 1):
            print(f"\n[{i}/{len(components)}] Processing: {comp_info['name']}")
            self.extract_component(comp_info['name'], sector, segment, deep_dive=deep_dive, hs_code=comp_info['hs_code'])


    def generate_taxonomy_with_llm(self, sector: str, segment: str) -> Dict[str, Any]:
        """
        Uses the LLM to propose a structured component taxonomy for any sector+segment.
        Returns a dict following the same schema as cryogenics_taxonomy.json.
        Falls back to built-in sector taxonomies if no API key is available.
        """
        # ── Built-in fallback taxonomies (used when no Groq API key) ──────────
        BUILTIN_TAXONOMIES: Dict[str, Any] = {
            "quantum computing": {
                "dilution refrigeration": {"Cooling System": ["Mixing Chamber", "Still Stage", "Cold Plate Assembly", "Pulse Tube Cryocooler", "Compressor Unit"], "Cryogenic Plumbing": ["Helium-3 Gas Handling System", "Helium-4 Pressurized Vessel", "Fill Line Assembly", "Check Valve Set", "Pressure Gauge Array"]},
                "cryogenics": {"Core Cooling": ["Dilution Refrigerator", "Pulse Tube Cryocooler", "Mixing Chamber", "Still Flange", "He-3/He-4 Mixture"], "Cryostat Hardware": ["Radiation Shield", "Vacuum Can", "Cold Finger Assembly", "Vibration Isolator Mount", "Thermal Anchor"]},
                "superconducting qubits": {"Qubit Chipset": ["Transmon Qubit Die", "Josephson Junction Array", "Qubit Substrate (Sapphire)", "Superconducting Resonator", "Qubit Wiring Interposer"], "Control Electronics": ["Arbitrary Waveform Generator", "IQ Mixer", "RF Attenuator Chain", "Circulators and Isolators", "HEMT Amplifier"]},
                "default": {"Processing Unit": ["Qubit Processor", "Control FPGA", "RF Signal Generator", "Microwave Switch Matrix", "Error Correction ASIC"], "Infrastructure": ["Dilution Refrigerator", "Vibration Isolation Platform", "Coaxial Cable Harness", "Magnetic Shielding Enclosure", "UPS Power Supply"]},
            },
            "artificial intelligence": {
                "gpu hardware": {"GPU Chipset": ["NVIDIA H100 SXM", "AMD Instinct MI300X", "Google TPU v5", "Intel Gaudi3 AI Accelerator", "Graphcore IPU"], "Memory": ["HBM3 Stack", "GDDR7 Module", "High-Bandwidth Memory Die", "On-Package SRAM", "NVLink Switch Chip"]},
                "ai infrastructure": {"Compute": ["GPU Server Node", "AI Training Cluster Switch", "High-Speed Interconnect NIC", "NVMe SSD Array", "Liquid Cooling Module"], "Networking": ["InfiniBand 400G Switch", "OSFP Optical Transceiver", "Direct-Attach Copper Cable", "Fiber Patch Panel", "Network Time Server"]},
                "default": {"AI Compute Hardware": ["H100 GPU", "TPU Accelerator", "FPGA Inference Card", "AI ASIC Chip", "High-Bandwidth Memory (HBM)"], "Data Center": ["Liquid Cooling System", "High-Speed Interconnect", "NVMe Storage Array", "Power Distribution Unit", "Rack Enclosure"]},
            },
            "semiconductors": {
                "default": {"Wafer Fabrication": ["Silicon Wafer (300mm)", "EUV Photomask", "Photoresist Chemical", "Chemical Mechanical Planarization Slurry", "Bulk Silicon Ingot"], "Lithography Equipment": ["ASML EUV Scanner (NXE:3600D)", "Immersion DUV Lithography System", "Electron Beam Writer", "Metrology SEM", "Spin Coater"], "Process Gases": ["Ultra-High Purity Nitrogen", "Argon Process Gas", "Hydrogen Fluoride Etch Gas", "Tungsten Hexafluoride", "Silane (SiH4)"], "Packaging": ["Advanced Flip-Chip Package", "High-Density Fan-Out Wafer Level Package", "2.5D Interposer", "Copper Pillar Bumping", "Underfill Epoxy"]},
                "memory": {"DRAM": ["DDR5 DRAM Die", "High-Bandwidth Memory (HBM3)", "LPDDR5 Mobile DRAM", "DRAM Module PCB", "Error-Correcting DIMM"], "NAND Flash": ["3D NAND Flash Die (QLC)", "NAND Controller ASIC", "NVMe SSD Enclosure", "Flash Translation Layer Firmware", "NAND Interface Driver"]},
            },
            "aerospace": {
                "propulsion": {"Rocket Engines": ["Turbopump Assembly", "Thrust Chamber", "Nozzle Extension", "Igniter System", "Propellant Valve"], "Propellants": ["Liquid Oxygen (LOX)", "Liquid Hydrogen (LH2)", "RP-1 Kerosene", "Hydrazine Monopropellant", "Ammonium Perchlorate Oxidizer"]},
                "default": {"Airframe Structures": ["Carbon Fibre Reinforced Polymer Panel", "Titanium Structural Frame", "Aluminium 7075 Alloy Sheet", "Fastener Set (Aerospace Grade)", "Honeycomb Core Sandwich Panel"], "Avionics": ["Flight Management Computer", "Inertial Navigation System", "GPS/GNSS Receiver Module", "Digital Air Data Computer", "ARINC 429 Data Bus Module"], "Propulsion": ["Turbofan Engine Core", "Combustion Chamber Liner", "Fan Blade (Ti alloy)", "Engine Control Unit", "Thrust Reverser Assembly"]},
            },
            "defence": {
                "default": {"Electronics": ["Military-Grade FPGA (Radiation Hardened)", "EO/IR Sensor Array", "Secure Communications Module", "Electronic Warfare Jammer Module", "GPS Anti-Jam Receiver"], "Propulsion & Munitions": ["Solid Rocket Motor", "Explosive Warhead Component", "Guidance System IMU", "Fin Stabilizer Assembly", "Propellant Grain"], "Platforms": ["Armour Steel Plate (MIL-DTL-12560)", "Composite Hull Panel", "Military Vehicle Engine Assembly", "Night Vision Optics", "Tactical Radio Set"]},
            },
            "pharmaceuticals": {
                "default": {"Active Pharmaceutical Ingredients": ["Paracetamol API", "Ibuprofen API", "Amoxicillin API", "Aspirin API", "Metformin API"], "Excipients": ["Microcrystalline Cellulose", "Lactose Monohydrate", "Magnesium Stearate", "Polyvinyl Pyrrolidone (PVP)", "Croscarmellose Sodium"], "Manufacturing Equipment": ["Fluid Bed Dryer", "High-Shear Granulator", "Tablet Press", "Blister Packaging Machine", "Autoclave Sterilizer"]},
            },
        }

        def _make_taxonomy(sector_str, segment_str, groups: Dict[str, list]) -> Dict[str, Any]:
            subsystems = []
            for group_name, components in groups.items():
                subsystems.append({
                    "name": group_name,
                    "components": [{"name": c, "leaf_id": f"{sector_str[:3].upper()}.{group_name[:3].upper()}.{c[:6].upper().replace(' ', '_')}"} for c in components]
                })
            return {
                "technology_domain": sector_str,
                "segment": segment_str,
                "subsystems": [{"name": segment_str, "subsystems": subsystems}]
            }

        def _get_builtin(sector_str: str, segment_str: str) -> Optional[Dict[str, Any]]:
            sector_key = sector_str.lower().strip()
            segment_key = segment_str.lower().strip()
            # Find best matching sector key
            for s_key, s_data in BUILTIN_TAXONOMIES.items():
                if s_key in sector_key or any(w in sector_key for w in s_key.split()):
                    # Find best matching segment
                    for seg_key, groups in s_data.items():
                        if seg_key != "default" and (seg_key in segment_key or any(w in segment_key for w in seg_key.split())):
                            return _make_taxonomy(sector_str, segment_str, groups)
                    # Use default
                    if "default" in s_data:
                        return _make_taxonomy(sector_str, segment_str, s_data["default"])
            return None

        if not self.groq_api_key or Groq is None:
            builtin = _get_builtin(sector, segment)
            if builtin:
                print(f"[*] Using built-in taxonomy for '{sector}' / '{segment}' (no Groq API key)")
                return builtin
            # Generic fallback
            return _make_taxonomy(sector, segment, {
                "Key Components": [f"{segment} Primary Component", f"{segment} Secondary Component", f"{segment} Supporting Material"],
                "Supporting Infrastructure": [f"{segment} Processing Equipment", f"{segment} Quality Control System", f"{segment} Storage & Handling"]
            })

        print(f"[*] LLM Taxonomy Generation: '{sector}' → '{segment}'...")

        prompt = f"""You are a senior supply-chain intelligence analyst. A user wants to map the supply chain for the following:
Industry Sector: {sector}
Segment / Sub-domain: {segment}

Your task is to generate a structured component taxonomy for this exact segment.

RULES:
1. Return ONLY a valid JSON object, no explanation text.
2. Group components into 3-6 logical subsystems.
3. Each subsystem should have 3-8 leaf components.
4. Components should be SPECIFIC and REAL items that can be sourced/traded (not vague categories).
5. Use the exact JSON schema below.

JSON SCHEMA:
{{
  "technology_domain": "{sector}",
  "segment": "{segment}",
  "subsystems": [
    {{
      "name": "Top-level Assembly Name",
      "subsystems": [
        {{
          "name": "Subsystem Group Name",
          "components": [
            {{
              "name": "Specific Component Name",
              "leaf_id": "ABBR.GROUP.COMPONENT_NAME"
            }}
          ]
        }}
      ]
    }}
  ]
}}

RETURN ONLY THE JSON. NO EXPLANATION.
"""
        try:
            client = Groq(api_key=self.groq_api_key)
            response = self._call_groq_with_retry(
                client,
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a precise JSON generation assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            raw = response.choices[0].message.content.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            return json.loads(raw)
        except Exception as e:
            print(f"[!] Taxonomy generation failed: {e}. Falling back to built-in taxonomy.")
            builtin = _get_builtin(sector, segment)
            if builtin:
                return builtin
            return _make_taxonomy(sector, segment, {
                "Key Components": [f"{segment} Primary Component", f"{segment} Secondary Component", f"{segment} Supporting Material"],
                "Supporting Infrastructure": [f"{segment} Processing Equipment", f"{segment} Quality Control System", f"{segment} Storage & Handling"]
            })


    def save_taxonomy(self, taxonomy_dict: Dict[str, Any], segment_name: str, sector_str: str) -> Path:
        """
        Persists a user-approved taxonomy to data/sectors/{sector}/{segment}/taxonomy.json
        """
        sector_dir = self._get_sector_dir(sector_str, segment_name)
        output_path = sector_dir / "taxonomy.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(taxonomy_dict, f, indent=4, ensure_ascii=False)
        print(f"[+] Taxonomy saved to: {output_path}")
        
        # Ensure dependencies are mapped correctly
        self.update_dependency_graph(sector_str, segment_name, taxonomy_dict)
        
        return output_path

    def update_dependency_graph(self, sector: str, segment: str, taxonomy: Dict[str, Any]):
        """Uses LLM to map relationships between the components in the taxonomy and writes dependencies.json."""
        sector_dir = self._get_sector_dir(sector, segment)
        dep_path = sector_dir / "dependencies.json"
        
        components = []
        for cat in taxonomy.get("subsystems", []):
            for sub in cat.get("subsystems", []):
                for comp in sub.get("components", []):
                    components.append(comp.get("name"))
                    
        prompt = f"""You are a supply chain analyst mapping the bill of materials for {segment} in {sector}.
I have the following components: {', '.join(components)}.

Identify the parent-child relationships between these components. Which components depend on which others? 
Create a dependency graph. If a component is a top-level component, its parent is "{segment}".

Return ONLY valid JSON matching this exact schema:
{{
  "dependencies": [
    {{
      "parent": "Component Name",
      "children": ["Dependent Sub-component 1", "Dependent Sub-component 2"]
    }}
  ]
}}
NO EXPLANATION. ONLY JSON."""

        if not self.groq_api_key or Groq is None:
            # Fallback to a flat structure
            deps = [{"parent": segment, "children": components}]
            with open(dep_path, "w") as f:
                json.dump({"dependencies": deps}, f, indent=2)
            return

        print(f"[*] Autonomous Discovery: Mapping supply chain dependencies for {segment}...")
        try:
            client = Groq(api_key=self.groq_api_key)
            response = self._call_groq_with_retry(
                client,
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You output only valid JSON. No text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            raw = response.choices[0].message.content.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            deps = json.loads(raw)
            if "dependencies" not in deps: deps = {"dependencies": []}
            with open(dep_path, "w", encoding="utf-8") as f:
                json.dump(deps, f, indent=2)
            print(f"[+] Dependency graph automatically routed and saved to: {dep_path}")
        except Exception as e:
            print(f"[!] Dependency graph generation failed: {e}. Falling back to flat structure.")
            deps = [{"parent": segment, "children": components}]
            with open(dep_path, "w") as f:
                json.dump({"dependencies": deps}, f, indent=2)



def main():

    parser = argparse.ArgumentParser(description="Supply-Chain Intelligence Extractor")
    parser.add_argument("--component", type=str, help="Single component to extract")
    parser.add_argument("--batch", action="store_true", help="Batch process a segment")
    parser.add_argument("--sector", type=str, default="quantum_computing", help="Sector name")
    parser.add_argument("--segment", type=str, default="cryogenics", help="Segment name")
    parser.add_argument("--deep-dive", action="store_true", help="Deep scraping")
    parser.add_argument("--hs-code", type=str, help="Manual HS code override")
    parser.add_argument("--groq-key", type=str, help="Groq API key")
    
    args = parser.parse_args()
    extractor = SupplyChainExtractor(groq_api_key=args.groq_key)
    
    if args.batch and args.segment and args.sector:
        extractor.batch_extract_from_taxonomy(args.segment, args.sector, deep_dive=args.deep_dive)
    elif args.component and args.sector and args.segment:
        extractor.extract_component(args.component, args.sector, args.segment, deep_dive=args.deep_dive, hs_code=args.hs_code)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
