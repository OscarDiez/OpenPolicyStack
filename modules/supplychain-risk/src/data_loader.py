import json
from pathlib import Path
from typing import Any, Dict

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "demo_components.json"


def load_demo_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Demo data not found at: {DATA_PATH}")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
