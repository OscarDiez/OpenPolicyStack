"""
SupplyTrace — Supply Chain Risk Intelligence API
=================================================
FastAPI app serving the multi-sector dashboard, onboarding wizard,
supply chain graph view, and all discovery/extraction endpoints.
"""
import json
import asyncio
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .scoring import score_component
from .analytics import get_recursive_risk_metrics, load_dependency_graph, get_component_risk_metrics
from .extractor import SupplyChainExtractor

# ─── App & Templates ──────────────────────────────────────────────────────────
app = FastAPI(
    title="SupplyTrace — Strategic Risk Intelligence",
    version="1.0.0",
    description="Multi-sector supply chain risk scoring and extraction engine.",
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

COUNTRY_COORDS: Dict[str, list] = {
    "USA": [37.09, -95.71], "US": [37.09, -95.71], "UNITED STATES": [37.09, -95.71],
    "CHINA": [35.86, 104.19], "CN": [35.86, 104.19],
    "RUSSIA": [61.52, 105.31], "RUSSIAN FEDERATION": [61.52, 105.31],
    "GERMANY": [51.16, 10.45], "JAPAN": [36.20, 138.25],
    "UK": [55.37, -3.43], "UNITED KINGDOM": [55.37, -3.43],
    "NETHERLANDS": [52.13, 5.29], "FINLAND": [61.92, 25.74],
    "FRANCE": [46.22, 2.21], "CANADA": [56.13, -106.34],
    "SWITZERLAND": [46.81, 8.22], "UKRAINE": [48.37, 31.16],
    "SOUTH KOREA": [35.90, 127.76], "TAIWAN": [23.69, 120.96],
    "INDIA": [20.59, 78.96], "AUSTRIA": [47.51, 14.55],
    "SWEDEN": [60.12, 18.64], "ITALY": [41.87, 12.56],
    "SPAIN": [40.46, -3.74], "BELGIUM": [50.50, 4.46],
    "AUSTRALIA": [-25.27, 133.77], "BRAZIL": [-14.23, -51.92],
    "SINGAPORE": [1.35, 103.82], "ISRAEL": [31.04, 34.85],
}


def _normalize_component_name(stem: str) -> str:
    name = stem.replace("_", " ").title()
    name = name.replace("Nbti", "NbTi").replace("Ofhc", "OFHC")
    name = name.replace("Rf ", "RF ").replace("Pid ", "PID ")
    if "Helium 3" in name: name = "Helium-3"
    if "Helium 4" in name: name = "Helium-4"
    return name


def _build_dashboard_rows(results: list) -> str:
    rows_html = ""
    for res in results:
        score = res["score"]
        color = "var(--success)"
        if score > 0.55: color = "var(--danger)"
        elif score > 0.35: color = "var(--warning)"

        badge_cls = f"badge-{res['conf']}"
        drivers_li = "".join(f"<li>{d}</li>" for d in res["drivers"][:2])

        supp_html = ""
        if not res["suppliers"]:
            supp_html = '<div class="no-data">No supplier records yet. Use "Discover" to extract intelligence.</div>'
        else:
            for s in res["suppliers"]:
                # Technical Specs
                tech = s.get("technical_capacity", {})
                specs_html = "".join([f'<span class="tech-badge">{spec}</span>' for spec in tech.get("specs", [])[:3]])
                modality = tech.get("modality")
                modality_html = f'<div class="tech-modality">{modality}</div>' if modality else ""

                # Financials
                fins = s.get("financials", {})
                funding = fins.get("total_funding")
                round_info = fins.get("last_round")
                fins_html = ""
                if funding or round_info:
                    fins_html = f'<div class="fin-info">💰 {funding or ""} {f"({round_info})" if round_info else ""}</div>'

                # Ecosystem
                eco = s.get("ecosystem", {})
                partners = ", ".join(eco.get("partnerships", []))
                eco_html = f'<div class="eco-info">🤝 {partners}</div>' if partners else ""

                # Leadership
                lead = s.get("leadership", {})
                founders = ", ".join(lead.get("founders", []))
                lead_html = f'<div class="lead-info">👤 {founders}</div>' if founders else ""

                supp_html += f"""
                <div class="supplier-card">
                    <div class="supplier-card-header">
                        <div class="supplier-name">{s['name']}</div>
                        <div class="supplier-meta">
                            <span>📍 {s.get('country') or 'Unknown'}</span>
                            <span>🏷️ {s.get('role') or 'Producer'}</span>
                        </div>
                    </div>
                    {modality_html}
                    <div class="tech-specs-container">{specs_html}</div>
                    <div class="supplier-details-grid">
                        {fins_html}
                        {eco_html}
                        {lead_html}
                    </div>
                    <div class="supplier-notes">{s.get('strategic_notes') or ''}</div>
                </div>"""

        safe_suppliers = json.dumps(res["suppliers"]).replace("'", "&apos;")
        
        sources_html = ""
        if res.get("sources"):
            sources_list = "".join([f'<li><a href="{src}" target="_blank" style="color:var(--primary);text-decoration:none;word-wrap:break-word;">{src}</a></li>' for src in res["sources"][:5]])
            sources_html = f"""
            <div class="sources-info" style="margin-top: 1.5rem; border-top: 1px solid var(--border); padding-top: 1rem;">
                <h4 style="margin:0 0 1rem;color:var(--muted);text-transform:uppercase;font-size:0.72rem">Extracted Sources</h4>
                <ul style="margin: 0; padding-left: 1.2rem; font-size: 0.85rem; color: var(--text-secondary);">
                    {sources_list}
                </ul>
            </div>
            """

        rows_html += f"""
        <tr class="clickable-row" onclick="toggleDetails('{res['id']}')">
            <td><div class="comp-name">{res['name']}</div></td>
            <td>
                <div class="score-val" style="color:{color}">{score:.2f}</div>
                <div class="risk-bar-bg"><div class="risk-bar" style="width:{score*100}%;background:{color}"></div></div>
            </td>
            <td><span class="badge {badge_cls}">{res['conf']}</span></td>
            <td><ul class="drivers-list">{drivers_li}</ul></td>
        </tr>
        <tr class="details-row" id="details-{res['id']}">
            <td colspan="4">
                <div class="details-content">
                    <div class="supplier-info">
                        <h4 style="margin:0 0 1rem;color:var(--muted);text-transform:uppercase;font-size:0.72rem">Identified Producers</h4>
                        {supp_html}
                        {sources_html}
                    </div>
                    <div class="map-container" id="map-{res['id']}" data-suppliers='{safe_suppliers}'></div>
                </div>
            </td>
        </tr>"""
    return rows_html


# ─── Page Routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding(request: Request):
    return templates.TemplateResponse("onboarding.html", {"request": request})


def _safe_name(text: str) -> str:
    """Sanitise any string into a safe folder/file name."""
    s = text.lower()
    for ch in [" ", "/", "-", "\u2014", "\u2013", "(", ")", "."]:
        s = s.replace(ch, "_")
    return re.sub(r"_+", "_", s).strip("_")


def _get_active_session() -> Optional[Dict[str, str]]:
    """Reads the last saved session. Returns None if no session file exists."""
    session_file = DATA_DIR / "active_session.json"
    if session_file.exists():
        try:
            with open(session_file) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _get_sector_data_dir(session: Optional[Dict[str, str]]) -> Optional[Path]:
    """
    Given a session dict, returns the per-sector data directory.
    e.g. {sector:'Quantum Computing', segment:'Cryogenics'}
         -> data/sectors/quantum_computing/cryogenics/
    Returns None if session is missing or incomplete.
    """
    if not session:
        return None
    sector = session.get("sector", "")
    segment = session.get("segment", "")
    if not sector or not segment:
        return None
    return DATA_DIR / "sectors" / _safe_name(sector) / _safe_name(segment)


def _get_active_component_names() -> Optional[set]:
    """
    Returns the set of lowercase component names for the active taxonomy, or:
    - None  : no session — no filter, show everything
    - set() : session exists but taxonomy is empty / not found yet
    """
    session = _get_active_session()
    sector_dir = _get_sector_data_dir(session)
    if sector_dir is None:
        return None  # No session — show everything

    tax_file = sector_dir / "taxonomy.json"
    if not tax_file.exists():
        return set()  # Session exists but taxonomy not written yet

    try:
        with open(tax_file) as f:
            tax = json.load(f)
        names: set = set()
        for top in tax.get("subsystems", []):
            for sub in top.get("subsystems", []):
                for comp in sub.get("components", []):
                    names.add(comp["name"].lower())
        return names
    except Exception:
        return set()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    session = _get_active_session()
    region = (session or {}).get("region", "EU")
    segment_label = (session or {}).get("segment", "All Components")
    sector_label = (session or {}).get("sector", "")
    sector_dir = _get_sector_data_dir(session)

    active_names = _get_active_component_names()
    has_session = session is not None

    # Scan the correct suppliers directory
    if sector_dir and (sector_dir / "suppliers").exists():
        suppliers_dir = sector_dir / "suppliers"
    elif active_names is None:
        # No session — fall back to legacy flat directory so old data still shows
        suppliers_dir = DATA_DIR / "suppliers"
    else:
        suppliers_dir = None  # Session exists but sector dir not set up yet

    files = sorted(suppliers_dir.glob("*_suppliers.json")) if suppliers_dir and suppliers_dir.exists() else []

    results = []
    for f in files:
        name = _normalize_component_name(f.stem.replace("_suppliers", ""))
        if active_names is not None and name.lower() not in active_names:
            continue
        try:
            with open(f) as fh:
                sdata = json.load(fh)
            suppliers = [s for s in sdata.get("suppliers", []) if s.get("name") != "GLOBAL_INDUSTRY_TOTAL"]
            sources = sdata.get("sources", [])
            score, drivers, conf = score_component(region, name, data_dir=sector_dir)
            results.append({"id": f.stem, "name": name, "score": score, "conf": conf, "drivers": drivers, "suppliers": suppliers, "sources": sources})
        except Exception:
            pass

    results.sort(key=lambda x: x["score"], reverse=True)
    avg_risk = sum(r["score"] for r in results) / len(results) if results else 0
    critical_count = sum(1 for r in results if r["score"] > 0.55)
    
    is_extracting = (session or {}).get("is_extracting", False)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_components": len(results),
        "avg_risk": f"{avg_risk:.2f}",
        "critical_count": critical_count,
        "segment": segment_label,
        "sector": sector_label,
        "has_session": has_session,
        "is_extracting": is_extracting,
        "rows": _build_dashboard_rows(results),
        "coords_json": json.dumps(COUNTRY_COORDS),
    })


@app.get("/graph-view", response_class=HTMLResponse)
async def graph_view(request: Request):
    session = _get_active_session()
    region = (session or {}).get("region", "EU")
    sector_dir = _get_sector_data_dir(session)

    graph = load_dependency_graph(data_dir=sector_dir)
    deps = graph.get("dependencies", [])

    suppliers_dir = (sector_dir / "suppliers") if sector_dir else (DATA_DIR / "suppliers")
    scores: Dict[str, Any] = {}
    if suppliers_dir and suppliers_dir.exists():
        for f in suppliers_dir.glob("*_suppliers.json"):
            name = _normalize_component_name(f.stem.replace("_suppliers", ""))
            try:
                metrics = get_component_risk_metrics(name, region, data_dir=sector_dir)
                score_val, _, _ = score_component(region, name, data_dir=sector_dir)
                scores[name] = {
                    "score": score_val,
                    "pillar_scores": metrics.get("pillar_scores", {}),
                    "drivers": metrics.get("key_drivers", []),
                }
            except Exception:
                pass

    return templates.TemplateResponse("graph.html", {
        "request": request,
        "graph_json": json.dumps(deps),
        "scores_json": json.dumps(scores),
    })


# ─── API Routes ──────────────────────────────────────────────────────────────

class TaxonomyRequest(BaseModel):
    sector: str
    segment: str

class SaveTaxonomyRequest(BaseModel):
    taxonomy: Dict[str, Any]
    segment: str
    sector: Optional[str] = ""
    region: Optional[str] = "EU"

class ExtractionRequest(BaseModel):
    sector: str
    segment: str
    region: Optional[str] = "EU"

class ScoreRequest(BaseModel):
    region: str
    segment: str
    scenario: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "supplytrace", "version": "1.0.0"}


@app.post("/api/v1/generate-taxonomy")
async def generate_taxonomy(req: TaxonomyRequest) -> Dict[str, Any]:
    """LLM generates a draft taxonomy for any sector+segment."""
    extractor = SupplyChainExtractor()
    sector_dir = DATA_DIR / "sectors" / _safe_name(req.sector) / _safe_name(req.segment)
    tax_file = sector_dir / "taxonomy.json"
    
    is_cached = False
    if tax_file.exists():
        suppliers_dir = sector_dir / "suppliers"
        if suppliers_dir.exists() and len(list(suppliers_dir.glob("*_suppliers.json"))) > 0:
            is_cached = True
            
        with open(tax_file, "r") as f:
            taxonomy = json.load(f)
        return {"status": "ok", "taxonomy": taxonomy, "is_cached": is_cached}
        
    taxonomy = extractor.generate_taxonomy_with_llm(req.sector, req.segment)
    return {"status": "ok", "taxonomy": taxonomy, "is_cached": False}


@app.post("/api/v1/save-taxonomy")
async def save_taxonomy(req: SaveTaxonomyRequest) -> Dict[str, Any]:
    """Saves the user-approved taxonomy into data/sectors/{sector}/{segment}/ and updates active session."""
    sector = req.sector or req.taxonomy.get("technology_domain", "unknown")
    extractor = SupplyChainExtractor()
    path = extractor.save_taxonomy(req.taxonomy, req.segment, sector)

    # Persist active session
    session = {"sector": sector, "segment": req.segment, "region": req.region or "EU"}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "active_session.json", "w") as f:
        json.dump(session, f, indent=2)

    return {"status": "ok", "path": str(path)}


@app.post("/api/v1/run-extraction")
async def run_extraction(req: ExtractionRequest) -> Dict[str, Any]:
    """Kicks off batch extraction for all components in the saved taxonomy."""
    extractor = SupplyChainExtractor()
    try:
        sector_dir = DATA_DIR / "sectors" / _safe_name(req.sector) / _safe_name(req.segment)
        tax_file = sector_dir / "taxonomy.json"
        component_count = 0
        if tax_file.exists():
            with open(tax_file) as f:
                tax = json.load(f)
            for top in tax.get("subsystems", []):
                for sub in top.get("subsystems", []):
                    component_count += len(sub.get("components", []))

        session_file = DATA_DIR / "active_session.json"
        if session_file.exists():
            with open(session_file, "r") as f:
                sess = json.load(f)
            sess["is_extracting"] = True
            with open(session_file, "w") as f:
                json.dump(sess, f, indent=2)

        def extraction_task():
            try:
                extractor.batch_extract_from_taxonomy(_safe_name(req.segment), req.sector)
            finally:
                if session_file.exists():
                    try:
                        with open(session_file, "r") as f:
                            s = json.load(f)
                        s["is_extracting"] = False
                        with open(session_file, "w") as f:
                            json.dump(s, f, indent=2)
                    except Exception as ex:
                        print(f"Failed to reset extracting state: {ex}")

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, extraction_task)

        return {"status": "started", "sector": req.sector, "segment": req.segment,
                "component_count": component_count}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/v1/discovery/{component}")
async def trigger_discovery(component: str) -> Dict[str, Any]:
    """Autonomous discovery for a single new component."""
    extractor = SupplyChainExtractor()
    try:
        path = extractor.extract_component(component, deep_dive=True)
        if path:
            return {"status": "success", "component": component, "path": str(path)}
        return {"status": "error", "message": "Extraction returned no output."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/graph/{component}")
def get_graph_data(component: str, region: str = "EU") -> Dict[str, Any]:
    return get_recursive_risk_metrics(component, region=region)


@app.post("/score")
def score(req: ScoreRequest) -> Dict[str, Any]:
    risk_score, drivers, confidence = score_component(req.region, req.segment, req.scenario)
    return {"region": req.region, "segment": req.segment, "risk_score": risk_score,
            "key_drivers": drivers, "confidence": confidence}
