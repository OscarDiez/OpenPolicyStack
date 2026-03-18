import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI

app = FastAPI(title="OpenPolicyStack Integration Pilot", version="0.1.0")

MODULE_NAME = os.getenv("OPS_MODULE_NAME", "integration-pilot")
MODULE_VERSION = os.getenv("PILOT_MODULE_VERSION", "0.1.0")
ARTIFACT_ROOT = Path(os.getenv("OPS_ARTIFACT_ROOT", "/var/openpolicystack/artifacts"))


def canonical_json(value: Any) -> str:
    """
    Deterministic JSON serialization used for stable content hashing.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "module_name": MODULE_NAME,
        "version": MODULE_VERSION,
    }


@app.post("/execute")
def execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    module_dir = ARTIFACT_ROOT / MODULE_NAME
    module_dir.mkdir(parents=True, exist_ok=True)

    stable_input = payload.get("input", payload)
    stable_input_hash = sha256_text(canonical_json(stable_input))

    artifact_filename = f"{stable_input_hash}.json"
    artifact_path = module_dir / artifact_filename

    artifact_content = {
        "input_hash": stable_input_hash,
        "received_payload": stable_input,
        "message": "integration pilot executed successfully",
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
    }

    serialized_artifact = json.dumps(
        artifact_content,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
    )
    artifact_path.write_text(serialized_artifact, encoding="utf-8")

    artifact_hash = sha256_text(serialized_artifact)

    return {
        "module_name": MODULE_NAME,
        "version": MODULE_VERSION,
        "status": "success",
        "output": {
            "message": "pilot module executed successfully",
            "input_hash": stable_input_hash,
            "received_keys": sorted(list(stable_input.keys()))
            if isinstance(stable_input, dict)
            else [],
        },
        "artifacts": [
            {
                "module_name": MODULE_NAME,
                "file_path": str(artifact_path),
                "hash": artifact_hash,
                "type": "pilot_output",
            }
        ],
    }