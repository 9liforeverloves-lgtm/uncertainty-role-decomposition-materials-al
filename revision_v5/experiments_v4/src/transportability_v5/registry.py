"""SQLite-backed mutable execution registry for immutable Development jobs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REGISTRY_SCHEMA_VERSION = "revision-v5-run-registry-v1"
ALLOWED = {
    "PLANNED": {"RUNNING", "EXCLUDED_WITH_REASON"},
    "RUNNING": {"COMPLETED", "RECOVERED", "FAILED", "PLANNED"},
    "FAILED": {"PLANNED"},
    "COMPLETED": set(),
    "RECOVERED": set(),
    "EXCLUDED_WITH_REASON": set(),
}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize(path: Path, job_ids: list[str], task_manifest_sha256: str) -> sqlite3.Connection:
    connection = connect(path)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
            claimed_at TEXT, started_at TEXT, completed_at TEXT, worker_id TEXT, pid INTEGER,
            hostname TEXT, exit_code INTEGER, runtime_seconds REAL, retry_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT, output_path TEXT, output_hash TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL, attempt INTEGER NOT NULL, payload_json TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ("schema_version", REGISTRY_SCHEMA_VERSION))
    connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ("immutable_task_manifest_sha256", task_manifest_sha256))
    now = timestamp()
    connection.executemany(
        "INSERT OR IGNORE INTO jobs(job_id,status,updated_at) VALUES(?,?,?)",
        [(job_id, "PLANNED", now) for job_id in job_ids],
    )
    return connection


def _event(connection: sqlite3.Connection, job_id: str, event_type: str, attempt: int, payload: dict) -> int:
    cursor = connection.execute(
        "INSERT INTO events(job_id,timestamp,event_type,attempt,payload_json) VALUES(?,?,?,?,?)",
        (job_id, timestamp(), event_type, attempt, json.dumps(payload, sort_keys=True)),
    )
    return int(cursor.lastrowid)


def claim_next(connection: sqlite3.Connection, worker_id: str, pid: int, hostname: str) -> dict | None:
    """Atomically claim one PLANNED job; concurrent callers cannot receive the same row."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute(
            "SELECT job_id,attempt FROM jobs WHERE status='PLANNED' ORDER BY job_id LIMIT 1"
        ).fetchone()
        if row is None:
            connection.execute("COMMIT")
            return None
        job_id, prior_attempt = row
        attempt = int(prior_attempt) + 1
        now = timestamp()
        payload = {"worker_id": worker_id, "pid": pid, "hostname": hostname, "claimed_at": now, "started_at": now}
        connection.execute(
            "UPDATE jobs SET status='RUNNING',attempt=?,claimed_at=?,started_at=?,worker_id=?,pid=?,hostname=?,updated_at=? WHERE job_id=? AND status='PLANNED'",
            (attempt, now, now, worker_id, pid, hostname, now, job_id),
        )
        event_id = _event(connection, job_id, "PLANNED_TO_RUNNING", attempt, payload)
        connection.execute("COMMIT")
        return {"job_id": job_id, "attempt": attempt, "event_id": event_id, **payload}
    except Exception:
        connection.execute("ROLLBACK")
        raise


def claim_specific(connection: sqlite3.Connection, job_id: str, worker_id: str, pid: int, hostname: str) -> dict:
    """Atomically claim one named PLANNED job, used for prespecified canaries."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute("SELECT status,attempt FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None or row[0] != "PLANNED":
            raise ValueError(f"job is not planned: {job_id}")
        attempt = int(row[1]) + 1; now = timestamp()
        payload = {"worker_id": worker_id, "pid": pid, "hostname": hostname, "claimed_at": now, "started_at": now}
        connection.execute("UPDATE jobs SET status='RUNNING',attempt=?,claimed_at=?,started_at=?,worker_id=?,pid=?,hostname=?,updated_at=? WHERE job_id=?", (attempt,now,now,worker_id,pid,hostname,now,job_id))
        event_id = _event(connection, job_id, "PLANNED_TO_RUNNING", attempt, payload)
        connection.execute("COMMIT")
        return {"job_id":job_id,"attempt":attempt,"event_id":event_id,**payload}
    except Exception:
        connection.execute("ROLLBACK")
        raise


def transition(connection: sqlite3.Connection, job_id: str, target: str, payload: dict | None = None, *, allow_stale_recovery: bool = False, allow_retry: bool = False) -> int:
    payload = payload or {}
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute("SELECT status,attempt,retry_count FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        current, attempt, retry_count = row
        permitted = target in ALLOWED[current]
        if current == "RUNNING" and target == "PLANNED":
            permitted = permitted and allow_stale_recovery
        if current == "FAILED" and target == "PLANNED":
            permitted = permitted and allow_retry
        if not permitted:
            raise ValueError(f"invalid status transition {current}->{target}")
        now = timestamp()
        next_retry = int(retry_count) + (1 if current == "FAILED" and target == "PLANNED" else 0)
        connection.execute(
            """UPDATE jobs SET status=?, completed_at=CASE WHEN ? IN ('COMPLETED','RECOVERED') THEN ? ELSE completed_at END,
               exit_code=COALESCE(?,exit_code), runtime_seconds=COALESCE(?,runtime_seconds),
               last_error=COALESCE(?,last_error), output_path=COALESCE(?,output_path),
               output_hash=COALESCE(?,output_hash), retry_count=?, updated_at=? WHERE job_id=?""",
            (target, "COMPLETED", now, payload.get("exit_code"), payload.get("runtime_seconds"), payload.get("last_error"), payload.get("output_path"), payload.get("output_hash"), next_retry, now, job_id),
        )
        event_id = _event(connection, job_id, f"{current}_TO_{target}", int(attempt), payload)
        connection.execute("COMMIT")
        return event_id
    except Exception:
        connection.execute("ROLLBACK")
        raise


def recover_stale(connection: sqlite3.Connection, cutoff_iso: str) -> list[str]:
    rows = connection.execute("SELECT job_id FROM jobs WHERE status='RUNNING' AND started_at < ?", (cutoff_iso,)).fetchall()
    recovered = []
    for (job_id,) in rows:
        transition(connection, job_id, "PLANNED", {"last_error": "stale-worker recovery"}, allow_stale_recovery=True)
        recovered.append(job_id)
    return recovered


def snapshot(connection: sqlite3.Connection):
    return connection.execute("SELECT * FROM jobs ORDER BY job_id").fetchall()
