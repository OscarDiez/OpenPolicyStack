"""
ai_scenario.py — Live AI-driven scenario scoring for SupplyTrace.

For each (segment, perspective, scenario) triple, this module:
  1. Fetches recent news headlines about the scenario topic via DuckDuckGo
  2. Calls Llama 3.3 70B (Groq) to reason about each component's exposure
  3. Returns a per-component dict: { delta, reasoning, sources }
  4. Caches results to disk for 24h so repeated loads are instant

Delta values are NOT softened — if a perspective is genuinely exposed,
the model is instructed to reflect that honestly.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

# ─── LLM client — Groq preferred, OpenAI fallback ────────────────────────────
_provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()

_groq_client   = None
_openai_client = None

if _provider == "groq":
    try:
        from groq import Groq
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    except Exception:
        pass
else:
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception:
        pass

GROQ_MODEL   = "llama-3.3-70b-versatile"
OPENAI_MODEL = "gpt-4o-mini"

try:
    from ddgs import DDGS as _DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS as _DDGS
    except ImportError:
        _DDGS = None

CACHE_TTL_SECONDS = 86400  # 24 hours

# ─── Cache helpers ────────────────────────────────────────────────────────────

def _cache_path(segment_dir: Path, perspective: str, scenario_key: str) -> Path:
    cache_dir = segment_dir / "_ai_scenario_cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"{perspective}_{scenario_key}.json"


def _load_cache(cache_file: Path) -> Optional[Dict]:
    if not cache_file.exists():
        return None
    try:
        with open(cache_file) as f:
            data = json.load(f)
        age = time.time() - data.get("_cached_at", 0)
        if age > CACHE_TTL_SECONDS:
            return None
        return data
    except Exception:
        return None


def _save_cache(cache_file: Path, data: Dict):
    data["_cached_at"] = time.time()
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)


# ─── News fetcher ─────────────────────────────────────────────────────────────

def _fetch_news(query: str, max_results: int = 6) -> List[Dict]:
    """Fetch recent headlines via DuckDuckGo. Returns list of {title, url, body}."""
    if _DDGS is None:
        return []
    try:
        results = []
        with _DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url":   r.get("url", ""),
                    "body":  r.get("body", "")[:300],
                })
        return results
    except Exception as e:
        print(f"[ai_scenario] News fetch failed: {e}")
        return []


# ─── Core reasoning ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a geopolitical supply chain risk analyst. You are brutally honest.
If a country or region is genuinely exposed to a supply disruption, say so clearly and score it high.
If a country or region actually BENEFITS from a disruption (e.g. gains leverage, gains new buyers),
score it lower or negative. Do not soften scores for political reasons.

You will be given:
- A supply chain scenario (e.g. EU sanctions on Russia)
- A geopolitical perspective (EU, US, CHINA, GLOBAL)
- A list of supply chain components with their supplier countries
- Recent news headlines about this scenario

For each component, output a JSON object with:
  "delta": float between -0.30 and +0.50 (negative = risk goes DOWN, positive = risk goes UP)
  "reasoning": 1-2 sentence explanation referencing the specific supplier geography
  "sources": list of 0-2 news headline titles that support your reasoning (empty list if none apply)

Be precise. A delta of 0.0 means the scenario has no effect on this component.
A delta of +0.45 means severe exposure. A delta of -0.20 means the perspective
actually benefits (e.g. China benefits when Russia needs new gas buyers).
"""

def _build_user_prompt(
    scenario_label: str,
    scenario_description: str,
    perspective: str,
    components: List[Dict],
    news: List[Dict],
) -> str:
    news_block = "\n".join(
        f"- {n['title']} ({n['url']}): {n['body']}"
        for n in news
    ) or "No recent news retrieved."

    comp_block = "\n".join(
        f"- {c['name']}: suppliers in {', '.join(c['countries']) or 'unknown'}"
        for c in components
    )

    return f"""SCENARIO: {scenario_label}
Description: {scenario_description}

PERSPECTIVE: {perspective}

RECENT NEWS:
{news_block}

COMPONENTS TO SCORE:
{comp_block}

Return a JSON object where each key is the component name (exactly as given above)
and the value is {{ "delta": float, "reasoning": "...", "sources": ["headline1", ...] }}.
Return ONLY valid JSON, no markdown, no explanation outside the JSON.
"""


def _call_llm(user_prompt: str) -> Optional[Dict]:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
    ]
    try:
        if _groq_client is not None:
            response = _groq_client.chat.completions.create(
                model=GROQ_MODEL, messages=messages, temperature=0.2, max_tokens=4096,
            )
        elif _openai_client is not None:
            response = _openai_client.chat.completions.create(
                model=OPENAI_MODEL, messages=messages, temperature=0.2, max_tokens=4096,
            )
        else:
            print("[ai_scenario] No LLM client available")
            return None

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"[ai_scenario] LLM call failed: {e}")
        return None


# ─── Public API ───────────────────────────────────────────────────────────────

def get_ai_scenario_deltas(
    segment_dir: Path,
    perspective: str,
    scenario_key: str,
    scenario_label: str,
    scenario_description: str,
    components: List[Dict],   # [{"name": str, "countries": [str]}]
    force_refresh: bool = False,
) -> Dict[str, Dict]:
    """
    Returns a dict keyed by component name:
      {
        "Methane":   {"delta": 0.35, "reasoning": "...", "sources": ["..."]},
        "Ethane":    {"delta": 0.18, "reasoning": "...", "sources": []},
        ...
      }

    Results are cached for 24h per (segment, perspective, scenario) triple.
    """
    cache_file = _cache_path(segment_dir, perspective, scenario_key)

    if not force_refresh:
        cached = _load_cache(cache_file)
        if cached:
            print(f"[ai_scenario] Cache hit: {cache_file.name}")
            cached.pop("_cached_at", None)
            return cached

    print(f"[ai_scenario] Computing live deltas for {scenario_key} / {perspective} ...")

    # 1. Fetch news
    news_query = f"{scenario_label} supply chain commodities 2025 2026"
    news = _fetch_news(news_query, max_results=6)
    print(f"[ai_scenario] Fetched {len(news)} news items")

    # 2. Build prompt and call LLM
    user_prompt = _build_user_prompt(
        scenario_label=scenario_label,
        scenario_description=scenario_description,
        perspective=perspective,
        components=components,
        news=news,
    )

    result = _call_llm(user_prompt)

    if result is None:
        print("[ai_scenario] LLM failed, returning empty deltas")
        return {}

    # 3. Clamp deltas to [-0.30, +0.50] and ensure correct structure
    cleaned = {}
    for comp_name, val in result.items():
        if not isinstance(val, dict):
            continue
        delta = float(val.get("delta", 0.0))
        delta = max(-0.30, min(0.50, delta))
        cleaned[comp_name] = {
            "delta":     round(delta, 3),
            "reasoning": str(val.get("reasoning", "")),
            "sources":   list(val.get("sources", [])),
        }

    # 4. Save to cache
    _save_cache(cache_file, cleaned)
    print(f"[ai_scenario] Cached {len(cleaned)} component deltas to {cache_file.name}")

    return cleaned


def get_component_ai_delta(
    ai_deltas: Dict[str, Dict],
    component_name: str,
) -> Dict:
    """
    Look up a component's AI delta by name. Tries exact match first,
    then case-insensitive, then partial match.
    Returns {"delta": 0.0, "reasoning": "", "sources": []} if not found.
    """
    empty = {"delta": 0.0, "reasoning": "", "sources": []}

    if component_name in ai_deltas:
        return ai_deltas[component_name]

    lower = component_name.lower()
    for k, v in ai_deltas.items():
        if k.lower() == lower:
            return v

    for k, v in ai_deltas.items():
        if lower in k.lower() or k.lower() in lower:
            return v

    return empty
