import json
import logging
import glob
import os
import argparse
from core.risk_engine import RiskEngine
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("RiskPipeline")

def run_pipeline(limit=10):
    print("\n" + "=" * 60)
    print("🚀 DR ANTI-CORRUPTION: RISK ANALYSIS PIPELINE".center(60))
    print("=" * 60)
    
    # 1. Discover Latest Data
    p_files = glob.glob("data/proveedores_full_*.json")
    if not p_files:
        print("❌ ERROR: No full suppliers file found in data/")
        return
    
    input_file = max(p_files, key=os.path.getmtime)
    print(f"📖 Loading data source: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    items = data.get('payload', {}).get('content', [])
    print(f"   Total Suppliers Loaded: {len(items)}")
    
    # 2. Strategy: Target Discovery
    engine = RiskEngine()
    targets = []
    
    print("\n🔍 Identifying High-Risk Targets...")
    
    # Strategy A: Multi-Company Representatives (Network Concentration)
    multi_rep_rpes = set()
    for rpe, pids in engine.company_to_people.items():
        for pid in pids:
            if len(engine.person_to_companies.get(pid, set())) >= 5:
                multi_rep_rpes.add(rpe)
    
    # Strategy B: Keywords (Constructora, etc.)
    keyword_rpes = {str(s.get('rpe')) for s in items if s.get('razon_social') and 'CONSTRUCTORA' in s['razon_social'].upper()}
    
    priority_rpes = multi_rep_rpes.union(keyword_rpes)
    print(f"   Targets via Network Concentration: {len(multi_rep_rpes)}")
    print(f"   Targets via Keywords: {len(keyword_rpes)}")
    print(f"   Total unique priority targets: {len(priority_rpes)}")
    
    # Filter items to only priority targets
    priority_items = [s for s in items if str(s.get('rpe')) in priority_rpes]
    
    # 3. Analyze
    results = []
    selected_targets = priority_items[:limit]
    
    print(f"\n⚡ Starting Deep Analysis (Sample Limit: {limit})...")
    print("-" * 60)
    
    for i, supplier in enumerate(selected_targets):
        name = supplier.get('razon_social', 'Unknown')
        rpe = supplier.get('rpe')
        
        print(f"   [{i+1}/{len(selected_targets)}] Analyzing RPE {rpe}: {name[:30]}...")
        
        # Analyze
        risk_report = engine.analyze_supplier(name, supplier)
        results.append(risk_report)
        
    print(f"\n✅ Analysis Complete.")
    
    # 4. Save Report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"data/risk_report_batch_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Detailed report saved to: {output_file}")
    
    # 5. Dashboard View
    print("\n" + "🏁 RISK DASHBOARD SUMMARY ".center(60, "-"))
    print(f"{'RISK':<8} | {'SCORE':<5} | {'ENTITY'}")
    print("-" * 60)
    
    # Sort results by risk score
    sorted_results = sorted(results, key=lambda x: x['risk_score'], reverse=True)
    
    for res in sorted_results:
        color = "🔴" if res['risk_score'] >= 50 else ("🟡" if res['risk_score'] >= 25 else "🟢")
        name = res['entity'][:45]
        print(f"{color} {res['risk_level']:<6} | {res['risk_score']:>3}   | {name}")
        for factor in res['factors'][:3]:
            print(f"   ↳ ⚠️ {factor}")
        if len(res['factors']) > 3:
            print(f"   ↳ ... and {len(res['factors'])-3} more factors")
    print("-" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DR Anti-Corruption Risk Pipeline")
    parser.add_argument("--limit", type=int, default=10, help="Number of entities to analyze")
    args = parser.parse_args()
    
    run_pipeline(limit=args.limit)
