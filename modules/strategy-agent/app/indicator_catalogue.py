"""
indicator_catalogue.py — Live data fetcher for the Quantum Act IA pilot.

Sources:
  - Eurostat REST API (no auth required)
    Base: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/
  - CORDIS public search (no auth required)
    Base: https://cordis.europa.eu/search/results_en

All fetched values are returned as IndicatorValue objects with full provenance.
On fetch failure, falls back to a PROXY or ASSUMPTION value with a quality flag.
"""

import httpx
import logging
from typing import Optional

from app.schemas import IndicatorValue, SourceType, QualityFlag

logger = logging.getLogger(__name__)

EUROSTAT_BASE = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
)
CORDIS_SEARCH_BASE = "https://cordis.europa.eu/search/results_en"

# ─── Eurostat helpers ─────────────────────────────────────────────────────────

def _eurostat_url(dataset_code: str, params: dict) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{EUROSTAT_BASE}/{dataset_code}?format=JSON&lang=EN&{query}"


def _fetch_eurostat(
    dataset_code: str,
    params: dict,
    value_key: str,
) -> Optional[float]:
    """
    Fetch a single scalar value from a Eurostat dataset.
    Returns None on any error so callers can fall back gracefully.
    """
    url = _eurostat_url(dataset_code, params)
    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        values = list(data.get("value", {}).values())
        if values:
            return float(values[-1])          # most recent non-null value
        return None
    except Exception as exc:
        logger.warning("Eurostat fetch failed for %s: %s", dataset_code, exc)
        return None


# ─── CORDIS helper ────────────────────────────────────────────────────────────

def _fetch_cordis_project_count(keyword: str) -> Optional[int]:
    """
    Query the CORDIS public search for projects matching a keyword.
    Returns total hit count, or None on failure.
    """
    params = {
        "q":          keyword,
        "p":          "1",
        "num":        "1",
        "srt":        "/project/contentUpdateDate:decreasing",
        "format":     "json",
    }
    try:
        resp = httpx.get(CORDIS_SEARCH_BASE, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        # CORDIS returns {"totalHits": N, "results": [...]}
        return int(data.get("totalHits", 0))
    except Exception as exc:
        logger.warning("CORDIS fetch failed for keyword '%s': %s", keyword, exc)
        return None


def _fetch_cordis_total_funding(keyword: str) -> Optional[float]:
    """
    Approximate total EC contribution for projects matching a keyword.
    Sums ecMaxContribution across the first page of results (100 items).
    Returns value in millions EUR, or None on failure.
    """
    params = {
        "q":      keyword,
        "p":      "1",
        "num":    "100",
        "srt":    "/project/contentUpdateDate:decreasing",
        "format": "json",
    }
    try:
        resp = httpx.get(CORDIS_SEARCH_BASE, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        total = sum(
            float(r.get("ecMaxContribution", 0) or 0)
            for r in results
        )
        return round(total / 1_000_000, 2)    # convert to M EUR
    except Exception as exc:
        logger.warning("CORDIS funding fetch failed: %s", exc)
        return None


# ─── Public fetch functions ───────────────────────────────────────────────────

def fetch_gerd_total(geo: str = "EU27_2020") -> IndicatorValue:
    """
    Total intramural R&D expenditure (GERD) as % of GDP.
    Eurostat dataset: rd_e_gerdtot
    """
    value = _fetch_eurostat(
        "rd_e_gerdtot",
        {"geo": geo, "unit": "PC_GDP", "lastTimePeriod": "1"},
        value_key="value",
    )
    if value is not None:
        return IndicatorValue(
            indicator_id="gerd_pct_gdp",
            name="EU GERD as % of GDP",
            value=value,
            unit="% of GDP",
            source_type=SourceType.EUROSTAT,
            source_ref="eurostat:rd_e_gerdtot",
            quality_flag=QualityFlag.VERIFIED,
            note=f"Total R&D expenditure, {geo}, latest available year",
        )
    # fallback
    return IndicatorValue(
        indicator_id="gerd_pct_gdp",
        name="EU GERD as % of GDP",
        value=2.22,
        unit="% of GDP",
        source_type=SourceType.EUROSTAT,
        source_ref="eurostat:rd_e_gerdtot",
        quality_flag=QualityFlag.PROXY,
        note="Eurostat fetch failed; using 2022 published value as proxy",
    )


def fetch_rd_personnel(geo: str = "EU27_2020") -> IndicatorValue:
    """
    Total R&D personnel (researchers) as % of active population.
    Eurostat dataset: rd_p_persocc
    """
    value = _fetch_eurostat(
        "rd_p_persocc",
        {"geo": geo, "unit": "PC_ACT_POP", "sex": "T",
         "prof_pos": "TOTAL", "lastTimePeriod": "1"},
        value_key="value",
    )
    if value is not None:
        return IndicatorValue(
            indicator_id="rd_personnel_pct",
            name="EU R&D personnel as % of active population",
            value=value,
            unit="% active population",
            source_type=SourceType.EUROSTAT,
            source_ref="eurostat:rd_p_persocc",
            quality_flag=QualityFlag.VERIFIED,
            note=f"All sectors, both sexes, {geo}, latest available",
        )
    return IndicatorValue(
        indicator_id="rd_personnel_pct",
        name="EU R&D personnel as % of active population",
        value=1.43,
        unit="% active population",
        source_type=SourceType.EUROSTAT,
        source_ref="eurostat:rd_p_persocc",
        quality_flag=QualityFlag.PROXY,
        note="Eurostat fetch failed; using 2022 published value as proxy",
    )


def fetch_hightech_employment(geo: str = "EU27_2020") -> IndicatorValue:
    """
    Employment in high-technology sectors (% of total employment).
    Eurostat dataset: htec_emp_nat2
    """
    value = _fetch_eurostat(
        "htec_emp_nat2",
        {"geo": geo, "unit": "PC_EMP", "lastTimePeriod": "1"},
        value_key="value",
    )
    if value is not None:
        return IndicatorValue(
            indicator_id="hightech_employment_pct",
            name="EU high-tech employment as % of total employment",
            value=value,
            unit="% of total employment",
            source_type=SourceType.EUROSTAT,
            source_ref="eurostat:htec_emp_nat2",
            quality_flag=QualityFlag.VERIFIED,
            note=f"High-tech sectors, {geo}, latest available",
        )
    return IndicatorValue(
        indicator_id="hightech_employment_pct",
        name="EU high-tech employment as % of total employment",
        value=4.8,
        unit="% of total employment",
        source_type=SourceType.EUROSTAT,
        source_ref="eurostat:htec_emp_nat2",
        quality_flag=QualityFlag.PROXY,
        note="Eurostat fetch failed; using 2022 published value as proxy",
    )


def fetch_quantum_project_count() -> IndicatorValue:
    """
    Number of EU-funded projects with 'quantum' in title/description.
    Source: CORDIS public search.
    """
    count = _fetch_cordis_project_count("quantum")
    if count is not None:
        return IndicatorValue(
            indicator_id="cordis_quantum_projects",
            name="EU-funded quantum research projects (CORDIS)",
            value=float(count),
            unit="projects",
            source_type=SourceType.CORDIS,
            source_ref="cordis:search?q=quantum",
            quality_flag=QualityFlag.VERIFIED,
            note="Total CORDIS project hits for keyword 'quantum'",
        )
    return IndicatorValue(
        indicator_id="cordis_quantum_projects",
        name="EU-funded quantum research projects (CORDIS)",
        value=320.0,
        unit="projects",
        source_type=SourceType.CORDIS,
        source_ref="cordis:search?q=quantum",
        quality_flag=QualityFlag.PROXY,
        note="CORDIS fetch failed; using 2024 approximate count as proxy",
    )


def fetch_quantum_funding() -> IndicatorValue:
    """
    Approximate total EC funding for quantum projects (M EUR).
    Source: CORDIS public search, first 100 results.
    """
    funding = _fetch_cordis_total_funding("quantum")
    if funding is not None:
        return IndicatorValue(
            indicator_id="cordis_quantum_funding_meur",
            name="EU quantum project funding — sample total (M EUR)",
            value=funding,
            unit="M EUR",
            source_type=SourceType.CORDIS,
            source_ref="cordis:search?q=quantum",
            quality_flag=QualityFlag.PROXY,
            note=(
                "Sum of ecMaxContribution for top-100 CORDIS results. "
                "Proxy for total EU quantum R&D investment signal."
            ),
        )
    return IndicatorValue(
        indicator_id="cordis_quantum_funding_meur",
        name="EU quantum project funding — sample total (M EUR)",
        value=1200.0,
        unit="M EUR",
        source_type=SourceType.CORDIS,
        source_ref="cordis:search?q=quantum",
        quality_flag=QualityFlag.ASSUMPTION,
        note="CORDIS fetch failed; assumption based on Quantum Flagship budget",
    )


# ─── Master fetch ─────────────────────────────────────────────────────────────

def fetch_all_indicators(geo: str = "EU27_2020") -> list[IndicatorValue]:
    """
    Fetch all five Quantum Act pilot indicators.
    Returns a list ready to pass directly into AssessRequest.indicators.
    Failures fall back gracefully — never raises.
    """
    return [
        fetch_gerd_total(geo),
        fetch_rd_personnel(geo),
        fetch_hightech_employment(geo),
        fetch_quantum_project_count(),
        fetch_quantum_funding(),
    ]