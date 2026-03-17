import json
from pathlib import Path
from typing import Dict, List, Any

def calculate_hhi(shares: List[float]) -> float:
    """
    Calculate the Herfindahl-Hirschman Index (HHI).
    Input shares should be decimals (e.g., 0.509 for 50.9%).
    Result is on a 0-10,000 scale.
    """
    return sum((share * 100) ** 2 for share in shares)

def get_component_risk_metrics(component: str, region: str = "US", data_dir: Path = None) -> Dict[str, Any]:
    """
    Level 3 Analytics: Calculates 7-Pillar risk metrics from registries.
    Pillar 1 (HHI) and Pillar 2 (Geopolitics) are now CALIBRATED using trade flows.
    Accepts an optional data_dir to support per-sector folder isolation.
    """
    base_dir = data_dir or (Path(__file__).resolve().parents[1] / "data")
    safe_name = component.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
    
    supplier_file = base_dir / "suppliers" / f"{safe_name}_suppliers.json"
    trade_file = base_dir / "trade" / f"{safe_name}_trade_flows.json"
    
    if not supplier_file.exists():
        return {"error": f"No registry found for {component}"}

    with open(supplier_file, "r") as f:
        supp_data = json.load(f)
    
    trade_data = None
    if trade_file.exists():
        with open(trade_file, "r") as f:
            trade_data = json.load(f)

    suppliers = supp_data.get("suppliers", [])
    real_suppliers = [s for s in suppliers if s.get("name") != "GLOBAL_INDUSTRY_TOTAL"]
    notes_blob = " ".join([s.get("strategic_notes") or "" for s in suppliers]).lower()
    
    if not real_suppliers:
        return {"error": "Empty registry"}

    # --- PILLAR 1: Market Concentration (HHI) ---
    # NEW LOGIC: Use Trade Data if available for volume-weighting
    if trade_data and trade_data.get("exporters"):
        shares = [e.get("share", 0) for e in trade_data["exporters"]]
        hhi = calculate_hhi(shares)
        n = len(trade_data["exporters"])
    else:
        # Fallback to naive entity count
        n = len(real_suppliers)
        hhi = calculate_hhi([1.0/n] * n)
        if n <= 2: hhi = max(hhi, 5000)
    
    p1_score = min(1.0, hhi / 10000 + 0.1)

    # --- PILLAR 2: Geopolitics ---
    r_region = region.upper()
    adversaries = ["RUSSIA", "CHINA", "IRAN", "NORTH KOREA", "RUSSIAN FEDERATION"]
    
    if trade_data and trade_data.get("exporters"):
        # Calculate adversarial share of world exports
        adversary_share = sum([e.get("share", 0) for e in trade_data["exporters"] 
                               if e.get("country", "").upper() in adversaries])
        p2_score = 0.2 + (0.75 * adversary_share) if r_region in ["US", "EU", "UK"] else 0.2
        countries = [e.get("country") for e in trade_data["exporters"]]
    else:
        countries = [s.get("country") or "Unknown" for s in real_suppliers]
        has_adversary = any(c.upper() in adversaries for c in countries if isinstance(c, str))
        p2_score = 0.8 if has_adversary and r_region in ["US", "EU", "UK"] else 0.2

    # --- PILLAR 3: Shelf-Life / Perishability ---
    p3_score = 0.1
    if "helium-3" in component.lower() or "he-3" in component.lower():
        p3_score = 0.55 # Reflects the 5.5% annual decay risk

    # --- PILLAR 4: Substitutability ---
    bespoke_keywords = ["custom", "fridge", "mixing", "superconducting", "bespoke", "chamber"]
    is_bespoke = any(k in component.lower() for k in bespoke_keywords)
    p4_score = 0.8 if is_bespoke else 0.3

    # --- PILLAR 5: Lead-Time & Logistics ---
    p5_score = 0.4
    if is_bespoke or "magnet" in component.lower():
        p5_score = 0.85 # High lead-time for custom engineering

    # --- PILLAR 6: Regulatory & Export ---
    p6_score = 0.2
    reg_keywords = ["itar", "dual-use", "export control", "license", "regulated"]
    if any(k in notes_blob for k in reg_keywords):
        p6_score = 0.9

    # --- PILLAR 7: Strategic Impact ---
    p7_score = 0.5
    core_keywords = ["chamber", "pump", "fridge", "helium-3", "magnet", "wire"]
    if any(k in component.lower() for k in core_keywords):
        p7_score = 0.95 # Life-blood components

    # --- 📈 COLLECT HIGH-FIDELITY DRIVERS ---
    drivers = []
    
    # Extract top companies for dynamic text
    top_suppliers_names = [s.get("name") for s in real_suppliers[:2] if s.get("name")]
    top_sup_str = ", ".join(top_suppliers_names) if top_suppliers_names else "major suppliers"
    
    if p1_score > 0.6:
        label = "Volume-Weighted" if trade_data else "Structural"
        drivers.append(f"{label} Monopoly Risk: The market for {component} is highly concentrated (HHI: {int(hhi)}). The supply chain is dangerously reliant on a few key players like {top_sup_str}.")
    
    if p2_score > 0.5:
        adversary_list = [c for c in countries if c and c.upper() in adversaries]
        uniq_adv = ", ".join(set(adversary_list)) if adversary_list else "rival jurisdictions"
        drivers.append(f"Geopolitical Dependency: Sourcing for {component} shows significant reliance on adversarial jurisdictions ({uniq_adv}), exposing the network to export bans or sanctions based on official trade data.")
    
    if p3_score > 0.5: 
        drivers.append(f"Physical Perishability: {component} has a time-critical decay factor that prevents effective long-term stockpiling, meaning a supply shock would instantly halt production.")
        
    if p4_score > 0.6: 
        drivers.append(f"Low Substitutability: Because {component} is a highly bespoke, custom-engineered part with strict tolerances, there are virtually no drop-in replacements available in the open market.")
        
    if p5_score > 0.6: 
        drivers.append(f"Inertia Risk: Specialized engineering and testing requirements for {component} lead to extreme procurement delays, often extending lead times beyond 12 months for new orders.")
        
    if p6_score > 0.6: 
        drivers.append(f"Regulatory Bottleneck: Production of {component} is subject to stringent dual-use export controls (e.g., ITAR), requiring complex government licensing that could suddenly be revoked.")
        
    if p7_score > 0.8: 
        drivers.append(f"Critical System Failure Risk: {component} acts as the 'life-blood' bottleneck of the entire system architecture; any disruption here cascades immediately, halting all core operations.")


    return {
        "pillar_scores": {
            "hhi": round(p1_score, 2),
            "geopolitics": round(p2_score, 2),
            "shelf_life": p3_score,
            "substitutability": p4_score,
            "lead_time": p5_score,
            "regulatory": p6_score,
            "impact": p7_score
        },
        "key_drivers": drivers,
        "raw": {
            "hhi": hhi,
            "russia_exposure": 100 if "Russia" in countries else 0,
            "china_exposure": 100 if "China" in countries else 0,
            "has_industry_total": trade_data is not None
        }
    }

def load_dependency_graph(data_dir: Path = None) -> Dict[str, Any]:
    """Loads the dependency graph from dependencies.json in the given data_dir."""
    base_dir = data_dir or (Path(__file__).resolve().parents[1] / "data")
    dep_file = base_dir / "dependencies.json"
    if not dep_file.exists():
        return {"dependencies": []}
    with open(dep_file, "r") as f:
        return json.load(f)

def get_recursive_risk_metrics(component: str, region: str = "US", memo=None, data_dir: Path = None) -> Dict[str, Any]:
    """
    Level 4 Analytics: Calculates recursive 'Chain of Dependency' risk.
    Traverses the graph to find accumulated risk from sub-components.
    Accepts an optional data_dir to support per-sector folder isolation.
    """
    if memo is None: memo = {}
    if component in memo: return memo[component]

    base_metrics = get_component_risk_metrics(component, region, data_dir=data_dir)
    if "error" in base_metrics:
        # If no registry, we treat it as unknown risk (0.5) but still check children
        base_metrics = {
            "pillar_scores": {k: 0.5 for k in ["hhi", "geopolitics", "shelf_life", "substitutability", "lead_time", "regulatory", "impact"]},
            "key_drivers": ["Unknown Component - Data Missing"],
            "raw": {}
        }

    # 2. Find children in the graph
    graph = load_dependency_graph(data_dir=data_dir)
    children_names = []
    for entry in graph.get("dependencies", []):
        if entry["parent"].lower() == component.lower():
            children_names = entry["children"]
            break

    # 3. Recursively calculate children's risk
    child_risks = []
    for child in children_names:
        child_metrics = get_recursive_risk_metrics(child, region, memo, data_dir=data_dir)
        child_risks.append({
            "name": child,
            "metrics": child_metrics
        })

    # 4. Calculate Accumulated Risk Index (ARI)
    # Formula: ARI = α * Base_Risk + (1-α) * Max(Children_Risk)
    # We use a simple average of pillar scores for the "Base_Risk" here
    base_avg = sum(base_metrics["pillar_scores"].values()) / 7
    
    accumulated_score = base_avg
    spof = None
    max_child_score = 0

    if child_risks:
        for child in child_risks:
            # Calculate child's avg score
            child_avg = sum(child["metrics"]["pillar_scores"].values()) / 7
            if child_avg > max_child_score:
                max_child_score = child_avg
                spof = child["name"]
        
        # Propagation: Recursive risk is the average of self and the most dangerous child
        accumulated_score = (base_avg + max_child_score) / 2

    # 5. Build Recursive drivers
    recursive_drivers = base_metrics["key_drivers"][:]
    if spof:
        recursive_drivers.append(f"Chain Vulnerability: Critical bottleneck detected in sub-component '{spof}'.")

    result = {
        "component": component,
        "base_avg_score": round(base_avg, 2),
        "accumulated_score": round(accumulated_score, 2),
        "spof": spof,
        "pillar_scores": base_metrics["pillar_scores"], # We keep base pillars for the UI
        "key_drivers": recursive_drivers,
        "children": [c["name"] for c in child_risks],
        "raw": base_metrics["raw"]
    }
    
    memo[component] = result
    return result

if __name__ == "__main__":
    metrics = get_component_risk_metrics(component="Helium-3", region="US")
    print(json.dumps(metrics, indent=2))
