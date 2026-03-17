from src.scoring import score_component, RISK_WEIGHTS
import json

from pathlib import Path

def test_7_pillar_scoring():
    print("\n" + "="*60)
    print("7-PILLAR SCORING ENGINE VERIFICATION")
    print("="*60)
    print(f"Current Weights: {json.dumps(RISK_WEIGHTS, indent=2)}")

    test_cases = [
        {"comp": "Helium-3", "reg": "US", "scen": None},
        {"comp": "Mixing Chamber", "reg": "US", "scen": None},
        {"comp": "Dilution Refrigerator", "reg": "US", "scen": None},
        {"comp": "Quantum Computer", "reg": "US", "scen": "Sanctions on Russia"}
    ]
    
    # Use the new per-sector data path for the test
    base_dir = Path(__file__).parent / "data" / "sectors" / "quantum_computing" / "cryogenics"

    for tc in test_cases:
        score, drivers, conf = score_component(tc["reg"], tc["comp"], tc["scen"], data_dir=base_dir)
        print(f"\n[+] Component: {tc['comp']}")
        print(f"    Region:    {tc['reg']}")
        print(f"    Scenario:  {tc['scen']}")
        print(f"    FINAL SCORE: {score}")
        print(f"    Key Drivers:")
        for d in drivers:
            print(f"      - {d}")
        print(f"    Confidence:  {conf}")

if __name__ == "__main__":
    test_7_pillar_scoring()
