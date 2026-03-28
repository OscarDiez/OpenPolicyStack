"""
streamlit_app.py — Strategy & Feedback Agent UI
Calls the live SFA service at localhost:8010.
Run with: python -m streamlit run modules/strategy-agent/streamlit_app.py
"""

import streamlit as st
import requests
import json
import pandas as pd

API_BASE = "http://localhost:8010"

st.set_page_config(
    page_title="EU Impact Assessment — Strategy & Feedback Agent",
    page_icon="🇪🇺",
    layout="wide",
)

# ─── Header ───────────────────────────────────────────────────────────────────

st.markdown("""
<div style='background-color:#003399;padding:20px 30px;border-radius:8px;margin-bottom:20px'>
    <h1 style='color:white;margin:0;font-size:24px'>🇪🇺 EU Impact Assessment — Strategy & Feedback Agent</h1>
    <p style='color:#FFCC00;margin:4px 0 0;font-size:13px'>
        Reusable, evidence-grounded IA artefacts · OpenPolicyStack · v0.3.0
    </p>
</div>
""", unsafe_allow_html=True)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def clean(text: str) -> str:
    """Replace unicode encoding artefacts with proper characters."""
    return (text
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .encode("ascii", "ignore").decode("ascii")
    )

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    scenario = st.selectbox(
        "Select scenario",
        ["baseline_v1", "adverse_v1", "recovery_v1"],
        format_func=lambda x: {
            "baseline_v1":  "📊 Baseline — current state",
            "adverse_v1":   "📉 Adverse — fiscal shock",
            "recovery_v1":  "📈 Recovery — rebound",
        }[x]
    )

    st.markdown("---")
    st.markdown("### 📡 Service status")

    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        if r.status_code == 200:
            st.success(f"✅ Service online — {r.json().get('version','')}")
        else:
            st.error("⚠️ Service returned an error")
    except Exception:
        st.error("❌ Service offline — start Docker first")
        st.code("docker run --rm -p 8010:8010 \\\n  -e ANTHROPIC_API_KEY=your-key \\\n  ops-strategy-agent")
        st.stop()

    run_btn = st.button("▶ Run Assessment", type="primary", use_container_width=True)
    pdf_btn = st.button("📄 Download PDF Brief", use_container_width=True)

    st.markdown("---")
    st.markdown("### 📖 About")
    st.markdown(
        "This tool automates EU Impact Assessment artefact production "
        "using live Eurostat and CORDIS data. "
        "All scores are traceable to the evidence payload."
    )

# ─── Scenario payloads ────────────────────────────────────────────────────────

SCENARIO_FILES = {
    "baseline_v1": "modules/strategy-agent/examples/assess_request_baseline.json",
    "adverse_v1":  "modules/strategy-agent/examples/assess_request_adverse.json",
    "recovery_v1": "modules/strategy-agent/examples/assess_request_recovery.json",
}

def load_scenario(scenario_id: str) -> dict:
    try:
        with open(SCENARIO_FILES[scenario_id], "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Scenario file not found: {SCENARIO_FILES[scenario_id]}")
        st.stop()

# ─── Session state ────────────────────────────────────────────────────────────

if "assess_result" not in st.session_state:
    st.session_state.assess_result = None
if "last_scenario" not in st.session_state:
    st.session_state.last_scenario = None

# ─── Run assessment ───────────────────────────────────────────────────────────

if run_btn or st.session_state.assess_result is None:
    payload = load_scenario(scenario)
    with st.spinner("Fetching live indicators and scoring options..."):
        try:
            r = requests.post(f"{API_BASE}/assess", json=payload, timeout=30)
            r.raise_for_status()
            st.session_state.assess_result = r.json()
            st.session_state.last_scenario = scenario
        except Exception as e:
            st.error(f"Assessment failed: {e}")
            st.stop()

result   = st.session_state.assess_result
scenario = st.session_state.last_scenario or scenario

# ─── PDF download ─────────────────────────────────────────────────────────────

if pdf_btn and result:
    brief_payload = {
        "run_id":        result["run_id"],
        "scenario_id":   result["scenario_id"],
        "option_scores": result["option_scores"],
        "drivers":       result["drivers"],
        "assumptions":   result["assumptions"],
        "evidence":      result["evidence"],
        "objective":     "EU Quantum Act option comparison",
    }
    with st.spinner("Generating PDF brief..."):
        try:
            r = requests.post(f"{API_BASE}/brief/pdf", json=brief_payload, timeout=30)
            r.raise_for_status()
            st.sidebar.download_button(
                label="📥 Click to download PDF",
                data=r.content,
                file_name=f"IA_Brief_{result['scenario_id']}.pdf",
                mime="application/pdf",
            )
            st.sidebar.success("PDF ready — click above to download!")
        except Exception as e:
            st.error(f"PDF generation failed: {e}")

# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 MCDA Scoring",
    "🔄 Sensitivity Analysis",
    "📝 Brief Comparison",
    "📋 Evidence & Provenance",
])

# ─── TAB 1: MCDA Scoring ──────────────────────────────────────────────────────

with tab1:
    scenario_labels = {
        "baseline_v1": "Baseline — current state",
        "adverse_v1":  "Adverse — fiscal shock",
        "recovery_v1": "Recovery — rebound",
    }
    st.markdown(f"### Option Scoring — {scenario_labels.get(scenario, scenario)}")
    st.markdown(f"**Run ID:** `{result['run_id']}` &nbsp;|&nbsp; **Scenario:** `{result['scenario_id']}`")

    options = sorted(result["option_scores"], key=lambda x: x["rank"])

    preferred = next((o for o in options if o["rank"] == 1), None)
    if preferred:
        st.success(
            f"✅ **Preferred option:** {clean(preferred['option_name'])} "
            f"(weighted score: **{preferred['weighted_total']:+.3f}**)"
        )

    criteria = ["economic", "social", "environmental", "competitiveness", "feasibility", "coherence"]

    rows = []
    for o in options:
        score_map = {cs["criterion"]: cs["score"] for cs in o["criteria_scores"]}
        status = str(o["status"]).replace("OptionStatus.", "").capitalize()
        row = {
            "Rank":    o["rank"],
            "Option":  clean(o["option_name"]),
            "Econ":    f"{score_map.get('economic', 0):+.1f}",
            "Social":  f"{score_map.get('social', 0):+.1f}",
            "Env":     f"{score_map.get('environmental', 0):+.1f}",
            "Comp":    f"{score_map.get('competitiveness', 0):+.1f}",
            "Feas":    f"{score_map.get('feasibility', 0):+.1f}",
            "Coh":     f"{score_map.get('coherence', 0):+.1f}",
            "Total":   f"{o['weighted_total']:+.3f}",
            "Status":  status,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.caption(
        "Scoring scale: -2 (strongly negative) to +2 (strongly positive). "
        "Weights: Economic 0.25, Competitiveness 0.25, Social 0.15, "
        "Feasibility 0.15, Environmental 0.10, Coherence 0.10."
    )

    # Key drivers
    st.markdown("### 🔑 Key Drivers — Preferred Option")
    drivers = result.get("drivers", [])
    if drivers:
        dcols = st.columns(len(drivers))
        for i, d in enumerate(drivers):
            with dcols[i]:
                direction_icon = "📈" if d["direction"] == "positive" else "📉"
                st.metric(
                    label=f"{direction_icon} {d['criterion'].capitalize()}",
                    value=f"{d['contribution']:.3f}",
                    help=d.get("source_ref") or "Domain knowledge"
                )

    # Per-option rationale
    st.markdown("### 📋 Scoring Rationale")
    for o in options:
        status = str(o["status"]).replace("OptionStatus.", "").capitalize()
        with st.expander(f"{clean(o['option_name'])} — Score: {o['weighted_total']:+.3f} ({status})"):
            for cs in o["criteria_scores"]:
                has_evidence = bool(cs.get("evidence_ids"))
                badge = "✅" if has_evidence else "⚠️"
                ev_str = ", ".join(cs["evidence_ids"]) if has_evidence \
                    else cs.get("assumption", "domain knowledge")
                st.markdown(
                    f"{badge} **{cs['criterion'].capitalize()}** "
                    f"({cs['score']:+.1f}): {cs['rationale']}  \n"
                    f"<small style='color:grey'>{'Evidence' if has_evidence else 'Assumption'}: {ev_str}</small>",
                    unsafe_allow_html=True
                )

# ─── TAB 2: Sensitivity Analysis ─────────────────────────────────────────────

with tab2:
    st.markdown("### 🔄 Weight Sensitivity Analysis")
    st.markdown(
        "Tests how option rankings change across four stakeholder weight scenarios. "
        "A stable ranking confirms the preferred option is robust to value assumptions."
    )

    sens_payload = {
        "run_id":        result["run_id"],
        "scenario_id":   result["scenario_id"],
        "option_scores": result["option_scores"],
    }

    with st.spinner("Running sensitivity analysis..."):
        try:
            sr = requests.post(f"{API_BASE}/sensitivity", json=sens_payload, timeout=15)
            sr.raise_for_status()
            sens = sr.json()

            stable  = sens.get("stable", False)
            summary = sens.get("summary", "")

            if stable:
                st.success(f"✅ {summary}")
            else:
                st.warning(f"⚠️ {summary}")

            # Summary table
            sens_rows = []
            for s in sens.get("results", []):
                rankings = sorted(s["option_rankings"], key=lambda x: x["rank"])
                top = rankings[0] if rankings else {}
                sens_rows.append({
                    "Weight Scenario": s["scenario_label"].replace("_", " ").title(),
                    "Preferred Option": clean(top.get("option_name", "—")),
                    "Score":           f"{top.get('score', 0):+.3f}",
                    "Stable":          "✅ Yes" if s["ranking_stable"] else "⚠️ No",
                })

            sens_df = pd.DataFrame(sens_rows)
            st.dataframe(sens_df, use_container_width=True, hide_index=True)

            # Colour-coded score matrix
            st.markdown("### Score matrix across weight scenarios")
            st.markdown(
                "Each cell shows the weighted score for that option under that weight scenario. "
                "🥇 = top-ranked option in that scenario."
            )

            # Build short option name mapping
            opt_short = {}
            for o in sorted(result["option_scores"], key=lambda x: x["rank"]):
                name = clean(o["option_name"])
                opt_short[o["option_name"]] = name[:28] + "..." if len(name) > 28 else name

            matrix_rows = []
            for s in sens.get("results", []):
                scenario_label = s["scenario_label"].replace("_", " ").title()
                rankings = sorted(s["option_rankings"], key=lambda x: x["rank"])
                top_score = rankings[0]["score"] if rankings else None
                row = {"Weight Scenario": scenario_label}
                for r in rankings:
                    short = opt_short.get(r["option_name"], r["option_name"])
                    score_str = f"{r['score']:+.3f}"
                    if r["score"] == top_score:
                        score_str = f"🥇 {score_str}"
                    row[short] = score_str
                matrix_rows.append(row)

            matrix_df = pd.DataFrame(matrix_rows).set_index("Weight Scenario")

            # Style the dataframe
            def highlight_gold(val):
                if isinstance(val, str) and val.startswith("🥇"):
                    return "background-color: #1a4a1a; color: #00cc44; font-weight: bold"
                return ""

            styled = matrix_df.style.applymap(highlight_gold)
            st.dataframe(styled, use_container_width=True)

            st.caption(
                "🥇 = preferred option under that weight scenario. "
                "Changes across rows indicate sensitivity to stakeholder value assumptions."
            )

        except Exception as e:
            st.error(f"Sensitivity analysis failed: {e}")

# ─── TAB 3: Brief Comparison ──────────────────────────────────────────────────

with tab3:
    st.markdown("### 📝 Brief Comparison — Deterministic vs LLM-Enhanced")
    st.markdown(
        "The **deterministic brief** is generated purely from structured fields — "
        "always consistent, fully traceable. "
        "The **LLM brief** uses Claude to rewrite the same structured data "
        "into more readable prose, constrained to no new facts."
    )

    brief_payload = {
        "run_id":        result["run_id"],
        "scenario_id":   result["scenario_id"],
        "option_scores": result["option_scores"],
        "drivers":       result["drivers"],
        "assumptions":   result["assumptions"],
        "evidence":      result["evidence"],
        "objective":     "EU Quantum Act option comparison",
    }

    col_det, col_llm = st.columns(2)

    with col_det:
        st.markdown("#### 🔧 Deterministic Brief")
        with st.spinner("Generating deterministic brief..."):
            try:
                dr = requests.post(f"{API_BASE}/brief", json=brief_payload, timeout=15)
                dr.raise_for_status()
                det_brief = dr.json().get("brief_markdown", "")
                st.markdown(det_brief)
            except Exception as e:
                st.error(f"Failed: {e}")

    with col_llm:
        st.markdown("#### 🤖 LLM-Enhanced Brief")
        with st.spinner("Generating LLM brief (may take a few seconds)..."):
            try:
                lr = requests.post(f"{API_BASE}/brief/llm", json=brief_payload, timeout=30)
                lr.raise_for_status()
                llm_brief = lr.json().get("brief_markdown", "")
                st.markdown(llm_brief)
            except Exception as e:
                st.error(f"Failed: {e}")

# ─── TAB 4: Evidence & Provenance ────────────────────────────────────────────

with tab4:
    st.markdown("### 📋 Evidence & Provenance Payload")
    st.markdown(
        "Every score in the MCDA table is linked to at least one indicator below, "
        "or carries an explicit assumption tag. "
        "Quality flags: ✅ **Verified** = official source, "
        "⚠️ **Proxy** = estimated fallback, "
        "❌ **Assumption** = no data available."
    )

    evidence = result.get("evidence", [])
    if evidence:
        ev_rows = []
        for e in evidence:
            flag = str(e.get("quality_flag", "")).replace("QualityFlag.", "").lower()
            flag_display = {
                "verified":   "✅ Verified",
                "proxy":      "⚠️ Proxy",
                "assumption": "❌ Assumption",
                "stale":      "⏰ Stale",
            }.get(flag, flag)

            ev_rows.append({
                "Indicator": e["indicator_id"],
                "Source":    e["source_ref"],
                "Value":     e.get("value", "—"),
                "Unit":      e.get("unit", "—"),
                "Quality":   flag_display,
                "Note":      e.get("note", ""),
            })

        ev_df = pd.DataFrame(ev_rows)
        st.dataframe(ev_df, use_container_width=True, hide_index=True)

    assumptions = result.get("assumptions", [])
    if assumptions:
        st.markdown("### ⚠️ Explicit Assumptions")
        st.markdown(
            "The following scores were assigned without direct indicator evidence, "
            "flagged in accordance with the 'no evidence → no claim' rule."
        )
        for a in assumptions:
            st.markdown(f"- {clean(a)}")

    with st.expander("🔍 View raw API response"):
        st.json(result)