import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI

app = FastAPI(title="OpenPolicyStack Integration Pilot", version="0.1.0")

MODULE_NAME = os.getenv("OPS_MODULE_NAME", "integration-pilot")
MODULE_VERSION = os.getenv("PILOT_MODULE_VERSION", "0.1.0")
ARTIFACT_ROOT = Path(os.getenv("OPS_ARTIFACT_ROOT", "/var/openpolicystack/artifacts"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "module_name": MODULE_NAME,
        "version": MODULE_VERSION,
    }


@app.post("/execute")
def execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    execution_id = str(uuid.uuid4())
    timestamp = now_iso()

    module_dir = ARTIFACT_ROOT / MODULE_NAME
    module_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = module_dir / f"{execution_id}.json"

    artifact_content = {
        "execution_id": execution_id,
        "timestamp": timestamp,
        "received_payload": payload,
        "message": "integration pilot executed successfully",
    }

    serialized = json.dumps(artifact_content, indent=2)
    artifact_path.write_text(serialized, encoding="utf-8")

    sha256_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    return {
        "module_name": MODULE_NAME,
        "version": MODULE_VERSION,
        "status": "success",
        "output": {
            "message": "pilot module executed successfully",
            "execution_id": execution_id,
            "received_keys": sorted(list(payload.keys())),
        },
        "artifacts": [
            {
                "module_name": MODULE_NAME,
                "file_path": str(artifact_path),
                "hash": sha256_hash,
                "type": "pilot_output",
            }
        ],
    }