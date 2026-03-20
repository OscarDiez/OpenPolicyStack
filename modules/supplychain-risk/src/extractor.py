#!/usr/bin/env python3
"""
Supply-Chain Intelligence Extractor
=====================================
Implements the data collection hierarchy from the methodology:

  Priority 1 — UN Comtrade API (official trade statistics, most reliable)
  Priority 2 — Web extraction: DuckDuckGo + BeautifulSoup/PyPDF2 + LLM (70B)
  Priority 3 — LLM-estimated trade shares (last resort, clearly labelled)

All sources are tracked and included in every output file.
Taxonomy generation goes all the way down to raw earth materials.

Key improvements:
- Ownership tracking: who OWNS facilities, not just where they are
- Unbiased global supplier search — no geographic preference baked in
- Quantum computing-specific relevance validation
- Exhaustiveness enforcement with loud failure reporting
- CRM-aware: He-3, NbTiN, Si-28, In, Nb, Ge, Ga, GaAs, InP focus
"""

import os
import json
import time
import re
import datetime
import io
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import httpx

# Load .env immediately — before any os.getenv() calls or provider checks
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
print(f"[env] LLM_PROVIDER={os.getenv('LLM_PROVIDER','groq')} OPENAI_KEY={'set' if os.getenv('OPENAI_API_KEY') else 'MISSING'} GROQ_KEY={'set' if os.getenv('GROQ_API_KEY') else 'MISSING'}")

# LLM provider is selected via LLM_PROVIDER env var: "groq" (default) or "openai"
_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower().strip()

# Human-readable label stamped into data_source fields so outputs always reflect
# which model actually produced the estimate.
_MODEL_LABEL = "GPT-4o mini (OpenAI)" if _PROVIDER == "openai" else "Llama 3.3 70B (Groq)"

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from openai import OpenAI
except Exception as _e:
    print(f"[!] openai import failed: {_e}")
    OpenAI = None

if _PROVIDER == "openai" and OpenAI is None:
    raise RuntimeError("LLM_PROVIDER=openai but 'openai' failed to import. Check the error above.")
if _PROVIDER == "groq" and Groq is None:
    raise RuntimeError("LLM_PROVIDER=groq but 'groq' failed to import. Run: pip install groq")

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# ─── Models ───────────────────────────────────────────────────────────────────
# Groq models
GROQ_MODEL_QUALITY = "llama-3.3-70b-versatile"
GROQ_MODEL_FAST    = "llama-3.1-8b-instant"

# OpenAI models
OPENAI_MODEL_QUALITY = "gpt-4o-mini"    # universally available, strong quality
OPENAI_MODEL_FAST    = "gpt-4o-mini"    # same — no reason to downgrade with OpenAI pricing

# Legacy aliases (used in old code paths)
MODEL_QUALITY = GROQ_MODEL_QUALITY
MODEL_FAST    = GROQ_MODEL_FAST

# ─── CRM Knowledge Base (from PDF review) ─────────────────────────────────────
# Critical Raw Materials for Quantum Technology — semi-manufactured goods are
# the true chokepoints, not raw elements.  China controls >50% refining for 9/20.
QT_CRITICAL_MATERIALS = {
    "He-3":   "Helium-3 isotope — produced as byproduct of tritium decay in nuclear reactors; US and Russia only significant sources",
    "NbTiN":  "Niobium-titanium nitride — superconducting thin film; <5 fabs worldwide capable of QC-grade deposition",
    "Si-28":  "Isotopically enriched silicon-28 — requires centrifuge enrichment; Russia (URENCO-RU) dominates",
    "Ge-73":  "Germanium-73 isotope — requires isotope separation; niche market controlled by Russia/Germany",
    "Rb-87":  "Rubidium-87 — cold atom/Rydberg qubits; Sigma-Aldrich/Merck + specialty isotope labs",
    "InP":    "Indium phosphide wafers — III-V semiconductor for photonic qubits; In supply from China >60%",
    "GaAs":   "Gallium arsenide wafers — Ga refining >80% Chinese controlled",
    "NbTi":   "Niobium-titanium wire — superconducting wire for magnets; Bruker EAS, Luvata, Furukawa",
    "Nb":     "Niobium metal — 90% from Brazil (CBMM) but Chinese firms hold equity stakes in CBMM",
    "In":     "Indium — >60% refined in China; critical for InP and ITO",
    "Ga":     "Gallium — >80% refined in China; export controls tightened 2023",
    "Ge":     "Germanium — China export controls from 2023; dual-use restriction",
    "OFHC":   "Oxygen-free high-conductivity copper — thermal anchor material; Aurubis, KME, Wieland",
}

# ─── Ownership Intelligence ────────────────────────────────────────────────────
# Known cases where geographic location ≠ beneficial owner
KNOWN_OWNERSHIP_ALERTS = {
    "niobium": "CBMM (Brazil) is nominally Brazilian but Chinese consortium (CITIC, Taiyuan, etc.) holds ~15% equity. Companhia Brasileira de Metalurgia e Mineração (CBMM) — note partial Chinese ownership.",
    "gallium": "Most gallium refining is in China. Even where non-Chinese plants exist, upstream germanium/gallium concentrate often sourced from Chinese smelters.",
    "germanium": "China imposed export controls on Ge in August 2023. Umicore (Belgium) refines Ge but depends on Chinese concentrate supply.",
    "helium-3": "He-3 in the US is managed by DOE/Isotek; Russian supply through FSUE Isotope. Both are state-controlled — ownership IS the state.",
    "indium": "Indium refining: China >60%, South Korea ~15%, Japan ~10%. Korean/Japanese refiners often import Chinese concentrate.",
}


class SupplyChainExtractor:

    def __init__(self, groq_api_key: Optional[str] = None):
        # ── provider selection ────────────────────────────────────────────────
        # Set LLM_PROVIDER=openai in your .env to use OpenAI instead of Groq.
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()

        self.groq_api_key  = groq_api_key or os.getenv("GROQ_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.comtrade_key  = os.getenv("COMTRADE_API_KEY")
        self.data_dir      = Path(__file__).resolve().parents[1] / "data"

        # Groq rate-limit tracking (not needed for OpenAI)
        self._rate_limit_hits = 0
        self._use_fast_model  = False

        if self.provider == "openai":
            if not self.openai_api_key:
                print("[!] LLM_PROVIDER=openai but OPENAI_API_KEY not set — LLM calls will fail.")
            else:
                print(f"[i] LLM provider: OpenAI ({OPENAI_MODEL_QUALITY})")
        else:
            if not self.groq_api_key:
                print("[!] GROQ_API_KEY not set — LLM calls will fail.")
            else:
                print(f"[i] LLM provider: Groq ({GROQ_MODEL_QUALITY})")

    # ──────────────────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────────────────

    def _safe_name(self, text: str) -> str:
        s = text.lower()
        s = re.sub(r'\(.*?\)', '', s)
        for ch in [" ", "/", "-", "(", ")", ".", ",", "'"]:
            s = s.replace(ch, "_")
        return re.sub(r"_+", "_", s).strip("_")

    def _get_sector_dir(self, sector: str, segment: str) -> Path:
        p = self.data_dir / "sectors" / self._safe_name(sector) / self._safe_name(segment)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _llm_call(self, prompt: str, model: str, max_tokens: int) -> str:
        """Raw single LLM call — dispatches to the correct provider."""
        if self.provider == "openai":
            client = OpenAI(api_key=self.openai_api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        else:
            client = Groq(api_key=self.groq_api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()

    def _llm(self, prompt: str, model: str = MODEL_QUALITY, max_retries: int = 3, max_tokens: int = 4096) -> str:
        """Robust LLM call with exponential back-off.
        - OpenAI: waits on rate limits, never downgrades model.
        - Groq: after 3 cumulative rate-limit hits on the quality model,
          permanently switches to the fast model for the rest of the run.
        """
        if self.provider == "openai":
            quality_model = OPENAI_MODEL_QUALITY
            current_model = quality_model
        else:
            quality_model = GROQ_MODEL_QUALITY
            fast_model    = GROQ_MODEL_FAST
            if self._use_fast_model and model == GROQ_MODEL_QUALITY:
                model = fast_model
            current_model = model

        for attempt in range(max_retries):
            try:
                return self._llm_call(prompt, current_model, max_tokens)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "rate_limit" in err_str or "429" in err_str or "rate limit" in err_str

                # Groq: fall back to fast model after repeated rate limits
                if self.provider == "groq" and is_rate_limit and current_model == GROQ_MODEL_QUALITY:
                    self._rate_limit_hits += 1
                    if self._rate_limit_hits >= 3:
                        self._use_fast_model = True
                        print(f"[!] {self._rate_limit_hits} rate limit hits — permanently switching to {GROQ_MODEL_FAST} for this run.")
                    else:
                        print(f"[!] Rate limit on {GROQ_MODEL_QUALITY} (hit {self._rate_limit_hits}/3) — falling back to {GROQ_MODEL_FAST} for this call.")
                    current_model = GROQ_MODEL_FAST
                    continue

                if attempt < max_retries - 1:
                    wait = 20 * (attempt + 1)
                    print(f"[!] LLM failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s…")
                    time.sleep(wait)
                else:
                    raise

    def _llm_quality_only(self, prompt: str, max_tokens: int = 8000, max_retries: int = 5) -> str:
        """Always uses the quality model. On rate limit, waits and retries — never downgrades."""
        if self.provider == "openai":
            quality_model = OPENAI_MODEL_QUALITY
        else:
            quality_model = GROQ_MODEL_QUALITY

        for attempt in range(max_retries):
            try:
                return self._llm_call(prompt, quality_model, max_tokens)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "rate_limit" in err_str or "429" in err_str or "rate limit" in err_str
                if is_rate_limit:
                    wait = 60 if attempt == 0 else 90 * attempt
                    print(f"[!] Rate limit on {quality_model}. Waiting {wait}s before retry {attempt + 1}/{max_retries}…")
                    time.sleep(wait)
                elif attempt < max_retries - 1:
                    wait = 20 * (attempt + 1)
                    print(f"[!] LLM error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s…")
                    time.sleep(wait)
                else:
                    raise

    def _parse_json(self, raw: str) -> Any:
        """Robust JSON extraction from LLM response — handles markdown fences and plain JSON."""
        raw = raw.strip()
        try:
            return json.loads(raw)
        except Exception:
            pass
        for pattern in [r'```json\s*([\s\S]*?)```', r'```\s*([\s\S]*?)```']:
            m = re.search(pattern, raw)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except Exception:
                    pass
        for start, end in [('{', '}'), ('[', ']')]:
            i = raw.find(start)
            j = raw.rfind(end)
            if i != -1 and j > i:
                try:
                    return json.loads(raw[i:j + 1])
                except Exception:
                    pass
        raise ValueError(f"Could not parse JSON from LLM response:\n{raw[:300]}")

    # ──────────────────────────────────────────────────────────────────────────
    # Taxonomy Generation
    # ──────────────────────────────────────────────────────────────────────────

    def generate_taxonomy_with_llm(self, sector: str, segment: str) -> Dict[str, Any]:
        """
        Generate a DEEP, POLICY-GRADE bill-of-materials taxonomy.
        Two-pass: generate then deepen/validate.
        Scrapes actual web pages for richer context.
        """
        print(f"[*] Generating deep taxonomy: {sector} → {segment}")

        # ── Step 1: Rich web context (scrape, not just snippets) ──────────────
        seed_queries = [
            f"{segment} {sector} bill of materials full component list",
            f"{segment} quantum computing supply chain critical materials raw inputs 2024",
            f"{segment} quantum technology components manufacturers upstream materials",
            f"{segment} dilution refrigerator OR qubit OR superconducting full parts list",
            f"site:arxiv.org OR site:nature.com {segment} quantum computing supply chain components",
        ]
        sources: List[str] = []
        context_parts: List[str] = []

        for q in seed_queries:
            results = self.search_web(q, max_results=6)
            for r in results:
                url = r.get("url", "")
                snippet = f"[{url}]\n{r['title']}: {r['snippet']}"
                context_parts.append(snippet)
                if url:
                    sources.append(url)
            time.sleep(1)

        # Scrape top 4 URLs for full page content
        scraped_context = ""
        for url in sources[:4]:
            scraped = self._scrape_url(url, timeout=12)
            if scraped:
                scraped_context += f"\n\n=== FULL PAGE: {url} ===\n{scraped[:2500]}"

        search_context = "\n".join(context_parts[:20])
        full_context   = search_context + scraped_context

        # Inject CRM knowledge
        crm_note = "\n".join(f"  - {k}: {v}" for k, v in QT_CRITICAL_MATERIALS.items())

        prefix = segment[:3].upper()

        # ── Step 2: First-pass taxonomy generation ────────────────────────────
        print("[*] Pass 1: generating taxonomy skeleton…")

        prompt_1 = f"""You are a senior supply-chain engineer and critical-materials analyst advising the European Commission on strategic technology dependencies. You are mapping the FULL upstream supply chain for the "{segment}" segment of {sector}.

YOUR SINGLE MOST IMPORTANT RULE:
Every branch MUST drill all the way down to a RAW or REFINED MATERIAL — the actual substance that gets mined, refined, or synthesised and traded internationally. A "fiber optic cable" or "magnet" is NOT a leaf. Germanium dioxide, neodymium oxide, hafnium tetrachloride — THESE are leaves.

═══════════════════════════════════════════════════════════════
STRUCTURE (mandatory — follow exactly)
═══════════════════════════════════════════════════════════════

Level 1 = Functional subsystem (e.g. "Light Source", "Waveguide", "Detector")
Level 2 = Sub-assembly or component (e.g. "Laser Diode", "Optical Fiber")
Level 3 = Material input to that component (e.g. "Germanium-doped silica preform")
Level 4 = Raw/refined material — THIS IS THE LEAF (e.g. "Germanium Dioxide (GeO2)")

EVERY branch must end at Level 4 (a raw/refined material with a leaf_id).
NO branch may end at Level 1, 2, or 3.
NO exceptions.

═══════════════════════════════════════════════════════════════
WHAT COUNTS AS A VALID LEAF (raw/refined material)
═══════════════════════════════════════════════════════════════

✅ VALID leaves (what we want):
• Elements and refined metals: Germanium, Indium, Gallium, Hafnium, Niobium, Tantalum, Ruthenium
• Chemical compounds: Germanium Dioxide, Indium Phosphide, Hafnium Oxide, Trimethylindium
• Isotopes: Helium-3, Silicon-28, Germanium-73
• Specialty refined materials: High-purity silicon wafer, OFHC copper, NbTi superconducting wire
• Specialty gases: Arsine (AsH3), Phosphine (PH3), Silane (SiH4), Nitrogen trifluoride

❌ INVALID leaves (do NOT use as leaves — drill deeper):
• "Fiber optic cable" → drill to: silica preform → germanium dioxide + silicon dioxide
• "Laser diode" → drill to: InP substrate → indium + phosphorus
• "Magnet" → drill to: neodymium-iron-boron alloy → neodymium oxide + iron + boron
• "Superconducting wire" → drill to: niobium-titanium alloy → niobium + titanium
• "PCB" → drill to: copper foil + FR4 substrate + solder (tin-silver-copper)
• "Sensor" → drill to: the active material (e.g. ruthenium oxide, germanium crystal)
• ANY manufactured component — always drill one level deeper to the material

═══════════════════════════════════════════════════════════════
CRITICAL RAW MATERIALS TO LOOK FOR (include if relevant)
═══════════════════════════════════════════════════════════════
{crm_note}

═══════════════════════════════════════════════════════════════
QUALITY RULES
═══════════════════════════════════════════════════════════════
• Minimum 40 leaf nodes across the whole tree
• leaf_id format: {prefix}-001, {prefix}-002 … (sequential, no gaps)
• Node names: CLEAN chemical/material names only — no country, supplier, or company names
• NO vague nodes: "Other materials", "Miscellaneous", "Various"
• NO invented compounds — only real substances used in real {segment} fabrication
• NO duplicates — if a material appears in multiple branches, give each instance its own leaf_id

WEB RESEARCH CONTEXT:
{full_context[:5000]}

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT — return ONLY valid JSON, no explanation, no markdown:
═══════════════════════════════════════════════════════════════
{{
  "technology_domain": "{sector}",
  "segment": "{segment}",
  "sources": {json.dumps(list(dict.fromkeys(sources))[:8])},
  "supply_chain": [
    {{
      "name": "Functional Subsystem",
      "children": [
        {{
          "name": "Component or Sub-assembly",
          "children": [
            {{
              "name": "Material Input",
              "children": [
                {{
                  "name": "Germanium Dioxide",
                  "leaf_id": "{prefix}-001"
                }},
                {{
                  "name": "Silicon Dioxide",
                  "leaf_id": "{prefix}-002"
                }}
              ]
            }}
          ]
        }}
      ]
    }}
  ]
}}"""

        try:
            # Taxonomy MUST use the quality model — wait out rate limits rather than fall back to 8B
            raw      = self._llm_quality_only(prompt_1, max_tokens=8000)
            taxonomy = self._parse_json(raw)
        except Exception as e:
            print(f"[!] Pass 1 taxonomy generation failed: {e}")
            taxonomy = {"technology_domain": sector, "segment": segment, "sources": sources[:6], "supply_chain": []}

        taxonomy.setdefault("technology_domain", sector)
        taxonomy.setdefault("segment", segment)
        taxonomy.setdefault("sources", sources[:6])
        taxonomy.setdefault("supply_chain", [])

        n_leaves = self._count_leaves(taxonomy.get("supply_chain", []))
        print(f"[+] Pass 1 complete — {n_leaves} leaf components.")

        # ── Step 3: Second pass — deepen and fill gaps ────────────────────────
        if n_leaves < 35:
            print(f"[*] Pass 2: only {n_leaves} leaves found, deepening taxonomy…")

            existing_json = json.dumps(taxonomy, indent=2)

            # Find highest existing leaf_id number
            all_ids = re.findall(rf'{prefix}-(\d+)', existing_json)
            next_id = max((int(x) for x in all_ids), default=0) + 1

            # For pass 2, use quality model if available; keep fast model if already fallen back
            p2_model  = MODEL_FAST if self._use_fast_model else MODEL_QUALITY
            p2_tokens = 4000 if p2_model == MODEL_FAST else 8000

            # Only include existing tree if it's not empty (no point sending empty skeleton)
            tree_context = (
                f"CURRENT TAXONOMY (expand this):\n{existing_json[:3000]}"
                if n_leaves > 0
                else f"The previous attempt produced no leaves. Start fresh for {segment} ({sector})."
            )

            prompt_2 = f"""You are expanding a supply-chain taxonomy for "{segment}" ({sector}) for EU policy analysis.
Target: at least 40 leaf nodes. Current count: {n_leaves}.

{tree_context}

YOUR MOST IMPORTANT RULE: Every leaf node must be a RAW or REFINED MATERIAL — the actual substance traded internationally (e.g. Germanium Dioxide, Indium, Niobium, Hafnium Oxide, Arsine gas). Never leave a branch ending at a component or assembly — always drill to the material.

Add missing branches. New leaf_ids start at {prefix}-{next_id:03d}.

Check for gaps — and for each, drill to the raw material:
- Electrical connectors → copper, gold, tin-silver solder
- Sealing materials → indium wire, fluoroelastomer, nitrile rubber
- Thermal management → OFHC copper, aluminum alloy, silver paste
- Control electronics → silicon wafer, tantalum capacitors, gold wire bonds
- Structural alloys → specific grade (e.g. Ti-6Al-4V, SS-316L, Al-6061)
- Specialty gases → arsine, phosphine, silane, nitrogen trifluoride
- Dopants → boron, phosphorus, arsenic (semiconductor grade)

Node names must be clean chemical/material names only — no country, supplier, or company names.

Return the COMPLETE improved taxonomy as valid JSON only:
{{
  "technology_domain": "{sector}",
  "segment": "{segment}",
  "sources": {json.dumps(taxonomy.get('sources', []))},
  "supply_chain": [ ... ]
}}"""

            try:
                raw2      = self._llm_quality_only(prompt_2, max_tokens=8000)
                taxonomy2 = self._parse_json(raw2)
                n2 = self._count_leaves(taxonomy2.get("supply_chain", []))
                if n2 > n_leaves:
                    taxonomy = taxonomy2
                    taxonomy.setdefault("technology_domain", sector)
                    taxonomy.setdefault("segment", segment)
                    print(f"[+] Pass 2 complete — {n2} leaf components (was {n_leaves}).")
                else:
                    print(f"[!] Pass 2 didn't improve count ({n2} vs {n_leaves}), keeping pass 1.")
            except Exception as e:
                print(f"[!] Pass 2 failed: {e}. Using pass 1 result.")

        n_final = self._count_leaves(taxonomy.get("supply_chain", []))
        print(f"[+] Final taxonomy: {n_final} leaf components across {len(taxonomy.get('supply_chain', []))} top-level systems.")
        return taxonomy

    def _count_leaves(self, nodes: list) -> int:
        count = 0
        for node in nodes:
            if "leaf_id" in node:
                count += 1
            count += self._count_leaves(node.get("children", []))
        return count

    def save_taxonomy(self, taxonomy: dict, segment: str, sector: str = "") -> Path:
        safe_sector  = self._safe_name(sector or taxonomy.get("technology_domain", "unknown"))
        safe_segment = self._safe_name(segment)
        path = self.data_dir / "sectors" / safe_sector / safe_segment
        path.mkdir(parents=True, exist_ok=True)
        tax_file = path / "taxonomy.json"
        with open(tax_file, "w") as f:
            json.dump(taxonomy, f, indent=2)
        print(f"[+] Taxonomy saved → {tax_file}")
        return tax_file

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 1 — UN Comtrade
    # ──────────────────────────────────────────────────────────────────────────

    def _get_hs_code(self, component: str) -> Optional[str]:
        prompt = f"""You are a trade classification expert.
What is the best 6-digit HS (Harmonised System) commodity code for "{component}" in quantum computing supply chains?
Reply with ONLY the 6-digit code (e.g. 284590), or the word NONE if no appropriate code exists."""
        try:
            result = self._llm(prompt, model=MODEL_FAST).strip().strip('"').strip("'").split()[0]
            if re.match(r'^\d{6}$', result):
                return result
        except Exception:
            pass
        return None

    def _fetch_comtrade(self, hs_code: str, component: str) -> Optional[Dict]:
        print(f"[*] Querying UN Comtrade — HS {hs_code}…")
        reporters = "842,156,276,251,392,410,826,528,752,756,246,124,036,356"
        base_url  = "https://comtradeapi.un.org/public/v1/get/C/A/HS"
        params    = {
            "cmdCode":      hs_code,
            "period":       "2022,2023",
            "flowCode":     "X",
            "reporterCode": reporters,
            "format":       "json",
        }
        if self.comtrade_key:
            base_url = "https://comtradeapi.un.org/data/v1/get/C/A/HS"
            params["subscription-key"] = self.comtrade_key
            params["reporterCode"]     = "all"

        try:
            headers  = {"User-Agent": "SupplyTrace/1.0 (EC AI-for-Policy research)"}
            response = httpx.get(base_url, params=params, headers=headers, timeout=25.0)
            if response.status_code == 200:
                records = response.json().get("data", [])
                if records:
                    print(f"[+] Comtrade: {len(records)} records.")
                    return self._process_comtrade(records, component, hs_code)
            else:
                print(f"[!] Comtrade {response.status_code}: {response.text[:120]}")
        except Exception as e:
            print(f"[!] Comtrade error: {e}")
        return None

    def _process_comtrade(self, records: list, component: str, hs_code: str) -> Optional[Dict]:
        country_totals: Dict[str, float] = {}
        total_value = 0.0
        for rec in records:
            country = rec.get("reporterDesc") or rec.get("reporterISO") or "Unknown"
            value   = float(rec.get("primaryValue") or 0)
            if value > 0:
                country_totals[country] = country_totals.get(country, 0) + value
                total_value += value

        if not country_totals or total_value == 0:
            return None

        exporters = sorted(
            [{"country": c, "share": round(v / total_value, 4), "value_usd": round(v),
              "source": "UN Comtrade Official"}
             for c, v in country_totals.items()],
            key=lambda x: x["share"], reverse=True
        )[:12]

        return {
            "commodity":       component,
            "hs_code":         hs_code,
            "year":            "2022-2023",
            "total_value_usd": round(total_value),
            "data_source":     "UN Comtrade Official",
            "exporters":       exporters,
            "importers":       [],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 2 — Web Search + LLM Extraction
    # ──────────────────────────────────────────────────────────────────────────

    def generate_search_queries(self, component: str, sector: str = "quantum computing") -> List[str]:
        """
        Generate targeted search queries for finding real industrial suppliers.
        Includes ownership/beneficial ownership queries — critical for cases
        where location ≠ controller (e.g. Brazilian niobium mines with Chinese equity).
        """
        prompt = f"""You are a supply-chain intelligence researcher for the European Commission, analysing {sector} supply chains.

Generate exactly 10 highly specific search queries to find REAL companies manufacturing or supplying "{component}".

QUERY TYPES TO COVER (one per type minimum):
1. Global manufacturers (no geographic filter)
2. Asian suppliers (China, Japan, South Korea, Taiwan specifically)
3. European/Western suppliers
4. Ownership & parent company: who OWNS the production facilities or mines
5. Chinese investment or equity stakes in non-Chinese producers
6. Trade/market intelligence reports (site:bis.gov, site:usgs.gov, site:esa.int, site:ec.europa.eu)
7. Quantum computing or cryogenic application-specific
8. Critical raw material supply chain (if applicable)
9. Industry association member lists or supplier registries
10. Academic or government report on {component} supply chain

Rules:
- Do NOT include company names in queries
- Do NOT bias toward any country — the truth matters regardless of origin
- Include boolean operators where helpful (OR, site:)
- Focus on verifiable, citeable sources

Output: one query per line, no numbering, no bullets."""
        try:
            raw     = self._llm(prompt, model=MODEL_FAST)
            queries = [l.strip() for l in raw.strip().splitlines() if len(l.strip()) > 10]
            return queries[:10]
        except Exception as e:
            print(f"[!] Query generation failed: {e}")
            return [
                f"{component} manufacturer supplier quantum computing global",
                f"{component} producer China Japan Korea Taiwan supplier",
                f"{component} European manufacturer cryogenic applications",
                f"{component} mine owner parent company China investment equity",
                f"{component} supply chain critical raw material site:usgs.gov OR site:ec.europa.eu",
                f"{component} supplier market share report producers list",
            ]

    def search_web(self, query: str, max_results: int = 8) -> List[Dict[str, str]]:
        if not DDGS:
            print("[!] DDGS not available. Install: pip install ddgs")
            return []
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title":   r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url":     r.get("href", ""),
                    })
            return results
        except Exception as e:
            print(f"[!] Search error: {e}")
            return []

    def _scrape_url(self, url: str, timeout: int = 10) -> str:
        if not url:
            return ""
        try:
            headers  = {"User-Agent": "Mozilla/5.0 (compatible; SupplyTraceResearch/1.0)"}
            response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if response.status_code != 200:
                return ""
            content_type = response.headers.get("content-type", "").lower()

            if "pdf" in content_type and PyPDF2:
                reader = PyPDF2.PdfReader(io.BytesIO(response.content))
                text   = " ".join((p.extract_text() or "") for p in reader.pages[:8])
                return text[:4000]

            if "html" in content_type and BeautifulSoup:
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                return soup.get_text(separator=" ", strip=True)[:4000]

        except Exception:
            pass
        return ""

    def _check_ownership_context(self, component: str) -> str:
        """Return any known ownership intelligence for this component from our knowledge base."""
        comp_lower = component.lower()
        for key, note in KNOWN_OWNERSHIP_ALERTS.items():
            if key in comp_lower:
                return note
        return ""

    def extract_entities_with_llm(
        self,
        component: str,
        search_results: List[Dict[str, str]],
        sector: str = "quantum computing",
    ) -> List[Dict[str, Any]]:
        """
        Extract real companies from search results using 70B model.
        Includes ownership/beneficial owner tracking.
        Scrapes the top 5 source URLs for richer content.
        NO geographic bias — truth regardless of country.
        """
        if not search_results:
            return []

        context_parts = []
        sources_used  = []

        for i, r in enumerate(search_results):
            snippet = f"[Source: {r['url']}]\nTitle: {r['title']}\n{r['snippet']}"
            # Scrape top 8 URLs for full page content (most useful ones first)
            if i < 8 and r.get("url"):
                scraped = self._scrape_url(r["url"])
                if scraped:
                    snippet += f"\n[Full page content]:\n{scraped[:2000]}"
            context_parts.append(snippet)
            if r.get("url"):
                sources_used.append(r["url"])

        context = "\n\n---\n\n".join(context_parts)

        # Inject any known ownership alerts for this component
        ownership_alert = self._check_ownership_context(component)
        ownership_note  = f"\n\nKNOWN OWNERSHIP INTELLIGENCE:\n{ownership_alert}" if ownership_alert else ""

        # Inject CRM context if relevant
        crm_context = ""
        comp_lower  = component.lower()
        for crm_key, crm_desc in QT_CRITICAL_MATERIALS.items():
            if crm_key.lower() in comp_lower or comp_lower in crm_key.lower():
                crm_context = f"\n\nCRM CONTEXT: {crm_desc}"
                break

        prompt = f"""You are a senior supply-chain intelligence analyst for the European Commission AI for Policy initiative. You are mapping {sector} supply chains for official policy briefings that will directly inform EU regulations.

COMPONENT: {component}
SECTOR: {sector}
{ownership_note}{crm_context}

TASK: From the web sources below, extract ALL real companies that manufacture, produce, or supply "{component}" for quantum computing applications.

⚠️ CRITICAL — NO GEOGRAPHIC BIAS:
You MUST identify suppliers from ALL countries including China, Russia, South Korea, Taiwan, Japan, USA, Europe, etc.
Do NOT favour Western suppliers. Do NOT omit Chinese, Russian, or Asian suppliers.
The truth is what matters — this is for EU policy that depends on accurate global intelligence.
If Chinese firms dominate supply, that MUST be reflected in your output.

⚠️ OWNERSHIP TRACKING — THIS IS MANDATORY:
For EVERY supplier, research and report:
- parent_company: the immediate parent company if different from operating entity
- ultimate_owner_country: the country of the BENEFICIAL OWNER (who ultimately controls it)
- ownership_notes: if a facility is in Country A but owned by Country B, state this explicitly
  Example: "CBMM mine is in Brazil but Chinese consortium (CITIC Metals, Taiyuan Iron) holds ~15% equity"
  Example: "Germanium refiner in Belgium but sources 100% of concentrate from Chinese smelters"

TARGET: At minimum 20 companies. Include niche, regional, and specialised producers — even small or specialized ones.
If fewer than 20 real companies exist globally for this component, explain why (market concentration note in strategic_notes).

STRICT VALIDATION:
- Only include companies you are CERTAIN exist as real legal entities
- REJECT: product codes, model numbers, URLs, generic descriptions
- REJECT: names that are not clearly a company (e.g. "Various manufacturers")
- REJECT any name you cannot confidently attribute to a real firm

FOR EACH COMPANY provide:
- name: exact legal company name
- country: country of primary operations/HQ (physical location)
- ultimate_owner_country: country of beneficial owner (may differ from HQ country)
- parent_company: parent/holding company name (null if independent)
- role: "Producer" | "Distributor" | "OEM" | "Refiner" | "Research Institution" | "State-Owned Enterprise"
- quantum_relevance: "direct" (makes QC-grade product) | "upstream" (material/precursor) | "adjacent" (general industrial)
- strategic_notes: 1–2 sentences on market position, concentration risk, ownership flags
- source_url: the URL from the sources below that confirms this company's existence
- data_confidence: "high" | "medium" | "low"

OUTPUT: JSON array only, no explanation:
[
  {{
    "name": "Company Name",
    "country": "Country",
    "ultimate_owner_country": "Country",
    "parent_company": null,
    "role": "Producer",
    "quantum_relevance": "direct",
    "strategic_notes": "Description including any ownership flags.",
    "source_url": "https://...",
    "data_confidence": "high"
  }}
]

SOURCES:
{context[:12000]}"""

        try:
            time.sleep(4)
            raw      = self._llm_quality_only(prompt, max_tokens=4096)
            entities = self._parse_json(raw)
            if not isinstance(entities, list):
                return []
            clean = []
            for e in entities:
                if not isinstance(e, dict):
                    continue
                name = (e.get("name") or "").strip()
                if len(name) < 3 or name.lower() in {"unknown", "various", "n/a", "tbd"}:
                    continue
                if re.match(r'^[A-Z0-9\-_]{2,8}$', name):
                    continue
                # Ensure ownership fields exist (even if null)
                e.setdefault("ultimate_owner_country", e.get("country", "Unknown"))
                e.setdefault("parent_company", None)
                e.setdefault("quantum_relevance", "adjacent")
                e.setdefault("source_url", sources_used[0] if sources_used else "")
                clean.append(e)
            print(f"[+] Extracted {len(clean)} companies.")
            return clean
        except Exception as e:
            print(f"[!] Entity extraction failed: {e}")
            return []

    def _enrich_ownership(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        For each extracted supplier, ask the LLM to research beneficial ownership.
        This catches cases where a company's listed country differs from who actually
        controls it (e.g. a Malaysian refiner owned by a Chinese SOE).

        Results are clearly labelled as LLM-estimated and should be verified against
        current corporate filings — ownership structures change and LLM training data
        has a cutoff date.
        """
        if not entities:
            return entities

        # Build a compact list of companies to research
        company_list = []
        for i, e in enumerate(entities):
            company_list.append(f"{i+1}. {e.get('name','?')} (listed country: {e.get('country','?')})")

        prompt = f"""You are a corporate intelligence analyst specialising in beneficial ownership and foreign equity stakes in strategic industries.

For each company below, research:
1. Who are the major shareholders or parent companies?
2. Is there any significant foreign state ownership or equity stake — especially from China, Russia, or other geopolitically sensitive actors?
3. Does the listed country of operations match the country of the beneficial owner?

Be specific where you know facts (e.g. "CITIC Metals holds 15% of CBMM").
Where you are uncertain, say so explicitly.

COMPANIES:
{chr(10).join(company_list)}

Return a JSON array with one entry per company (same order, same numbering):
[
  {{
    "index": 1,
    "beneficial_owner_country": "Country of ultimate beneficial owner",
    "parent_company": "Parent/holding company name or null",
    "ownership_detail": "Specific ownership facts or 'No significant foreign ownership identified'",
    "ownership_confidence": "high | medium | low",
    "ownership_data_note": "LLM-estimated from training data — verify against current corporate filings"
  }}
]"""

        try:
            print(f"[*] Enriching ownership data for {len(entities)} companies…")
            time.sleep(3)
            raw = self._llm_quality_only(prompt, max_tokens=3000)
            ownership_data = self._parse_json(raw)
            if not isinstance(ownership_data, list):
                return entities

            # Merge ownership data back into entities
            for item in ownership_data:
                idx = item.get("index", 0) - 1
                if 0 <= idx < len(entities):
                    entities[idx]["beneficial_owner_country"] = item.get("beneficial_owner_country", entities[idx].get("country"))
                    entities[idx]["parent_company"]          = item.get("parent_company") or entities[idx].get("parent_company")
                    entities[idx]["ownership_detail"]        = item.get("ownership_detail", "")
                    entities[idx]["ownership_confidence"]    = item.get("ownership_confidence", "low")
                    entities[idx]["ownership_data_note"]     = item.get("ownership_data_note", "LLM-estimated from training data — verify against current corporate filings")

            print(f"[+] Ownership enrichment complete.")
            return entities

        except Exception as e:
            print(f"[!] Ownership enrichment failed: {e} — continuing without it.")
            # Add the honesty label even on failure so it's always present
            for entity in entities:
                entity.setdefault("ownership_data_note", "Ownership not verified — LLM enrichment failed. Verify against current corporate filings.")
            return entities

    def _llm_fallback_suppliers(self, component: str, sector: str) -> List[Dict[str, Any]]:
        """
        Last-resort supplier extraction using pure LLM knowledge (no web context).
        Clearly labelled as AI-estimated.  Used when web search yields nothing.
        """
        print(f"[*] Attempting pure LLM knowledge fallback for '{component}'…")
        ownership_alert = self._check_ownership_context(component)
        crm_note = ""
        comp_lower = component.lower()
        for crm_key, crm_desc in QT_CRITICAL_MATERIALS.items():
            if crm_key.lower() in comp_lower or comp_lower in crm_key.lower():
                crm_note = f"\nCRM NOTE: {crm_desc}"
                break

        prompt = f"""You are a world expert in {sector} supply chains, with deep knowledge of critical materials and industrial suppliers.

COMPONENT: {component}
{crm_note}
{"OWNERSHIP NOTE: " + ownership_alert if ownership_alert else ""}

List every real company you KNOW produces or supplies "{component}" for quantum computing or related high-tech applications.
Include suppliers from ALL countries without any geographic bias.
For EACH company, also report who OWNS it (parent company / beneficial owner country) — this is critical.

If fewer than 10 companies exist globally, explain why (market concentration note).

Output JSON array:
[
  {{
    "name": "Company Name",
    "country": "Country of operations",
    "ultimate_owner_country": "Country of beneficial owner",
    "parent_company": "Parent company name or null",
    "role": "Producer",
    "quantum_relevance": "direct",
    "strategic_notes": "Key facts including ownership/concentration flags.",
    "source_url": "LLMESTIMATED",
    "data_confidence": "medium",
    "data_source": "AI-Estimated ({_MODEL_LABEL} — no web sources consulted)"
  }}
]"""
        try:
            time.sleep(8)
            raw      = self._llm_quality_only(prompt, max_tokens=4096)
            entities = self._parse_json(raw)
            if not isinstance(entities, list):
                return []
            for e in entities:
                e["data_source"]        = f"AI-Estimated ({_MODEL_LABEL} — no web sources consulted)"
                e["data_confidence"]    = "low"
                e.setdefault("ultimate_owner_country", e.get("country", "Unknown"))
                e.setdefault("parent_company", None)
                e.setdefault("quantum_relevance", "adjacent")
                e.setdefault("source_url", "LLMESTIMATED")
            clean = [e for e in entities if isinstance(e, dict) and len((e.get("name") or "")) >= 3]
            print(f"[+] LLM fallback yielded {len(clean)} companies (low confidence).")
            return clean
        except Exception as e:
            print(f"[!] LLM fallback also failed: {e}")
            return []

    def estimate_market_shares(
        self,
        component: str,
        entities: List[Dict],
        context: str,
    ) -> List[Dict]:
        """
        Ask the LLM for ACTUAL estimated market share percentages for each supplier.
        If the LLM returns a new company not in the list, it gets added.
        Falls back to Zipf distribution if LLM fails.
        """
        if not entities:
            return entities
        print(f"[*] Estimating market shares for {len(entities)} companies…")

        names = [e["name"] for e in entities]
        prompt = f"""You are a senior market intelligence analyst advising the European Commission on quantum technology supply chains.

For each company below, estimate their ACTUAL percentage share of the global market for "{component}" specifically in quantum computing / advanced technology applications.

Be specific and realistic. Use your knowledge of production capacity, reported revenues, known market positions, and industry concentration. Do NOT make all shares equal — reflect actual concentration.

If you know of important companies that are NOT in the list but are significant suppliers of "{component}", include them as additional entries at the end.

Companies to assess:
{json.dumps(names, indent=2)}

CONTEXT from web research:
{context[:3000]}

OUTPUT: A JSON array where each entry has:
- "name": exact company name (from the list above, or a new company you are adding)
- "market_share_pct": your best estimate of their % share (0-100, must sum to ~100 across all major players)
- "share_confidence": "high" | "medium" | "low"
- "share_notes": one sentence explaining the basis for this estimate (cite specific facts if known)
- "is_new_company": true if this company was NOT in the input list above, false otherwise

Return ONLY the JSON array:"""

        try:
            time.sleep(8)
            raw    = self._llm_quality_only(prompt, max_tokens=3000)
            share_data = self._parse_json(raw)
            if not isinstance(share_data, list):
                raise ValueError("Not a list")

            # Build lookup of existing entities
            entity_map = {e["name"].lower(): e for e in entities}
            total_pct = 0.0
            processed = []

            for item in share_data:
                if not isinstance(item, dict):
                    continue
                name = (item.get("name") or "").strip()
                if len(name) < 3:
                    continue
                pct = float(item.get("market_share_pct", 0) or 0)
                if pct <= 0:
                    continue

                # If LLM found a new company, add it to entities
                if item.get("is_new_company") and name.lower() not in entity_map:
                    print(f"[+] LLM identified additional supplier: {name}")
                    new_entity = {
                        "name": name,
                        "country": "Unknown",
                        "ultimate_owner_country": "Unknown",
                        "parent_company": None,
                        "role": "Producer",
                        "quantum_relevance": "adjacent",
                        "strategic_notes": item.get("share_notes", ""),
                        "source_url": "LLMESTIMATED",
                        "data_confidence": "low",
                        "data_source": f"AI-Estimated ({_MODEL_LABEL} — identified during market share estimation)",
                    }
                    entities.append(new_entity)
                    entity_map[name.lower()] = new_entity

                # Attach share data
                entity = entity_map.get(name.lower())
                if entity:
                    entity["market_share_pct"] = round(pct, 1)
                    entity["share_confidence"] = item.get("share_confidence", "medium")
                    entity["share_notes"]      = item.get("share_notes", "")
                    total_pct += pct

                processed.append(name.lower())

            # Normalize to decimals (0-1) and fill in any companies the LLM missed.
            # Re-scale so shares always sum to exactly 100% regardless of LLM rounding.
            if total_pct > 0:
                for entity in entities:
                    if "market_share_pct" not in entity:
                        entity["market_share_pct"] = 0.0
                        entity["share_confidence"] = "low"
                        entity["share_notes"] = "Share not estimated by LLM"
                    # Re-scale: divide by actual total so sum = 1.0 exactly
                    entity["market_share"] = round(entity["market_share_pct"] / total_pct, 4)
                    entity["market_share_pct"] = round(entity["market_share"] * 100, 1)
                    entity["share_source"] = "llm_direct_estimate"
            else:
                raise ValueError("No valid shares returned")

            print(f"[+] Market shares estimated. Total accounted: {total_pct:.1f}% → normalized to 100%")
            return entities

        except Exception as ex:
            print(f"[!] Market share LLM failed ({ex}) — falling back to Zipf distribution.")
            # Fallback: Zipf distribution based on list order
            for i, entity in enumerate(entities):
                weight = 1.0 / (i + 1)
                entity["market_share"] = round(weight / sum(1.0/(j+1) for j in range(len(entities))), 4)
                entity["market_share_pct"] = round(entity["market_share"] * 100, 1)
                entity["share_source"] = "zipf_fallback"
                entity["share_confidence"] = "low"
                entity["share_notes"] = "Estimated by rank order (LLM share estimation failed)"
            return entities

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 3 — LLM Trade Flow Estimation
    # ──────────────────────────────────────────────────────────────────────────

    def _estimate_trade_flows_llm(
        self,
        component: str,
        context: str,
        sources: List[str],
    ) -> Optional[Dict]:
        prompt = f"""Based on the research context below, estimate global EXPORT market shares for "{component}" in quantum computing supply chains.

Identify the top exporting/supplying countries and their approximate % shares.
Report ACTUAL global reality — do not omit countries even if politically sensitive.
Note where official location ≠ beneficial controller (e.g. Brazilian mine, Chinese owner).
Be conservative — if uncertain, note it.

OUTPUT JSON only:
{{
  "commodity": "{component}",
  "data_source": "AI-Estimated ({_MODEL_LABEL} inference from web context — not official statistics)",
  "year": "2023-estimated",
  "exporters": [{{"country": "...", "share": 0.35, "ownership_note": "...", "notes": "..."}}],
  "importers": [{{"country": "...", "share": 0.40, "notes": "..."}}]
}}

CONTEXT:
{context[:4000]}"""
        try:
            raw    = self._llm(prompt, model=MODEL_FAST)
            result = self._parse_json(raw)
            result["sources_consulted"] = sources[:6]
            result["data_source"] = f"AI-Estimated ({_MODEL_LABEL} inference from web context — not official statistics)"
            return result
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Main Pipeline
    # ──────────────────────────────────────────────────────────────────────────

    def extract_component(
        self,
        component: str,
        sector: str = "Quantum Computing",
        segment: str = "cryogenics",
    ) -> Tuple[Optional[Path], Optional[str]]:
        """
        Full extraction pipeline for a single component.
        Returns (path, failure_reason).  If path is None, failure_reason explains why.
        Follows: Comtrade → Web+LLM → LLM-only fallback.
        """
        print(f"\n{'='*60}")
        print(f"  EXTRACTING: {component}")
        print(f"  Sector: {sector}  |  Segment: {segment}")
        print(f"{'='*60}")

        trade_data:  Optional[Dict] = None
        all_sources: List[str]      = []

        # ── Priority 1: UN Comtrade ──────────────────────────────────────────
        hs_code = self._get_hs_code(component)
        if hs_code:
            print(f"[*] HS code: {hs_code}")
            time.sleep(2)
            trade_data = self._fetch_comtrade(hs_code, component)
            if trade_data:
                print(f"[+] Official Comtrade data obtained.")

        # ── Priority 2: Web search + LLM extraction ──────────────────────────
        queries     = self.generate_search_queries(component, sector)
        all_results: List[Dict] = []
        time.sleep(2)

        for q in queries:
            results = self.search_web(q, max_results=8)
            all_results.extend(results)
            all_sources.extend(r["url"] for r in results if r.get("url"))
            time.sleep(1)

        # Deduplicate sources
        seen: set = set()
        unique_sources: List[str] = []
        for s in all_sources:
            if s not in seen:
                seen.add(s)
                unique_sources.append(s)
        all_sources = unique_sources

        context_text = "\n".join(r["snippet"] for r in all_results)

        entities: List[Dict] = []

        if all_results:
            print(f"[+] {len(all_results)} results from {len(all_sources)} sources.")
            print("[*] Pausing 15s before LLM extraction…")
            time.sleep(15)
            entities = self.extract_entities_with_llm(component, all_results, sector)
        else:
            print(f"[!] No web results for '{component}'. Will attempt LLM fallback.")

        # ── Priority 2b: Second-pass gap-filling if under minimum ─────────────
        # If LLM returned fewer than 10 companies despite having web results,
        # force a second LLM call explicitly asking for MORE companies.
        if entities and len(entities) < 10:
            print(f"[!] Only {len(entities)} companies found — running second-pass gap fill…")
            known_names = [e["name"] for e in entities]
            gap_prompt = f"""You are a supply-chain intelligence analyst for the European Commission.

A first research pass found only these {len(known_names)} companies that supply "{component}" for quantum computing:
{json.dumps(known_names, indent=2)}

This is NOT enough. For EU policy purposes we need a COMPLETE picture of the global market.

YOUR TASK: Find at least 15 MORE real companies that supply "{component}" worldwide that are NOT already in the list above.
- Search globally: China, Japan, South Korea, Russia, Europe, Americas, Middle East, South-East Asia
- Include state-owned enterprises, research institutions that sell, small niche producers
- Include upstream raw material suppliers if relevant
- Do NOT repeat any company already in the list above

For EACH new company:
- name: exact legal company name
- country: country of operations/HQ
- ultimate_owner_country: beneficial owner country (may differ)
- parent_company: parent company or null
- role: "Producer" | "Refiner" | "Distributor" | "State-Owned Enterprise" | "Research Institution"
- quantum_relevance: "direct" | "upstream" | "adjacent"
- strategic_notes: 1-2 sentences on market position and any ownership flags
- source_url: "LLMESTIMATED"
- data_confidence: "medium"

CONTEXT from web research:
{context_text[:4000]}

Output JSON array only:"""
            try:
                time.sleep(8)
                raw2 = self._llm_quality_only(gap_prompt, max_tokens=4096)
                extra = self._parse_json(raw2)
                if isinstance(extra, list):
                    # Deduplicate by name (case-insensitive)
                    existing_names_lower = {e["name"].lower() for e in entities}
                    new_entities = []
                    for e in extra:
                        if not isinstance(e, dict):
                            continue
                        name = (e.get("name") or "").strip()
                        if len(name) < 3:
                            continue
                        if name.lower() in existing_names_lower:
                            continue
                        e.setdefault("ultimate_owner_country", e.get("country", "Unknown"))
                        e.setdefault("parent_company", None)
                        e.setdefault("quantum_relevance", "adjacent")
                        e.setdefault("source_url", "LLMESTIMATED")
                        e.setdefault("data_confidence", "medium")
                        new_entities.append(e)
                        existing_names_lower.add(name.lower())
                    entities.extend(new_entities)
                    print(f"[+] Gap fill added {len(new_entities)} companies. Total: {len(entities)}")
            except Exception as gap_e:
                print(f"[!] Gap fill failed: {gap_e} — continuing with {len(entities)} companies.")

        # ── Priority 3a: LLM-only supplier knowledge (if web extraction failed) ─
        if not entities:
            print(f"[!] Web extraction yielded no companies for '{component}'. Trying LLM knowledge fallback.")
            time.sleep(10)
            entities = self._llm_fallback_suppliers(component, sector)

        # ── Hard failure — report loudly ──────────────────────────────────────
        if not entities:
            reason = (
                f"EXTRACTION FAILED: No suppliers found for '{component}' after exhausting "
                f"all three tiers (Comtrade, web+LLM, LLM-only). This may indicate: "
                f"(1) component name is too generic or non-standard, "
                f"(2) component does not exist as a distinct traded good, "
                f"(3) market is so specialised it has no public data. "
                f"Queries attempted: {queries[:3]}"
            )
            print(f"[!!!] {reason}")
            return None, reason

        # ── Hard minimum: never save with only 1 supplier ─────────────────────
        # A single-supplier file breaks HHI scoring (HHI=10000 always) and
        # gives a false picture. Force another LLM pass if under minimum.
        if len(entities) < 3:
            print(f"[!!!] Only {len(entities)} supplier(s) found — this is too few. Forcing LLM knowledge expansion…")
            additional = self._llm_fallback_suppliers(component, sector)
            if additional:
                existing_names_lower = {e.get("name","").lower() for e in entities}
                for e in additional:
                    name = (e.get("name") or "").strip()
                    if name.lower() not in existing_names_lower and len(name) >= 3:
                        entities.append(e)
                        existing_names_lower.add(name.lower())
            print(f"[+] After expansion: {len(entities)} suppliers.")

        # ── Ownership enrichment ──────────────────────────────────────────────
        entities = self._enrich_ownership(entities)

        # Market share estimation
        entities = self.estimate_market_shares(component, entities, context_text)

        # ── Trade flows fallback ──────────────────────────────────────────────
        if not trade_data:
            print("[*] No Comtrade data — using LLM trade estimation (fallback)…")
            time.sleep(10)
            trade_data = self._estimate_trade_flows_llm(component, context_text, all_sources)

        # ── Persist ──────────────────────────────────────────────────────────
        path = self._save_data(component, sector, segment, entities, trade_data, all_sources)
        print(f"[+] Saved → {path}")
        print("[*] Cooling down 5s…\n")
        time.sleep(5)
        return path, None

    def batch_extract_from_taxonomy(self, segment: str, sector: str) -> Dict[str, Any]:
        """
        Extract all leaf components from a saved taxonomy.
        Skips components that already have a supplier file.

        EXHAUSTIVENESS ENFORCEMENT (point 14):
        - Every component in the taxonomy MUST be attempted.
        - Failures are logged loudly with reasons.
        - A batch_report.json is written summarising success/failure.
        - Returns the report dict.
        """
        sector_dir = self.data_dir / "sectors" / self._safe_name(sector) / self._safe_name(segment)
        tax_file   = sector_dir / "taxonomy.json"

        if not tax_file.exists():
            print(f"[!] Taxonomy not found: {tax_file}")
            return {"error": f"Taxonomy not found at {tax_file}"}

        with open(tax_file) as f:
            taxonomy = json.load(f)

        leaves: List[str] = []

        def _collect(node: dict) -> None:
            if "leaf_id" in node:
                leaves.append(node["name"])
            for child in node.get("children", []):
                _collect(child)

        for top in taxonomy.get("supply_chain", []):
            _collect(top)

        total = len(leaves)
        print(f"\n{'#'*60}")
        print(f"  BATCH EXTRACTION: {total} components in {sector}/{segment}")
        print(f"{'#'*60}\n")

        report: Dict[str, Any] = {
            "sector":          sector,
            "segment":         segment,
            "total_components": total,
            "extracted_at":    datetime.datetime.now().isoformat(),
            "succeeded":       [],
            "skipped_existing": [],
            "failed":          [],
        }

        for i, component in enumerate(leaves, 1):
            # Check for cancel signal
            cancel_file = self.data_dir / ".cancel_extraction"
            if cancel_file.exists():
                cancel_file.unlink()
                print("[!] Extraction cancelled by user.")
                break

            # Check for pause signal — wait until resumed or cancelled
            pause_file = self.data_dir / ".pause_extraction"
            if pause_file.exists():
                print("[~] Extraction paused. Waiting for resume…")
                while pause_file.exists():
                    if cancel_file.exists():
                        cancel_file.unlink()
                        print("[!] Extraction cancelled while paused.")
                        return report
                    time.sleep(3)
                print("[~] Extraction resumed.")

            print(f"\n[{i}/{total}] {component}")
            comp_file = sector_dir / "suppliers" / f"{self._safe_name(component)}_suppliers.json"

            if comp_file.exists():
                print(f"[*] Already extracted — skipping.")
                report["skipped_existing"].append(component)
                continue

            try:
                path, failure_reason = self.extract_component(component, sector, segment)
                if path:
                    report["succeeded"].append(component)
                else:
                    report["failed"].append({
                        "component": component,
                        "reason":    failure_reason,
                    })
                    print(f"[!!!] FAILED: {component}\n      Reason: {failure_reason}")
            except Exception as e:
                reason = f"Unhandled exception: {str(e)}"
                report["failed"].append({"component": component, "reason": reason})
                print(f"[!!!] EXCEPTION for '{component}': {e}")
                continue

        # Summary
        n_ok      = len(report["succeeded"])
        n_skip    = len(report["skipped_existing"])
        n_fail    = len(report["failed"])
        n_done    = n_ok + n_skip
        coverage  = round(n_done / total * 100, 1) if total > 0 else 0

        print(f"\n{'='*60}")
        print(f"  BATCH COMPLETE — {sector}/{segment}")
        print(f"  Total:    {total}")
        print(f"  Success:  {n_ok}")
        print(f"  Skipped:  {n_skip} (already existed)")
        print(f"  FAILED:   {n_fail}")
        print(f"  Coverage: {coverage}%")
        if report["failed"]:
            print(f"\n  [!!!] FAILED COMPONENTS (require manual review):")
            for f in report["failed"]:
                print(f"        - {f['component']}: {f['reason'][:100]}…")
        print(f"{'='*60}\n")

        report["coverage_pct"]   = coverage
        report["n_succeeded"]    = n_ok
        report["n_failed"]       = n_fail
        report["n_skipped"]      = n_skip

        # Write report
        report_path = sector_dir / "batch_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[+] Batch report saved → {report_path}")

        return report

    # ──────────────────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────────────────

    def _save_data(
        self,
        component: str,
        sector: str,
        segment: str,
        entities: List[Dict],
        trade: Optional[Dict],
        sources: List[str],
    ) -> Path:
        base_dir = self._get_sector_dir(sector, segment)

        supp_path = base_dir / "suppliers" / f"{self._safe_name(component)}_suppliers.json"
        supp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(supp_path, "w") as f:
            json.dump({
                "component":    component,
                "sector":       sector,
                "segment":      segment,
                "extracted_at": datetime.datetime.now().isoformat(),
                "model_used":   MODEL_QUALITY,
                "suppliers":    entities,
                "sources":      sources,
            }, f, indent=2)

        if trade:
            trade_path = base_dir / "trade" / f"{self._safe_name(component)}_trade_flows.json"
            trade_path.parent.mkdir(parents=True, exist_ok=True)
            with open(trade_path, "w") as f:
                json.dump(trade, f, indent=2)

        return supp_path


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="SupplyTrace — Quantum Supply Chain Extractor")
    parser.add_argument("--component", type=str, help="Component to extract (e.g. 'Helium-3')")
    parser.add_argument("--sector",    type=str, default="Quantum Computing")
    parser.add_argument("--segment",   type=str, default="cryogenics")
    parser.add_argument("--batch",     action="store_true", help="Batch extract from saved taxonomy")
    args = parser.parse_args()

    extractor = SupplyChainExtractor()

    if args.batch:
        extractor.batch_extract_from_taxonomy(args.segment, args.sector)
    elif args.component:
        path, reason = extractor.extract_component(args.component, args.sector, args.segment)
        if not path:
            print(f"\n[!!!] EXTRACTION FAILED: {reason}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
