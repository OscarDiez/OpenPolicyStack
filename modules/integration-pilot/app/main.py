import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

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
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def canonical_json(value: Any) -> str:
    """
    Deterministic JSON serialization for hashing and storage consistency.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_payload(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if payload is None:
        return None
    return sha256_text(canonical_json(payload))


def hash_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                workflow_template TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                request_payload TEXT,
                response_payload TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_calls (
                call_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                module_name TEXT NOT NULL,
                module_version TEXT,
                call_sequence INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                execution_time_ms INTEGER,
                request_payload TEXT,
                response_payload TEXT,
                error_message TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                call_id TEXT,
                module_name TEXT NOT NULL,
                artifact_type TEXT,
                file_path TEXT NOT NULL,
                hash TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (call_id) REFERENCES module_calls(call_id)
            )
            """
        )

        # Safe additive migration for hashing support
        if not column_exists(conn, "runs", "request_payload_hash"):
            conn.execute("ALTER TABLE runs ADD COLUMN request_payload_hash TEXT")

        if not column_exists(conn, "runs", "response_payload_hash"):
            conn.execute("ALTER TABLE runs ADD COLUMN response_payload_hash TEXT")

        if not column_exists(conn, "module_calls", "request_payload_hash"):
            conn.execute("ALTER TABLE module_calls ADD COLUMN request_payload_hash TEXT")

        if not column_exists(conn, "module_calls", "response_payload_hash"):
            conn.execute("ALTER TABLE module_calls ADD COLUMN response_payload_hash TEXT")

        conn.commit()


def insert_run(
    run_id: str,
    workflow_template: str,
    overall_status: str,
    created_at: str,
    request_payload: Dict[str, Any],
) -> None:
    request_payload_json = canonical_json(request_payload)
    request_payload_hash = sha256_text(request_payload_json)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id,
                workflow_template,
                overall_status,
                created_at,
                request_payload,
                response_payload,
                request_payload_hash,
                response_payload_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                workflow_template,
                overall_status,
                created_at,
                request_payload_json,
                None,
                request_payload_hash,
                None,
            ),
        )
        conn.commit()


def update_run(
    run_id: str,
    overall_status: str,
    response_payload: Dict[str, Any],
    completed_at: Optional[str] = None,
) -> None:
    response_payload_json = canonical_json(response_payload)
    response_payload_hash = sha256_text(response_payload_json)

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE runs
            SET overall_status = ?,
                completed_at = ?,
                response_payload = ?,
                response_payload_hash = ?
            WHERE run_id = ?
            """,
            (
                overall_status,
                completed_at,
                response_payload_json,
                response_payload_hash,
                run_id,
            ),
        )
        conn.commit()


def insert_module_call(
    call_id: str,
    run_id: str,
    module_name: str,
    call_sequence: int,
    status: str,
    started_at: str,
    request_payload: Dict[str, Any],
) -> None:
    request_payload_json = canonical_json(request_payload)
    request_payload_hash = sha256_text(request_payload_json)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO module_calls (
                call_id,
                run_id,
                module_name,
                module_version,
                call_sequence,
                status,
                started_at,
                completed_at,
                execution_time_ms,
                request_payload,
                response_payload,
                error_message,
                request_payload_hash,
                response_payload_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                run_id,
                module_name,
                None,
                call_sequence,
                status,
                started_at,
                None,
                None,
                request_payload_json,
                None,
                None,
                request_payload_hash,
                None,
            ),
        )
        conn.commit()


def update_module_call(
    call_id: str,
    module_version: Optional[str],
    status: str,
    completed_at: str,
    execution_time_ms: int,
    response_payload: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> None:
    response_payload_json = (
        canonical_json(response_payload) if response_payload is not None else None
    )
    response_payload_hash = (
        sha256_text(response_payload_json) if response_payload_json is not None else None
    )

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE module_calls
            SET module_version = ?,
                status = ?,
                completed_at = ?,
                execution_time_ms = ?,
                response_payload = ?,
                error_message = ?,
                response_payload_hash = ?
            WHERE call_id = ?
            """,
            (
                module_version,
                status,
                completed_at,
                execution_time_ms,
                response_payload_json,
                error_message,
                response_payload_hash,
                call_id,
            ),
        )
        conn.commit()


def insert_artifact(
    artifact_id: str,
    run_id: str,
    call_id: Optional[str],
    module_name: str,
    artifact_type: Optional[str],
    file_path: str,
    hash_value: Optional[str],
    created_at: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO artifacts (
                artifact_id,
                run_id,
                call_id,
                module_name,
                artifact_type,
                file_path,
                hash,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                run_id,
                call_id,
                module_name,
                artifact_type,
                file_path,
                hash_value,
                created_at,
            ),
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
    run_created_at = now_iso()

    insert_run(
        run_id=run_id,
        workflow_template="pilot-workflow",
        overall_status="running",
        created_at=run_created_at,
        request_payload=payload,
    )

    call_id = str(uuid.uuid4())
    call_started_at = now_iso()

    upstream_payload = {
        "run_id": run_id,
        "input": payload,
        "requested_by": MODULE_NAME,
    }

    insert_module_call(
        call_id=call_id,
        run_id=run_id,
        module_name="integration-pilot",
        call_sequence=1,
        status="running",
        started_at=call_started_at,
        request_payload=upstream_payload,
    )

    try:
        start_perf = time.perf_counter()

        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream_response = await client.post(
                f"{INTEGRATION_PILOT_URL}/execute",
                json=upstream_payload,
            )
            upstream_response.raise_for_status()
            pilot_result = upstream_response.json()

        execution_time_ms = int((time.perf_counter() - start_perf) * 1000)
        call_completed_at = now_iso()

        update_module_call(
            call_id=call_id,
            module_version=pilot_result.get("version"),
            status="success",
            completed_at=call_completed_at,
            execution_time_ms=execution_time_ms,
            response_payload=pilot_result,
        )

    except Exception as exc:
        execution_time_ms = (
            int((time.perf_counter() - start_perf) * 1000)
            if "start_perf" in locals()
            else 0
        )
        call_completed_at = now_iso()
        run_completed_at = now_iso()

        update_module_call(
            call_id=call_id,
            module_version=None,
            status="failed",
            completed_at=call_completed_at,
            execution_time_ms=execution_time_ms,
            response_payload=None,
            error_message=str(exc),
        )

        error_response = {
            "module_name": MODULE_NAME,
            "version": MODULE_VERSION,
            "status": "failed",
            "run_id": run_id,
            "error": f"Pilot module call failed: {exc}",
        }

        update_run(
            run_id=run_id,
            overall_status="failed",
            response_payload=error_response,
            completed_at=run_completed_at,
        )

        raise HTTPException(status_code=502, detail=f"Pilot module call failed: {exc}")

    for artifact in pilot_result.get("artifacts", []):
        insert_artifact(
            artifact_id=str(uuid.uuid4()),
            run_id=run_id,
            call_id=call_id,
            module_name=artifact.get("module_name", "integration-pilot"),
            artifact_type=artifact.get("type"),
            file_path=artifact.get("file_path", ""),
            hash_value=artifact.get("hash"),
            created_at=now_iso(),
        )

    orchestrator_dir = ARTIFACT_ROOT / "orchestrator"
    orchestrator_dir.mkdir(parents=True, exist_ok=True)

    summary_path = orchestrator_dir / f"{run_id}-summary.json"
    summary = {
        "run_id": run_id,
        "timestamp": run_created_at,
        "orchestrator": MODULE_NAME,
        "pilot_response": pilot_result,
    }
    summary_serialized = json.dumps(summary, indent=2, ensure_ascii=False)
    summary_path.write_text(summary_serialized, encoding="utf-8")
    summary_hash = hash_file(summary_path)

    insert_artifact(
        artifact_id=str(uuid.uuid4()),
        run_id=run_id,
        call_id=None,
        module_name=MODULE_NAME,
        artifact_type="run_summary",
        file_path=str(summary_path),
        hash_value=summary_hash,
        created_at=now_iso(),
    )

    final_response = {
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
                "hash": summary_hash,
                "type": "run_summary",
            }
        ],
    }

    update_run(
        run_id=run_id,
        overall_status="success",
        response_payload=final_response,
        completed_at=now_iso(),
    )

    return final_response