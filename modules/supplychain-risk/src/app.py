"""
SupplyTrace — Supply Chain Risk Intelligence API
=================================================
FastAPI application serving:
  - Onboarding wizard (taxonomy generation + extraction)
  - Multi-sector risk dashboard with scenario and perspective selectors
  - Geopolitical comparison view (EU vs US vs China)
  - Supply chain graph view
  - Analyses history hub
  - REST API for all scoring and extraction operations
"""

import json
import asyncio
import re
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load .env from the module root (one level above src/)
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

from scoring import score_component, SCENARIOS, get_scenarios_for_perspective
from analytics import (
    get_component_risk_metrics,
    load_dependency_graph,
    get_recursive_risk_metrics,
    get_perspective_comparison,
    get_segment_perspective_comparison,
    normalize_component_name,
)
from extractor import SupplyChainExtractor

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SupplyTrace — Strategic Risk Intelligence",
    version="2.0.0",
    description="Quantum technology supply chain risk scoring, extraction, and geopolitical analysis.",
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates     = Jinja2Templates(directory=str(TEMPLATES_DIR))
DATA_DIR      = Path(__file__).resolve().parents[1] / "data"

# ─── Country coordinates for Leaflet map ──────────────────────────────────────

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
    "DENMARK": [56.26, 9.50], "NORWAY": [60.47, 8.46],
    "CZECH REPUBLIC": [49.81, 15.47], "POLAND": [51.91, 19.14],
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_name(text: str) -> str:
    s = text.lower()
    for ch in [" ", "/", "-", "\u2014", "\u2013", "(", ")", ".", ","]:
        s = s.replace(ch, "_")
    return re.sub(r"_+", "_", s).strip("_")


def _normalize_component_name(stem: str) -> str:
    return normalize_component_name(stem)


def _get_active_session() -> Optional[Dict[str, str]]:
    session_file = DATA_DIR / "active_session.json"
    if session_file.exists():
        try:
            with open(session_file) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _get_sector_data_dir(session: Optional[Dict] = None) -> Optional[Path]:
    """Returns the data directory for an active session, or None if no session."""
    if not session:
        return None
    sector  = _safe_name(session.get("sector",  ""))
    segment = _safe_name(session.get("segment", ""))
    if not segment:
        return None
    if sector:
        return DATA_DIR / "sectors" / sector / segment
    return DATA_DIR / "segments" / segment


def _get_active_component_names(session: Optional[Dict] = None) -> Optional[set]:
    """
    Returns the set of lowercase leaf component names for the active taxonomy.
    None  → no session, show everything.
    set() → session exists but taxonomy not yet written.
    """
    if session is None:
        session = _get_active_session()
    sector_dir = _get_sector_data_dir(session)
    if sector_dir is None:
        return None

    tax_file = sector_dir / "taxonomy.json"
    if not tax_file.exists():
        return set()

    try:
        with open(tax_file) as f:
            tax = json.load(f)
        names: set = set()

        def _extract(node: dict) -> None:
            if "leaf_id" in node:
                raw_name = node.get("name", "")
                # Strip parenthetical suffixes (e.g. "Qubit Processor (IBM)" → "Qubit Processor")
                # so it matches the normalized file stem names
                clean = re.sub(r'\s*\([^)]*\)', '', raw_name).strip()
                names.add(clean.lower())
            for child in node.get("children", []):
                _extract(child)

        for top in tax.get("supply_chain", []):
            _extract(top)
        return names
    except Exception:
        return set()


def _build_dashboard_rows(results: list, scenario: Optional[str] = None) -> str:
    rows_html = ""
    for res in results:
        score = res["score"]
        if score > 0.55:
            color = "var(--danger)"
        elif score > 0.35:
            color = "var(--warning)"
        else:
            color = "var(--success)"

        badge_cls  = f"badge-{res['conf']}"
        drivers_li = "".join(f"<li>{d}</li>" for d in res["drivers"][:2])

        # Supplier cards
        supp_html = ""
        if not res["suppliers"]:
            supp_html = (
                '<p class="no-data">No supplier records yet. '
                'Use the Discover bar above to extract intelligence.</p>'
            )
        else:
            for s in res["suppliers"]:
                confidence = s.get("data_confidence", "")
                conf_cls   = {"high": "conf-high", "medium": "conf-med", "low": "conf-low"}.get(confidence, "")
                # Market share display
                share_pct = s.get("market_share_pct")
                if share_pct is None and s.get("market_share") is not None:
                    share_pct = round(float(s.get("market_share", 0)) * 100, 1)
                share_html = ""
                if share_pct is not None and float(share_pct) > 0:
                    share_conf = s.get("share_confidence", "")
                    share_note = s.get("share_notes", "")
                    share_title = f'title="{share_note}"' if share_note else ''
                    share_conf_label = f" ({share_conf})" if share_conf else ""
                    share_html = f'<span class="share-badge" {share_title}>~{share_pct:.1f}% est. share{share_conf_label}</span>'

                # Ownership intelligence
                owner_country = s.get("beneficial_owner_country") or s.get("ultimate_owner_country") or ""
                listed_country = s.get("country") or "Unknown"
                ownership_html = ""
                if owner_country and owner_country.upper() not in (listed_country.upper(), "UNKNOWN"):
                    ownership_html = f'<span class="ownership-flag" title="Beneficial owner country differs from listed HQ">&#9888; Beneficial owner: {owner_country}</span>'
                elif s.get("ownership_detail"):
                    ownership_html = f'<span class="ownership-note">{s.get("ownership_detail", "")[:80]}</span>'

                supp_html += f"""
                <div class="supplier-card">
                    <div class="supplier-card-header">
                        <span class="supplier-name">{s.get('name', '')}</span>
                        <span class="supplier-meta">{listed_country} &middot; {s.get('role') or 'Producer'}</span>
                    </div>
                    {share_html}
                    <p class="supplier-notes">{s.get('strategic_notes') or ''}</p>
                    {ownership_html}
                    {f'<span class="conf-badge {conf_cls}">{confidence} confidence</span>' if confidence else ''}
                </div>"""

        # Sources
        sources_html = ""
        if res.get("sources"):
            items = "".join(
                f'<li><a href="{src}" target="_blank" rel="noopener">{src}</a></li>'
                for src in res["sources"][:6]
            )
            sources_html = f"""
            <div class="sources-block">
                <h5>Intelligence Sources</h5>
                <ul>{items}</ul>
            </div>"""

        safe_suppliers = json.dumps(res["suppliers"]).replace("'", "&#39;")

        safe_comp_name = res['name'].replace("'", "\\'")
        rows_html += f"""
        <tr class="data-row" onclick="toggleDetails('{res['id']}')">
            <td>
                <span class="comp-name">{res['name']}</span>
                <button class="reextract-btn" id="reextract-{res['id']}" title="Re-extract intelligence for this component"
                    onclick="event.stopPropagation(); reExtractComponent('{safe_comp_name}', '{res['id']}')">&#8635;</button>
            </td>
            <td>
                <span class="score-val" style="color:{color}">{score:.3f}</span>
                <div class="risk-bar-bg"><div class="risk-bar" style="width:{score*100:.1f}%;background:{color}"></div></div>
            </td>
            <td><span class="badge {badge_cls}">{res['conf']}</span></td>
            <td><ul class="drivers-list">{drivers_li}</ul></td>
        </tr>
        <tr class="detail-row" id="details-{res['id']}">
            <td colspan="4">
                <div class="detail-content">
                    <div class="supplier-panel">
                        <h5>Identified Producers</h5>
                        {supp_html}
                        {sources_html}
                        <div class="so-what-block" id="sw-{res['id']}">
                            <h5 style="margin-top:.9rem">Policy Analysis</h5>
                            <button class="so-what-btn" onclick="loadSoWhat('{res['name'].replace("'", "&apos;")}', '{res['id']}')">
                                Generate "So what?" Analysis
                            </button>
                            <div class="so-what-text" id="sw-text-{res['id']}" style="display:none"></div>
                        </div>
                    </div>
                    <div class="map-panel" id="map-{res['id']}" data-suppliers='{safe_suppliers}'></div>
                </div>
            </td>
        </tr>"""
    return rows_html


# ─── Page Routes ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding(request: Request):
    return templates.TemplateResponse("onboarding.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request:  Request,
    sector:   Optional[str] = None,
    segment:  Optional[str] = None,
    region:   Optional[str] = None,
    scenario: Optional[str] = None,
):
    session = _get_active_session()

    # URL params override active session (used when navigating from Analyses page)
    if sector and segment:
        sector_label  = sector
        segment_label = segment
        sector_dir    = DATA_DIR / "sectors" / _safe_name(sector) / _safe_name(segment)
        eff_region    = region or "EU"
    else:
        sector_label  = (session or {}).get("sector", "")
        segment_label = (session or {}).get("segment", "All Components")
        sector_dir    = _get_sector_data_dir(session)
        eff_region    = region or (session or {}).get("region", "EU")

    has_session   = session is not None or bool(sector and segment)
    is_extracting = (session or {}).get("is_extracting", False)
    is_paused     = (session or {}).get("is_paused", False)

    suppliers_dir = (
        (sector_dir / "suppliers") if sector_dir
        else DATA_DIR / "segments" / "cryogenics" / "suppliers"
    )
    files = sorted(suppliers_dir.glob("*_suppliers.json")) if suppliers_dir and suppliers_dir.exists() else []

    results = []
    for f in files:
        name = _normalize_component_name(f.stem.replace("_suppliers", ""))
        try:
            with open(f) as fh:
                sdata = json.load(fh)
            suppliers = [s for s in sdata.get("suppliers", []) if s.get("name") != "GLOBAL_INDUSTRY_TOTAL"]
            sources   = sdata.get("sources", [])
            score, drivers, conf = score_component(eff_region, name, scenario=scenario, data_dir=sector_dir)
            results.append({
                "id": f.stem, "name": name, "score": score,
                "conf": conf, "drivers": drivers,
                "suppliers": suppliers, "sources": sources,
            })
        except Exception:
            pass

    results.sort(key=lambda x: x["score"], reverse=True)
    avg_risk       = sum(r["score"] for r in results) / len(results) if results else 0.0
    critical_count = sum(1 for r in results if r["score"] > 0.55)

    # Scenario label for display
    scenario_label = SCENARIOS[scenario]["label"] if scenario and scenario in SCENARIOS else "Baseline"

    return templates.TemplateResponse("dashboard.html", {
        "request":              request,
        "total_components":     len(results),
        "avg_risk":             f"{avg_risk:.3f}",
        "critical_count":       critical_count,
        "segment":              segment_label,
        "sector":               sector_label,
        "has_session":          has_session,
        "is_extracting":        is_extracting,
        "is_paused":            is_paused,
        "region":               eff_region,
        "scenario":             scenario or "",
        "scenario_label":       scenario_label,
        "scenarios":            SCENARIOS,
        "rows":                 _build_dashboard_rows(results, scenario),
        "coords_json":          json.dumps(COUNTRY_COORDS),
    })


@app.get("/taxonomy-view", response_class=HTMLResponse)
async def taxonomy_view(
    request: Request,
    sector:  Optional[str] = None,
    segment: Optional[str] = None,
):
    if sector and segment:
        sector_dir    = DATA_DIR / "sectors" / _safe_name(sector) / _safe_name(segment)
        segment_label = segment
    else:
        session       = _get_active_session()
        sector_dir    = _get_sector_data_dir(session)
        segment_label = (session or {}).get("segment", "Unknown")
        sector        = (session or {}).get("sector", "")

    taxonomy = {"supply_chain": []}
    if sector_dir:
        tax_file = sector_dir / "taxonomy.json"
        if tax_file.exists():
            with open(tax_file) as f:
                taxonomy = json.load(f)

    # Compute scores for all components that have supplier files
    scores: Dict[str, Any] = {}
    if sector_dir:
        suppliers_dir = sector_dir / "suppliers"
        if suppliers_dir and suppliers_dir.exists():
            session_r  = _get_active_session()
            eff_region = (session_r or {}).get("region", "EU")
            for f in suppliers_dir.glob("*_suppliers.json"):
                name = _normalize_component_name(f.stem.replace("_suppliers", ""))
                try:
                    score_val, drivers, conf = score_component(eff_region, name, data_dir=sector_dir)
                    scores[name] = {"score": score_val, "conf": conf, "drivers": drivers[:2]}
                except Exception:
                    pass

    # Compute branch scores as averages of their children's leaf scores
    def _score_node_recursive(node: dict) -> Optional[float]:
        if "leaf_id" in node:
            return scores.get(node.get("name", ""), {}).get("score")
        child_scores = [_score_node_recursive(ch) for ch in node.get("children", [])]
        valid = [s for s in child_scores if s is not None]
        if valid:
            avg = round(sum(valid) / len(valid), 3)
            scores[node.get("name", "")] = {"score": avg, "conf": "medium", "drivers": []}
            return avg
        return None

    for top in taxonomy.get("supply_chain", []):
        _score_node_recursive(top)

    return templates.TemplateResponse("taxonomy_view.html", {
        "request":     request,
        "segment":     segment_label,
        "sector":      sector or "",
        "taxonomy":    taxonomy,
        "scores_json": json.dumps(scores),
    })


@app.get("/graph-view", response_class=HTMLResponse)
async def graph_view(request: Request):
    session    = _get_active_session()
    region     = (session or {}).get("region", "EU")
    sector_dir = _get_sector_data_dir(session)

    graph = load_dependency_graph(data_dir=sector_dir)
    deps  = graph.get("dependencies", [])

    suppliers_dir = (sector_dir / "suppliers") if sector_dir else (DATA_DIR / "segments" / "cryogenics" / "suppliers")
    scores: Dict[str, Any] = {}
    if suppliers_dir and suppliers_dir.exists():
        for f in suppliers_dir.glob("*_suppliers.json"):
            name = _normalize_component_name(f.stem.replace("_suppliers", ""))
            try:
                score_val, _, _ = score_component(region, name, data_dir=sector_dir)
                metrics         = get_component_risk_metrics(name, region, data_dir=sector_dir)
                scores[name]    = {
                    "score":         score_val,
                    "pillar_scores": metrics.get("pillar_scores", {}),
                    "drivers":       metrics.get("key_drivers", []),
                }
            except Exception:
                pass

    return templates.TemplateResponse("graph.html", {
        "request":    request,
        "graph_json": json.dumps(deps),
        "scores_json": json.dumps(scores),
    })


@app.get("/comparison", response_class=HTMLResponse)
async def comparison_view(
    request: Request,
    sector:  Optional[str] = None,
    segment: Optional[str] = None,
    scenario: Optional[str] = None,
):
    """Geopolitical comparison page: EU vs US vs China side-by-side."""
    if sector and segment:
        sector_dir    = DATA_DIR / "sectors" / _safe_name(sector) / _safe_name(segment)
        segment_label = segment
        sector_label  = sector
    else:
        session       = _get_active_session()
        sector_dir    = _get_sector_data_dir(session)
        segment_label = (session or {}).get("segment", "All Components")
        sector_label  = (session or {}).get("sector", "")

    comparisons = get_segment_perspective_comparison(sector_dir, scenario=scenario) if sector_dir else []

    return templates.TemplateResponse("comparison.html", {
        "request":      request,
        "segment":      segment_label,
        "sector":       sector_label,
        "comparisons":  comparisons,
        "scenario":     scenario or "",
        "scenarios":    SCENARIOS,
    })


@app.get("/analyses", response_class=HTMLResponse)
async def analyses_page(request: Request):
    """List all past analyses grouped by sector."""
    analyses    = []
    sectors_dir = DATA_DIR / "sectors"

    def _count_leaves(node: dict) -> int:
        c = 1 if "leaf_id" in node else 0
        return c + sum(_count_leaves(ch) for ch in node.get("children", []))

    def _supp_stats(supp_dir: "Path"):
        count, last_ts = 0, 0.0
        if supp_dir.exists():
            files = list(supp_dir.glob("*_suppliers.json"))
            for sf in files:
                try:
                    with open(sf) as fh:
                        sd = json.load(fh)
                    count += len([s for s in sd.get("suppliers", []) if s.get("name") != "GLOBAL_INDUSTRY_TOTAL"])
                except Exception:
                    pass
            if files:
                last_ts = max(f.stat().st_mtime for f in files)
        return count, last_ts

    if sectors_dir.exists():
        for sector_folder in sectors_dir.iterdir():
            if not sector_folder.is_dir():
                continue
            for segment_folder in sector_folder.iterdir():
                if not segment_folder.is_dir() or segment_folder.name.startswith("_"):
                    continue
                tax_file = segment_folder / "taxonomy.json"
                if not tax_file.exists():
                    continue
                try:
                    with open(tax_file) as f:
                        tax = json.load(f)

                    sector_name  = tax.get("technology_domain", sector_folder.name.replace("_", " ").title())
                    segment_name = tax.get("segment", segment_folder.name.replace("_", " ").title())
                    sources      = tax.get("sources", [])
                    comp_count   = sum(_count_leaves(n) for n in tax.get("supply_chain", []))
                    supp_count, last_ts = _supp_stats(segment_folder / "suppliers")

                    last_run_str = "Never"
                    if last_ts > 0:
                        last_run_str = datetime.datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M")

                    # Scan _archive subdirectories for past runs
                    archived_runs = []
                    archive_root = segment_folder / "_archive"
                    if archive_root.exists():
                        for run_dir in sorted(archive_root.iterdir(), reverse=True):
                            if not run_dir.is_dir():
                                continue
                            run_tax  = run_dir / "taxonomy.json"
                            run_comp = 0
                            if run_tax.exists():
                                try:
                                    with open(run_tax) as fh:
                                        rt = json.load(fh)
                                    run_comp = sum(_count_leaves(n) for n in rt.get("supply_chain", []))
                                except Exception:
                                    pass
                            run_supp, _ = _supp_stats(run_dir / "suppliers")
                            # Parse timestamp from folder name (2026-03-19_14-30-00)
                            try:
                                run_dt = datetime.datetime.strptime(run_dir.name, "%Y-%m-%d_%H-%M-%S")
                                run_label = run_dt.strftime("%Y-%m-%d %H:%M")
                            except ValueError:
                                run_label = run_dir.name
                            archived_runs.append({
                                "label":            run_label,
                                "folder":           run_dir.name,
                                "components_count": run_comp,
                                "suppliers_count":  run_supp,
                            })

                    analyses.append({
                        "sector":            sector_name,
                        "segment":           segment_name,
                        "sector_raw":        sector_folder.name,
                        "segment_raw":       segment_folder.name,
                        "components_count":  comp_count,
                        "suppliers_count":   supp_count,
                        "last_run":          last_run_str,
                        "last_run_ts":       last_ts,
                        "sources":           sources,
                        "archived_runs":     archived_runs,
                    })
                except Exception as e:
                    print(f"[!] Could not parse {segment_folder}: {e}")

    grouped: Dict[str, list] = {}
    for a in sorted(analyses, key=lambda x: x["last_run_ts"], reverse=True):
        grouped.setdefault(a["sector"], []).append(a)

    return templates.TemplateResponse("analyses.html", {
        "request":          request,
        "grouped_analyses": grouped,
        "total_count":      len(analyses),
    })


# ─── API Routes ───────────────────────────────────────────────────────────────

class TaxonomyRequest(BaseModel):
    sector:  str
    segment: str
    force:   Optional[bool] = False

class SaveTaxonomyRequest(BaseModel):
    taxonomy: Dict[str, Any]
    segment:  str
    sector:   Optional[str] = ""
    region:   Optional[str] = "EU"

class ExtractionRequest(BaseModel):
    sector:  str
    segment: str
    region:  Optional[str] = "EU"

class RerunExtractionRequest(BaseModel):
    sector:         str
    segment:        str
    supplier_limit: Optional[int] = None

class ArchiveRequest(BaseModel):
    sector:  str
    segment: str

class ScoreRequest(BaseModel):
    region:   str
    segment:  str
    scenario: Optional[str] = None

class ExtractNodeRequest(BaseModel):
    component: str
    sector:    str
    segment:   str

class ReExtractComponentRequest(BaseModel):
    component: str
    sector:    str
    segment:   str


@app.get("/health")
def health():
    return {"status": "ok", "service": "supplytrace", "version": "2.0.0"}


@app.post("/api/v1/generate-taxonomy")
async def generate_taxonomy(req: TaxonomyRequest) -> Dict[str, Any]:
    """LLM generates a deep draft taxonomy for any sector + segment."""
    extractor = SupplyChainExtractor()
    sector_dir = DATA_DIR / "sectors" / _safe_name(req.sector) / _safe_name(req.segment)
    tax_file   = sector_dir / "taxonomy.json"

    if tax_file.exists() and not req.force:
        supp_dir   = sector_dir / "suppliers"
        is_cached  = supp_dir.exists() and len(list(supp_dir.glob("*_suppliers.json"))) > 0
        with open(tax_file) as f:
            taxonomy = json.load(f)
        return {"status": "ok", "taxonomy": taxonomy, "is_cached": is_cached}

    # Run in executor to avoid blocking the async event loop
    loop = asyncio.get_event_loop()
    taxonomy = await loop.run_in_executor(
        None, lambda: extractor.generate_taxonomy_with_llm(req.sector, req.segment)
    )
    return {"status": "ok", "taxonomy": taxonomy, "is_cached": False}


@app.post("/api/v1/save-taxonomy")
async def save_taxonomy(req: SaveTaxonomyRequest) -> Dict[str, Any]:
    """Save the user-approved taxonomy and update the active session."""
    sector    = req.sector or req.taxonomy.get("technology_domain", "unknown")
    extractor = SupplyChainExtractor()
    path      = extractor.save_taxonomy(req.taxonomy, req.segment, sector)

    session = {"sector": sector, "segment": req.segment, "region": req.region or "EU"}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "active_session.json", "w") as f:
        json.dump(session, f, indent=2)

    return {"status": "ok", "path": str(path)}


@app.post("/api/v1/run-extraction")
async def run_extraction(req: ExtractionRequest) -> Dict[str, Any]:
    """Kick off a background batch extraction for all taxonomy components."""
    extractor  = SupplyChainExtractor()
    sector_dir = DATA_DIR / "sectors" / _safe_name(req.sector) / _safe_name(req.segment)
    tax_file   = sector_dir / "taxonomy.json"

    # Count components
    component_count = 0
    if tax_file.exists():
        with open(tax_file) as f:
            tax = json.load(f)

        def _count(node: dict) -> int:
            c = 1 if "leaf_id" in node else 0
            return c + sum(_count(ch) for ch in node.get("children", []))

        component_count = sum(_count(n) for n in tax.get("supply_chain", []))

    # Set extracting flag
    session_file = DATA_DIR / "active_session.json"
    if session_file.exists():
        with open(session_file) as f:
            sess = json.load(f)
        sess["is_extracting"] = True
        with open(session_file, "w") as f:
            json.dump(sess, f, indent=2)

    def _extraction_task():
        try:
            extractor.batch_extract_from_taxonomy(req.segment, req.sector)
        finally:
            if session_file.exists():
                try:
                    with open(session_file) as f:
                        s = json.load(f)
                    s["is_extracting"] = False
                    with open(session_file, "w") as f:
                        json.dump(s, f, indent=2)
                except Exception:
                    pass

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _extraction_task)

    return {"status": "started", "sector": req.sector, "segment": req.segment,
            "component_count": component_count}


@app.post("/api/v1/rerun-extraction")
async def rerun_extraction(req: RerunExtractionRequest) -> Dict[str, Any]:
    """Wipe old extraction data and re-run for a past analysis."""
    import shutil
    extractor    = SupplyChainExtractor()
    sector_dir   = DATA_DIR / "sectors" / extractor._safe_name(req.sector) / extractor._safe_name(req.segment)

    if (sector_dir / "suppliers").exists():
        shutil.rmtree(sector_dir / "suppliers")
    if (sector_dir / "trade").exists():
        shutil.rmtree(sector_dir / "trade")

    tax_file        = sector_dir / "taxonomy.json"
    component_count = 0
    if tax_file.exists():
        with open(tax_file) as f:
            tax = json.load(f)

        def _count(node: dict) -> int:
            c = 1 if "leaf_id" in node else 0
            return c + sum(_count(ch) for ch in node.get("children", []))

        component_count = sum(_count(n) for n in tax.get("supply_chain", []))

    def _rerun():
        extractor.batch_extract_from_taxonomy(req.segment, req.sector)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _rerun)

    return {"status": "started", "sector": req.sector, "segment": req.segment,
            "component_count": component_count}


@app.post("/api/v1/archive-and-rerun")
async def archive_and_rerun(req: ArchiveRequest) -> Dict[str, Any]:
    """Archive current extraction data with timestamp, then start fresh extraction."""
    import shutil
    extractor  = SupplyChainExtractor()
    sector_dir = DATA_DIR / "sectors" / extractor._safe_name(req.sector) / extractor._safe_name(req.segment)

    if not sector_dir.exists():
        return {"status": "error", "message": "Segment directory not found."}

    # Create timestamped archive
    ts         = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_dir = sector_dir / "_archive" / ts
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Copy taxonomy, suppliers, trade into archive
    tax_file = sector_dir / "taxonomy.json"
    if tax_file.exists():
        shutil.copy2(tax_file, archive_dir / "taxonomy.json")
    for folder in ("suppliers", "trade"):
        src = sector_dir / folder
        if src.exists():
            shutil.copytree(src, archive_dir / folder)

    # Wipe current extraction data (keep taxonomy for re-run)
    for folder in ("suppliers", "trade"):
        tgt = sector_dir / folder
        if tgt.exists():
            shutil.rmtree(tgt)

    # Count components
    component_count = 0
    if tax_file.exists():
        with open(tax_file) as f:
            tax = json.load(f)
        def _count(node: dict) -> int:
            c = 1 if "leaf_id" in node else 0
            return c + sum(_count(ch) for ch in node.get("children", []))
        component_count = sum(_count(n) for n in tax.get("supply_chain", []))

    # Update session
    session_file = DATA_DIR / "active_session.json"
    session = {"sector": req.sector, "segment": req.segment, "region": "EU", "is_extracting": True}
    if session_file.exists():
        with open(session_file) as f:
            existing = json.load(f)
        existing["is_extracting"] = True
        session = existing
    with open(session_file, "w") as f:
        json.dump(session, f, indent=2)

    def _task():
        try:
            extractor.batch_extract_from_taxonomy(req.segment, req.sector)
        finally:
            if session_file.exists():
                try:
                    with open(session_file) as f:
                        s = json.load(f)
                    s["is_extracting"] = False
                    with open(session_file, "w") as f:
                        json.dump(s, f, indent=2)
                except Exception:
                    pass

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _task)

    return {"status": "started", "archived_as": ts, "component_count": component_count}


@app.post("/api/v1/discovery/{component}")
async def trigger_discovery(component: str) -> Dict[str, Any]:
    """Autonomous single-component discovery and extraction."""
    extractor = SupplyChainExtractor()
    session   = _get_active_session()
    sector    = (session or {}).get("sector",  "Quantum Computing")
    segment   = (session or {}).get("segment", "cryogenics")
    try:
        path = extractor.extract_component(component, sector=sector, segment=segment)
        if path:
            return {"status": "success", "component": component, "path": str(path)}
        return {"status": "error", "message": "Extraction returned no output."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/v1/so-what")
async def api_so_what(
    component: str,
    sector:    Optional[str] = None,
    segment:   Optional[str] = None,
    region:    Optional[str] = "EU",
) -> Dict[str, Any]:
    """
    LLM-generated 'So what?' policy brief for a component's risk situation.
    Returns a 2-3 sentence plain-English interpretation of the risk findings.
    """
    import os

    if sector and segment:
        data_dir = DATA_DIR / "sectors" / _safe_name(sector) / _safe_name(segment)
    else:
        session  = _get_active_session()
        data_dir = _get_sector_data_dir(session)

    try:
        from analytics import get_component_risk_metrics
        metrics = get_component_risk_metrics(component, region or "EU", data_dir=data_dir)
        if "error" in metrics:
            return {"text": f"Insufficient data to generate analysis for {component}.", "component": component}

        ps      = metrics["pillar_scores"]
        drivers = metrics["key_drivers"]
        raw     = metrics.get("raw", {})

        pillar_summary = ", ".join(f"{k}: {v:.2f}" for k, v in ps.items())
        driver_text    = ". ".join(drivers[:3]) if drivers else "No specific drivers identified."

        prompt = f"""You are a senior policy analyst at the European Commission advising on quantum technology supply chain security.

Analyze the supply chain risk for the component: **{component}**
Perspective: {region}
7-Pillar scores (0=safe, 1=critical): {pillar_summary}
Key risk drivers: {driver_text}
Russia exposure: {raw.get('russia_exposure', False)}, China exposure: {raw.get('china_exposure', False)}

Write a concise 2-3 sentence "So what?" policy brief. Focus on:
1. What the risk means in practical geopolitical terms
2. Which countries or actors create the most dependency
3. What a policymaker should consider doing

Be specific, factual, and professional. No bullet points. No preamble. Write in complete sentences."""

        provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
        if provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )
        else:
            from groq import Groq
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )

        text = resp.choices[0].message.content.strip()
        return {"text": text, "component": component}

    except Exception as e:
        return {"text": f"Analysis generation failed: {str(e)}", "component": component}


@app.get("/api/v1/compare-perspectives")
async def api_compare_perspectives(
    component: str,
    sector:    Optional[str] = None,
    segment:   Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return EU / US / China perspective comparison for a single component.
    Implements methodology section 5.3.
    """
    if sector and segment:
        data_dir = DATA_DIR / "sectors" / _safe_name(sector) / _safe_name(segment)
    else:
        session  = _get_active_session()
        data_dir = _get_sector_data_dir(session)
    return get_perspective_comparison(component, data_dir=data_dir)


@app.get("/graph/{component}")
def get_graph_data(component: str, region: str = "EU") -> Dict[str, Any]:
    session  = _get_active_session()
    data_dir = _get_sector_data_dir(session)
    return get_recursive_risk_metrics(component, region=region, data_dir=data_dir)


@app.post("/score")
def score(req: ScoreRequest) -> Dict[str, Any]:
    risk_score, drivers, confidence = score_component(req.region, req.segment, req.scenario)
    return {
        "region":     req.region,
        "segment":    req.segment,
        "scenario":   req.scenario,
        "risk_score": risk_score,
        "key_drivers": drivers,
        "confidence": confidence,
    }


@app.get("/api/v1/session-status")
async def session_status() -> Dict[str, Any]:
    """Lightweight poll endpoint for the dashboard to check extraction state."""
    session = _get_active_session()
    return {
        "is_extracting": bool((session or {}).get("is_extracting", False)),
        "is_paused":     bool((session or {}).get("is_paused", False)),
    }


@app.post("/api/v1/cancel-extraction")
async def cancel_extraction() -> Dict[str, Any]:
    """Write a cancel sentinel file that the extractor checks each iteration."""
    (DATA_DIR / ".pause_extraction").unlink(missing_ok=True)   # clear pause first
    (DATA_DIR / ".cancel_extraction").touch()
    session_file = DATA_DIR / "active_session.json"
    if session_file.exists():
        try:
            with open(session_file) as f:
                s = json.load(f)
            s["is_extracting"] = False
            s["is_paused"] = False
            with open(session_file, "w") as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass
    return {"status": "cancelled"}


@app.post("/api/v1/pause-extraction")
async def pause_extraction() -> Dict[str, Any]:
    """Write a pause sentinel file; extractor will hold after the current component."""
    (DATA_DIR / ".pause_extraction").touch()
    session_file = DATA_DIR / "active_session.json"
    if session_file.exists():
        try:
            with open(session_file) as f:
                s = json.load(f)
            s["is_paused"] = True
            with open(session_file, "w") as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass
    return {"status": "paused"}


@app.post("/api/v1/resume-extraction")
async def resume_extraction() -> Dict[str, Any]:
    """Delete the pause sentinel file; extractor continues automatically."""
    (DATA_DIR / ".pause_extraction").unlink(missing_ok=True)
    session_file = DATA_DIR / "active_session.json"
    if session_file.exists():
        try:
            with open(session_file) as f:
                s = json.load(f)
            s["is_paused"] = False
            with open(session_file, "w") as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass
    return {"status": "resumed"}


@app.post("/api/v1/extract-node")
async def extract_node(req: ExtractNodeRequest) -> Dict[str, Any]:
    """
    Run extraction for a single named component without touching the rest of the taxonomy.
    Fires in a background thread just like the full batch, so the request returns immediately.
    """
    extractor  = SupplyChainExtractor()
    sector_dir = DATA_DIR / "sectors" / _safe_name(req.sector) / _safe_name(req.segment)

    # Check if already extracted
    safe   = extractor._safe_name(req.component)
    outfile = sector_dir / "suppliers" / f"{safe}_suppliers.json"
    if outfile.exists():
        return {"status": "already_exists", "component": req.component, "file": str(outfile)}

    def _task():
        try:
            extractor.extract_component(req.component, sector=req.sector, segment=req.segment)
        except Exception as e:
            print(f"[!] extract-node failed for '{req.component}': {e}")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _task)

    return {"status": "started", "component": req.component}


@app.post("/api/v1/re-extract-component")
async def re_extract_component(req: ReExtractComponentRequest) -> Dict[str, Any]:
    """
    Delete existing supplier and trade files for a single component, then
    re-run extraction fresh. Lets users refresh stale data without touching
    the rest of the segment.
    """
    import shutil
    extractor  = SupplyChainExtractor()
    sector_dir = DATA_DIR / "sectors" / _safe_name(req.sector) / _safe_name(req.segment)
    safe       = extractor._safe_name(req.component)

    # Delete existing files for this component only
    (sector_dir / "suppliers" / f"{safe}_suppliers.json").unlink(missing_ok=True)
    (sector_dir / "trade"     / f"{safe}_trade_flows.json").unlink(missing_ok=True)

    def _task():
        try:
            extractor.extract_component(req.component, sector=req.sector, segment=req.segment)
        except Exception as e:
            print(f"[!] re-extract-component failed for '{req.component}': {e}")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _task)

    return {"status": "started", "component": req.component}


@app.get("/api/v1/node-score")
async def api_node_score(
    node_name: str,
    region: Optional[str] = "EU",
    scenario: Optional[str] = None,
    sector: Optional[str] = None,
    segment: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute risk score for any taxonomy node (leaf or branch).
    Branch nodes get the average score of all their descendant leaves.
    """
    if sector and segment:
        data_dir = DATA_DIR / "sectors" / _safe_name(sector) / _safe_name(segment)
    else:
        session  = _get_active_session()
        data_dir = _get_sector_data_dir(session)

    if not data_dir:
        return {"error": "No active session"}

    # Try direct leaf score first
    try:
        score, drivers, conf = score_component(region or "EU", node_name, scenario=scenario, data_dir=data_dir)
        return {
            "node": node_name,
            "score": score,
            "confidence": conf,
            "drivers": drivers[:3],
            "type": "leaf",
        }
    except Exception:
        pass

    # Branch node: find all descendant leaves via taxonomy
    tax_file = data_dir / "taxonomy.json"
    if not tax_file.exists():
        return {"error": "Taxonomy not found"}

    with open(tax_file) as f:
        taxonomy = json.load(f)

    def find_node(nodes, target_name):
        for node in nodes:
            if node.get("name", "").lower() == target_name.lower():
                return node
            result = find_node(node.get("children", []), target_name)
            if result:
                return result
        return None

    def collect_leaves(node):
        if "leaf_id" in node:
            return [node["name"]]
        leaves = []
        for child in node.get("children", []):
            leaves.extend(collect_leaves(child))
        return leaves

    target_node = find_node(taxonomy.get("supply_chain", []), node_name)
    if not target_node:
        # Fall back to treating all top-level nodes as children
        target_node = {"name": node_name, "children": taxonomy.get("supply_chain", [])}

    leaves = collect_leaves(target_node)
    if not leaves:
        return {"error": f"No leaf components found under '{node_name}'"}

    scores = []
    all_drivers = []
    for leaf in leaves:
        try:
            s, d, _ = score_component(region or "EU", leaf, scenario=scenario, data_dir=data_dir)
            scores.append(s)
            all_drivers.extend(d[:1])
        except Exception:
            pass

    if not scores:
        return {"error": "No scored leaf components found"}

    avg_score = round(sum(scores) / len(scores), 3)
    max_score = round(max(scores), 3)
    return {
        "node": node_name,
        "score": avg_score,
        "max_score": max_score,
        "leaf_count": len(scores),
        "confidence": "medium",
        "drivers": all_drivers[:3],
        "type": "branch",
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
