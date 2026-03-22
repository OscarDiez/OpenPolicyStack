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
from datetime import date
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


# ─── Perspective definitions: allies and adversaries ─────────────────────────
# These determine how the AI reasons about supply chain exposure.
# Allies = trusted trading partners, low adversarial risk.
# Adversaries = countries whose control over a supply is a risk to this perspective.

PERSPECTIVE_CONTEXT = {
    "EU": {
        "description": "The European Union — 27-member trading bloc, heavily dependent on imported energy and critical raw materials.",
        "adversaries":  ["Russia", "China", "Iran", "Belarus", "North Korea"],
        "allies":       ["United States", "Canada", "Norway", "Australia", "Japan", "South Korea", "UK", "Switzerland"],
        "logic": (
            "From the EU's perspective: if a scenario disrupts supply from Russia or China, EU risk INCREASES sharply. "
            "If Russia or China is hurt by the scenario (e.g. loses EU buyers, forced to find new markets), "
            "EU risk may DECREASE because it reduces dependency leverage. "
            "If the scenario benefits the US or Norway (EU allies), EU risk is stable or improves slightly."
        ),
    },
    "US": {
        "description": "The United States — dominant global power, strong domestic production base but reliant on China for critical minerals.",
        "adversaries":  ["Russia", "China", "Iran", "North Korea", "Cuba"],
        "allies":       ["EU", "Canada", "UK", "Australia", "Japan", "South Korea", "Taiwan", "Israel"],
        "logic": (
            "From the US perspective: if a scenario disrupts supply from China or Russia, US risk INCREASES. "
            "If the scenario weakens China's export leverage (e.g. WTO action, allied reshoring), US risk DECREASES. "
            "Taiwan is a key ally but also a vulnerability — any Taiwan-related scenario raises US risk significantly. "
            "Canada and Australia are trusted alternative suppliers."
        ),
    },
    "CHINA": {
        "description": "China — the world's largest manufacturer, dominant in critical mineral refining, seeking supply security for inputs it does not produce domestically.",
        "adversaries":  ["United States", "Japan", "South Korea", "Taiwan", "Australia", "UK", "India"],
        "allies":       ["Russia", "Iran", "Belarus", "Pakistan", "Saudi Arabia", "Gulf states"],
        "logic": (
            "From China's perspective: China IS the dominant supplier for most critical minerals — it does not face supply risk for materials it controls. "
            "China's risk is UPSTREAM: materials it must IMPORT (e.g. iron ore from Australia, helium from the US, niobium from Brazil). "
            "If Russia is sanctioned by the EU/US, China BENEFITS — it gains leverage as Russia's largest alternative buyer. "
            "China's risk INCREASES if Western allies coordinate to restrict exports to China, or if Taiwan is destabilised. "
            "Do NOT score China's risk high for scenarios where China is the dominant supplier — that is the EU/US problem, not China's."
        ),
    },
    "GLOBAL": {
        "description": "Global perspective — no adversary set, measures systemic supply concentration risk only.",
        "adversaries":  [],
        "allies":       [],
        "logic": (
            "From a global perspective: risk reflects pure supply concentration and physical disruption risk, "
            "not geopolitical alignment. A shortage that affects all buyers equally scores high. "
            "A scenario that merely redistributes trade flows (e.g. Russia sells to China instead of EU) scores low globally."
        ),
    },
}


_SYSTEM_PROMPT = """You are a senior geopolitical supply chain risk analyst. Your job is to assess how a specific scenario changes supply chain risk for a specific geopolitical perspective.

CRITICAL RULES:
1. You must reason from the PERSPECTIVE given — not generically. Different perspectives face opposite risks from the same event.
2. If the perspective IS the dominant supplier of a component, their supply risk is LOW (they control it). Score delta near 0 or negative.
3. If the perspective LOSES a supplier due to the scenario, risk INCREASES (positive delta).
4. If the scenario forces an adversary to redirect supply toward the perspective (e.g. Russia needs new buyers → ships to China), risk DECREASES (negative delta) for that perspective.
5. If a scenario weakens an adversary's leverage over the perspective, risk DECREASES.
6. Use today's date and current geopolitical reality. Do not use outdated assumptions.
7. Be brutally honest. Do not soften deltas for diplomatic reasons.

Delta scale:
  +0.40 to +0.50 = catastrophic exposure (supply cut off, no alternatives)
  +0.25 to +0.39 = severe exposure (major disruption, hard to replace)
  +0.10 to +0.24 = moderate exposure (disruption but alternatives exist)
  +0.01 to +0.09 = minor exposure
   0.00          = no material effect
  -0.01 to -0.15 = modest benefit (gains leverage or alternative buyers)
  -0.16 to -0.30 = significant benefit (major supply advantage or reduced adversary leverage)

Output format: a single JSON object where each key is the exact component name and the value is:
{ "delta": float, "reasoning": "1-2 sentences grounding the score in supplier geography and current events", "sources": ["headline title if applicable"] }

Return ONLY valid JSON. No markdown. No explanation outside the JSON.
"""


def _build_user_prompt(
    scenario_label: str,
    scenario_description: str,
    perspective: str,
    components: List[Dict],
    news: List[Dict],
) -> str:
    today = date.today().strftime("%B %d, %Y")

    ctx = PERSPECTIVE_CONTEXT.get(perspective, PERSPECTIVE_CONTEXT["GLOBAL"])
    adversaries_str = ", ".join(ctx["adversaries"]) or "none defined"
    allies_str      = ", ".join(ctx["allies"])      or "none defined"

    news_block = "\n".join(
        f"  - [{n['title']}] {n['body']}"
        for n in news
    ) or "  No recent news retrieved."

    comp_block = "\n".join(
        f"  - {c['name']}: suppliers in {', '.join(c['countries']) or 'unknown'}"
        for c in components
    )

    return f"""TODAY'S DATE: {today}

SCENARIO: {scenario_label}
DESCRIPTION: {scenario_description}

PERSPECTIVE: {perspective}
Who this is: {ctx['description']}
Adversaries (supply from these = risk): {adversaries_str}
Allies (supply from these = safe): {allies_str}
How to reason for this perspective:
{ctx['logic']}

RECENT NEWS (as of {today}):
{news_block}

COMPONENTS TO SCORE (name: supplier countries):
{comp_block}

For each component above, compute the delta to its risk score caused by this scenario, reasoning strictly from the {perspective} perspective.
Remember: if {perspective} IS the dominant producer of a component, their risk does not increase — it may decrease.
Return a JSON object where each key is the component name exactly as listed above.
"""


def _extract_json(raw: str) -> Optional[Dict]:
    """
    Robustly extract a JSON object from LLM output.
    Handles: markdown fences, preamble text, trailing commas, unescaped quotes in values.
    """
    import re

    # Strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break

    # Find outermost { }
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end <= start:
        return None
    raw = raw[start:end]

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Remove trailing commas before } or ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Last resort: extract each component block individually using regex
    # Pattern: "ComponentName": { ... }
    result = {}
    pattern = re.compile(
        r'"([^"]+)"\s*:\s*\{([^{}]+)\}',
        re.DOTALL
    )
    for match in pattern.finditer(raw):
        key  = match.group(1)
        body = "{" + match.group(2) + "}"
        try:
            val = json.loads(body)
            result[key] = val
        except Exception:
            # Try to manually extract delta and reasoning
            delta_m     = re.search(r'"delta"\s*:\s*(-?[\d.]+)', body)
            reasoning_m = re.search(r'"reasoning"\s*:\s*"([^"]*)"', body)
            if delta_m:
                result[key] = {
                    "delta":     float(delta_m.group(1)),
                    "reasoning": reasoning_m.group(1) if reasoning_m else "",
                    "sources":   [],
                }

    return result if result else None


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
        return _extract_json(raw)
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

    # 1. Fetch news — use today's year for recency
    today_year = date.today().year
    news_query = f"{scenario_label} supply chain trade {today_year}"
    news = _fetch_news(news_query, max_results=8)
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
