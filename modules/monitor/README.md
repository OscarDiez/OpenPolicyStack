## Monitor Module (EFMO – European Funding Monitor)

### 1. Purpose & Scope

**Problem it solves**

The monitor module (EFMO) automates monitoring of EU-funded projects for specific technology domains (quantum, HPC, AI, cybersecurity). It:

- **Ingests** projects and organizations from the EU Funding & Tenders Portal  
- **Filters** them by topic using keyword-based scoring and (optionally) LLM-based categorization  
- **Aggregates & analyzes** funding and participation over time  
- **Publishes** the processed data as SQLite databases and figures for dashboards and reporting  

**Policy questions it helps answer (per topic)**

Examples (for quantum, but analogous for HPC/AI/cybersecurity):

- How much EU funding is going into *quantum computing* vs *quantum sensing* vs *quantum communication* over time?
- Which countries and organization types are most active in this topic?
- How is the portfolio evolving (TRL distribution, platforms, applications)?
- What new relevant projects have appeared since the last run?

**When the orchestrator should call it**

- **Do call** when:
  - You want to **refresh topic dashboards / analytics** (e.g. daily, weekly).
  - Raw source data has been updated (sourcing workflow has run recently).
  - You need an updated **topic-specific snapshot** for a briefing or policy question.

- **Do *not* call** when:
  - You need **ad‑hoc, per-request analytics** on a small set of projects (better to query the DB directly).
  - You don’t have valid **EU portal API credentials** (for sourcing) or the network is constrained.
  - You cannot or do not want to incur **LLM costs** and you strictly require LLM-derived categories (e.g. “quantum computing” vs “basic science”).

At a high level: **orchestrator should treat this as a scheduled batch job** that periodically refreshes topic-specific funding intelligence, not as an interactive microservice.

---

### 2. Invocation Contract

**Current invocation options**

1. **Python API (recommended for orchestrator)**

For a given topic (e.g. quantum):

```python
from modules.monitor.data_workflows import MonitorWorkflow, DataSourcingWorkflow
from modules.monitor.workflow_settings import (
    sourcing_settings,
    quantum_settings,
    hpc_settings,
    ai_settings,
    cybersecurity_settings,
)

# One-time / periodic sourcing (raw data from EU API)
sourcing = DataSourcingWorkflow("sourcing", sourcing_settings)
sourcing.run()

# Topic-specific monitor run, using sourced data
quantum = MonitorWorkflow("quantum", quantum_settings)
quantum.run()
```

This is the **most deterministic** way for the orchestrator to trigger runs: you explicitly choose which workflow to run and when.

2. **Scheduler script**

```bash
cd modules/monitor
pipenv run python scheduler.py
```

- Uses `ENV` env var (`dev` vs `prod`) to decide behavior.
- In `prod` it uses `schedule` to run multiple workflows at fixed UTC times.
- In `dev` it currently runs the quantum workflow once and then loops.

For an orchestrator, this is more of a **standalone daemon**; less granular than calling workflows directly.

**Recommended invocation contract for the orchestrator**

Treat the monitor as a Python module with **two primary entrypoints**:

- `run_sourcing()` – refresh raw data from EU portal.
- `run_monitor(topic, options)` – run one topic workflow with explicit options.

Conceptually:

```python
def run_sourcing():
    DataSourcingWorkflow("sourcing", sourcing_settings).run()

def run_monitor(topic: str, *, use_llm: bool = True):
    settings_map = {
        "quantum": quantum_settings,
        "hpc": hpc_settings,
        "ai": ai_settings,
        "cybersecurity": cybersecurity_settings,
    }
    settings = settings_map[topic]
    # Orchestrator sets settings.suppress_llm_categorization as needed
    MonitorWorkflow(topic, settings).run()
```

This keeps **triggering deterministic**: the orchestrator always specifies `{workflow, topic, use_llm}` explicitly.

---

### 3. Input Schema

The module does **not** currently consume a JSON payload; its “inputs” are:

- **Configuration classes** in `workflow_settings.py` (per-topic settings)
- **Environment variables**:
  - `SEDIA_API_KEY` (EU Funding & Tenders Portal API) – required for sourcing
  - `lite_llm_url`, `lite_llm_model`, `lite_llm_api_key` – required if LLM categorization is enabled
  - `hook_teams` – required if Teams newsletter is enabled
- **Existing files**:
  - Raw data pickles (after sourcing)
  - Optional manual CSV inputs

For orchestration purposes, you can conceptualize a **run request** as a JSON config that drives how you call the Python API.

#### Proposed run request JSON (for orchestrator)

```json
{
  "workflow": "monitor",
  "topic": "quantum",
  "mode": "full",
  "use_llm": true,
  "suppress_ft_crawl": false,
  "import_manual_data": true,
  "send_deliverable": false,
  "send_newsletter": true
}
```

#### JSON Schema (proposed)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MonitorRunRequest",
  "type": "object",
  "required": ["workflow", "topic", "mode"],
  "properties": {
    "workflow": {
      "type": "string",
      "enum": ["sourcing", "monitor"],
      "description": "Which workflow to run."
    },
    "topic": {
      "type": "string",
      "enum": ["quantum", "hpc", "ai", "cybersecurity"],
      "description": "Topic-specific monitor to run (ignored for pure sourcing)."
    },
    "mode": {
      "type": "string",
      "enum": ["full", "no_llm"],
      "description": "Whether to include LLM categorization."
    },
    "use_llm": {
      "type": "boolean",
      "default": true,
      "description": "Convenience flag; equivalent to mode != 'no_llm'."
    },
    "suppress_ft_crawl": {
      "type": "boolean",
      "default": false,
      "description": "If true, sourcing reuses cached raw data instead of hitting the EU API."
    },
    "import_manual_data": {
      "type": "boolean",
      "default": false,
      "description": "Whether to merge manual CSVs into the dataset."
    },
    "send_deliverable": {
      "type": "boolean",
      "default": false,
      "description": "Whether to zip deliverables and send (currently email delivery is disabled)."
    },
    "send_newsletter": {
      "type": "boolean",
      "default": false,
      "description": "Whether to send a Teams newsletter with new projects."
    }
  },
  "additionalProperties": false
}
```

**Mandatory inputs for a successful run**

- For **sourcing**:
  - `workflow = "sourcing"`
  - Valid `SEDIA_API_KEY` in environment
- For **monitor**:
  - `workflow = "monitor"`
  - `topic` in allowed set
  - Raw data files present (sourcing has been run previously)
  - If `mode = "full"` / `use_llm = true`: valid `lite_llm_*` env vars and connectivity

The orchestrator can validate this JSON against the schema before calling the Python API.

---

### 4. Output Contract

**Output types**

1. **Intermediate data files (per topic)** – under `modules/monitor/data/{topic}/`
   - `filtered_projects.csv`
   - `filtered_organizations.csv`
   - `filtered_projects_prev.csv`
   - `processed_projects_diff.csv`
   - `matchscore_histogram.png`
   - Optional: `input_manual_projects.csv`, `input_manual_orgas.csv` (orchestrator / human-managed)

   These are **intermediate analysis products** – suitable for exploration, debugging, or feeding other data pipelines.

2. **SQLite database (per topic)** – under `modules/monitor/deliverables/{topic}/`
   - `{topic}.db` with tables:
     - `projects` – cleaned project-level data (including LLM-based dimensions if enabled)
     - `organizations` – organization-level data
     - `metadata` – run metadata (timestamps, keywords, thresholds, prompt)

   This is the **primary machine-consumable output** for downstream dashboards or analytics.

3. **Evaluation artifacts (per topic)** – under `modules/monitor/deliverables/{topic}/`
   - PNG plots:
     - `TotalFundingByFPOverTime.png`
     - `TotalFundingByLLMCategoryOverTime.png` (requires LLM categories)
     - `OrganizationsByCountryGroupOverTime.png`
     - `OrganizationTypeByCountryGroupOverTime.png`
     - `TotalFundingbyFP.png`
   - JSON results:
     - `TotalFundingByFPOverTime.json`
     - `TotalFundingByLLMCategoryOverTime.json` (requires LLM)
     - `OrganizationsByCountryGroupOverTime.json`
     - `OrganizationsByCountryGroupOverTime_absolute.json`
     - `OrganizationTypeByCountryGroupOverTime.json`
     - `TotalFundingbyFP.json`

   These are **intermediate / analytic outputs** – suitable for dashboards and human interpretation, but still “data-level”, not narrative policy briefs.

4. **Notifications (optional)**

- Teams messages (if `send_newsletter = true` and `hook_teams` configured) listing newly added projects in a given topic.

**Final vs intermediate**

- **Final, policy-ready data for other modules**:
  - The **SQLite DBs** (and their JSON summaries) – these should be treated as the canonical, versioned outputs that downstream modules (or the orchestrator) consume.
- **Intermediate**:
  - CSVs in `data/{topic}/`
  - PNG plots in `deliverables/{topic}/`
  - Logs and temporary `.dat` files

The orchestrator should primarily depend on **existence and freshness of `{topic}.db`** (plus metadata table) as the success signal and downstream interface.

---

### 5. Determinism & Reproducibility

**Is it deterministic given the same inputs?**

Not fully, because:

- **External data source**:
  - Sourcing hits the live EU Funding & Tenders Portal API. The dataset changes over time.
- **Time-based filters**:
  - New-project detection filters by `ecSignatureDate` within the last 4 weeks, using `datetime.now()`.
- **LLM categorization**:
  - Calls a remote LLM API; outputs can vary slightly run-to-run even for the same prompt.

Given completely frozen inputs (frozen raw data files, fixed env vars, same code version) and **LLM disabled**, the keyword-based parts are deterministic.

**Randomness**

- No explicit RNG usage; non-determinism comes from:
  - Network APIs (EU portal + LLM provider)
  - Current wall-clock time
  - Possible non-determinism in remote LLM

**Logging & metadata**

- Logging:
  - `scheduler.py` configures logging to `scheduler.log` + stdout:
    - Logs environment configuration (`ENV`, `lite_llm_*` prefixes)
    - Logs workflow execution and keep-alive heartbeat.
  - Other modules (`data_sourcing.py`, `data_processing.py`, `data_workflows.py`) use `logging` to record progress and errors.

- Metadata in outputs:
  - `metadata` table in each `{topic}.db` contains:
    - `DataAnalysisStartDate`
    - `DataAnalysisEndDate`
    - `categorization_prompt`
    - `keyword_list`
    - `matchscore_threshold`
  - This is sufficient to reconstruct *how* the run was configured.

- Not currently logged:
  - Git commit hash
  - Exact version of dependencies or OS
  - Exact LLM model version (beyond model name string)

**For orchestrator-managed reproducible runs**

To move towards reproducible “Runs”, the orchestrator should:

- Capture and store:
  - Code revision / commit hash for each run
  - Full monitor run request (the JSON described above)
  - Environment snapshot for key variables (e.g., `SEDIA_API_KEY` omitted, but flags & URLs kept)
- Optionally, disable LLM (`mode = "no_llm"`) for runs where strict determinism is a requirement.

---

### 6. Runtime & Failure Modes

**Common runtime dependencies**

- Network connectivity to:
  - EU Funding & Tenders Portal API (`SEDIA_API_KEY`).
  - Remote LLM endpoint (`lite_llm_url`) if LLM is enabled.
  - Microsoft Teams webhook (`hook_teams`) if newsletters are enabled.
- Filesystem write access under `modules/monitor/data/` and `modules/monitor/deliverables/`.

**Typical failure modes**

1. **Missing or invalid credentials**
   - `SEDIA_API_KEY` not set → sourcing fails with HTTP error or “unauthorized”.
   - `lite_llm_*` not set but `suppress_llm_categorization = False` → LLM categorization step raises an exception from the OpenAI client.
   - `hook_teams` not set but `send_newsletter = True` → Teams delivery fails; logged error.

   *Signal to orchestrator*: Non-zero exit code from the Python process, error entries in logs, and **missing or stale `{topic}.db`**.

2. **Network / API issues**
   - EU API timeouts, connection errors, or malformed JSON:
     - Handled via retry loops with sleep; if retries exhausted, particular chunks/codes are skipped and logged.
   - LLM API rate limits or errors:
     - Retried with exponential backoff (`make_chat_completion`), ultimately returning empty responses on hard failure.

   *Consequence*: Partial data download or incomplete categorization; outputs may exist but be incomplete. Orchestrator should treat “missing DB” or DB without fresh metadata as a failure signal.

3. **Missing intermediate files**
   - If `suppress_llm_categorization = True` but no previously generated `filtered_projects.csv` / `filtered_organizations.csv` exist, the monitor workflow will fail on:
     - `pd.read_csv(self.settings.filtered_projects_filename, ...)`

   *Mitigation*: As orchestrator, enforce ordering:
   - Always run sourcing + full monitor at least once to create baseline filtered files.
   - Or modify the module (future enhancement) to support a “keyword-only, no-LLM” path that still writes required files.

4. **Data shape / schema drift**
   - The EU portal API might change field names or structure.
   - This can cause:
     - KeyErrors when building DataFrames
     - Issues in evaluation logic that assumes certain columns.

   *Signal*: Python exceptions in `data_sourcing.py` or `data_evaluation.py`, logged with stack traces.

5. **Disk / SQLite issues**
   - Insufficient disk space or permissions when writing:
     - CSVs in `data/{topic}/`
     - DBs in `deliverables/{topic}/`
   - SQLite `to_sql` failures.

   *Signal*: Exceptions during DB write; absence or partial creation of `{topic}.db`.

6. **Long runtimes**
   - Sourcing can take **hours** due to thousands of EU API requests.
   - LLM categorization can also take hours because of rate limits and per-project calls.

   *Operational implications*:
   - Orchestrator should run these as **background jobs** with timeouts and monitoring.
   - Avoid scheduling overlapping LLM-heavy workflows (as noted in `docs/scheduler.md`).

**Failure signaling pattern the orchestrator can rely on**

- **Hard failure (run considered failed)**:
  - Python process exits with error.
  - Missing or unchanged `{topic}.db` or `metadata` timestamps after the run.

- **Soft / partial failure (run completes but data incomplete)**:
  - `{topic}.db` exists but:
    - `metadata` shows errors in logs (or missing expected fields).
    - Evaluations relying on `LLMCategory` are missing when LLM was expected.

For robust orchestration, you should:

- Treat “fresh `{topic}.db` + updated `metadata` timestamp” as the **success condition**.
- Inspect `scheduler.log` or per-run logs when that condition is not met.
- Optionally, enforce timeouts and retry policies at the orchestrator level.


