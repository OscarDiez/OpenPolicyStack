import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import FastAPI, HTTPException

app = FastAPI(title="OpenPolicyStack Orchestrator", version="0.1.0")

MODULE_NAME = os.getenv("OPS_MODULE_NAME", "orchestrator")
MODULE_VERSION = "0.1.0"
ARTIFACT_ROOT = Path(os.getenv("OPS_ARTIFACT_ROOT", "/var/openpolicystack/artifacts"))
SQLITE_PATH = Path(
    os.getenv(
        "ORCHESTRATOR__SQLITE_PATH",
        "/var/openpolicystack/metadata/orchestrator.db",
    )
)
INTEGRATION_PILOT_URL = os.getenv(
    "ORCHESTRATOR__INTEGRATION_PILOT_URL",
    "http://integration-pilot:8080",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_paths() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    ensure_paths()
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                workflow_template TEXT,
                status TEXT,
                created_at TEXT,
                request_payload TEXT,
                response_payload TEXT
            )
            """
        )
        conn.commit()


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "module_name": MODULE_NAME,
        "version": MODULE_VERSION,
        "pilot_url": INTEGRATION_PILOT_URL,
        "sqlite_path": str(SQLITE_PATH),
    }


@app.post("/execute")
async def execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    created_at = now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO runs (run_id, workflow_template, status, created_at, request_payload, response_payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "pilot-workflow",
                "running",
                created_at,
                json.dumps(payload),
                None,
            ),
        )
        conn.commit()

    upstream_payload = {
        "run_id": run_id,
        "input": payload,
        "requested_by": MODULE_NAME,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream_response = await client.post(
                f"{INTEGRATION_PILOT_URL}/execute",
                json=upstream_payload,
            )
            upstream_response.raise_for_status()
            pilot_result = upstream_response.json()
    except Exception as exc:
        with get_conn() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, response_payload = ? WHERE run_id = ?",
                ("failed", json.dumps({"error": str(exc)}), run_id),
            )
            conn.commit()
        raise HTTPException(status_code=502, detail=f"Pilot module call failed: {exc}")

    orchestrator_dir = ARTIFACT_ROOT / "orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    summary_path = orchestrator_dir / f"{run_id}-summary.json"
    summary = {
        "run_id": run_id,
        "timestamp": created_at,
        "orchestrator": MODULE_NAME,
        "pilot_response": pilot_result,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    response = {
        "module_name": MODULE_NAME,
        "version": MODULE_VERSION,
        "status": "success",
        "run_id": run_id,
        "output": {
            "message": "orchestrator executed pilot workflow successfully",
            "pilot_result": pilot_result,
        },
        "artifacts": [
            {
                "module_name": MODULE_NAME,
                "file_path": str(summary_path),
                "type": "run_summary",
            }
        ],
    }

    with get_conn() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, response_payload = ? WHERE run_id = ?",
            ("success", json.dumps(response), run_id),
        )
        conn.commit()

    return response