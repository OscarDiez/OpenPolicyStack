# OpenPolicyStack: Quantum Strategic Risk Dashboard

## Summary
The Quantum Strategic Risk Dashboard is an autonomous intelligence engine designed to assess supply-chain vulnerabilities for critical technologies (e.g., Cryogenics, Photonics). By aggregating unstructured web data and trade statistics via large language models, it visualizes macro-level geopolitical risks and single points of failure. This matters because it transforms opaque, global procurement networks into transparent, perspective-driven metrics, empowering security analysts to mitigate recursive supply chain risks before they disrupt critical infrastructure. 

## My Role & Ownership
**Role:** Product Designer (Developer Experience) & Core Developer.
**Ownership:** I owned the end-to-end design and implementation of the data extraction pipeline and the interactive dashboard. Specifically, I designed the LLM-powered supplier intelligence extraction workflow (`extractor.py`), engineered the risk-scoring algorithm (`scoring.py`), and built the FastAPI-driven frontend. In addition, I defined the primary developer workflows for adding new components to the taxonomy and configuring geopolitical logic for dynamic risk analysis. I did not focus on production infrastructure deployment or massive-scale data orchestration, deliberately keeping MVP architecture lean and local.

## Developer Workflows
The system was designed with developer experience at the forefront, turning complex data ingestion into straightforward CLI workflows:
- **Autonomous Intelligence Discovery**: A streamlined workflow allowing users to input a component (e.g., `python src/extractor.py --component "Helium-3"`), instantly triggering a pipeline that semantically scrapes the web, extracts supplier entities, and outputs normalized JSON.
- **Batch Processing by Taxonomy**: For scaling up investigations, analysts can target entire segments (`--batch --segment cryogenics`), mapping multi-tier components automatically into a centralized data directory.
- **Configurable Geopolitical Context**: A simple developer model where "adversaries" and security policies can be updated in a single file (`analytics.py`). The engine instantly recalculates risk scores based on who is running the analysis, making it a highly adaptable security framework.

## Interface and Interaction Decisions
- **Perspective-Driven Design**: The dashboard features a sleek, dark-mode, "glassmorphic" interface (`app.py`) built to highlight critical bottlenecks with clear, color-coded confidence indicators (Low/Medium/High risk).
- **Macro over Micro Mapping**: Instead of cluttering the UI with exact factory pins, the map visualization evolved to highlight entire supplier countries using Leaflet and GeoJSON contours. This instantly communicates absolute geopolitical risk, minimizing visual noise.
- **Progressive Disclosure**: To manage cognitive load, Risk Drivers and granular supplier tables are hidden by default. They are revealed conditionally inline—alongside the interactive map—only when a user clicks on an impacted component.
- **In-Dashboard Discovery**: The search bar doubles as a triggering mechanism for new LLM extractions. If a component is missing, entering it initiates the autonomous discovery workflow directly from the browser instance.

## Technical Structure
The architecture was kept minimalist to ensure transparency and reproducibility:
- **Frontend**: A singular, lightweight HTML/CSS/JS interface served via **FastAPI**, incorporating **Leaflet.js** for map rendering without heavy frontend frameworks.
- **Backend Analytics engine**: A **Python**-based scoring module utilizing network dependency graphs to calculate recursive risk and propagate single-point failures upstream.
- **Data Pipeline**: The extraction engine interacts with the **Groq API** (Llama 3.1) for high-speed unstructured web entity extraction, enriched iteratively through predefined JSON schemas.

## Screen Capture Suggestions
To best frame this case study visually, I recommend capturing the following screenshots:
1. **The Hero (Top Half of Dashboard):** Capture the glowing "Quantum Strategic Risk Dashboard" title, the central search bar, and the high-level KPI stat grid (Components Tracked, Average Risk, High-Risk Bottlenecks). 
   *Focus: Initial impact, dark-mode aesthetics, and simplicity.*
![Hero Section](/Users/karlmaximilienkohler/.gemini/antigravity/brain/cda06e20-f6b2-497c-9064-18b8a616ac28/hero_screenshot_1772478371338.png)
2. **The Intelligence Table:** Capture the main Risk Table outlining Component, Strategic Risk (with the progress bars), Confidence badges, and Primary Risk Drivers bullet points. 
   *Focus: Information architecture and readable data syntax.*
![The Intelligence Table](/Users/karlmaximilienkohler/.gemini/antigravity/brain/cda06e20-f6b2-497c-9064-18b8a616ac28/table_screenshot_1772478398864.png)
3. **The Deep-Dive Drawer (Expanded Row):** Click on a high-risk component (e.g., `Helium-3`) to open the expanded drawer. Capture the 50/50 split showing the "Identified Producers" scrolling list on the left alongside the stark dark-mode Leaflet Map highlighting supplier countries in bright blue on the right. 
   *Focus: The progressive disclosure interaction and visual mapping decision.*
![The Deep-Dive Drawer](/Users/karlmaximilienkohler/.gemini/antigravity/brain/cda06e20-f6b2-497c-9064-18b8a616ac28/drawer_screenshot_1772478424489.png)
4. **The Developer Workflow (Terminal Snapshot):** Grab a clean screenshot of your VS Code terminal running `python src/extractor.py --component "Helium-3"` and showing the JSON extraction success output. 
   *Focus: DX and the "magic" behind the autonomous intelligence.*

## Reflection
**Impact:** I successfully transformed a theoretical supply chain problem into a functioning, perspective-based intelligence tool. The largest win was bridging the gap between unstructured geopolitical events on the web and a strict, quantifiable data schema that directly informs the user's dashboard.

**What I'd Improve:** Currently, the system relies seamlessly on flat JSON files acting as pseudo-databases. For the next phase of scale, I'd abstract this into a proper graph database (like Neo4j) to support infinitely deep n-tier supplier mapping. On the frontend, polling for extraction state via reloading could be upgraded to a real-time WebSocket connection to give analysts instant feedback on the data ingestion process.
