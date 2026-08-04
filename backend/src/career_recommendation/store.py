"""
Career Recommendation — recommendation persistence.

UNTESTED / STAND-IN: the M4 architecture diagram shows a shared
PostgreSQL "Candidate Profiles / Recommendations / Analysis Runs"
store used across all three modules, but no Postgres wiring exists
anywhere in this repo yet (checked: no psycopg/sqlalchemy usage
outside dependency locks). Rather than block the API endpoints on
that shared schema being designed by the team, this uses a local
SQLite file with the same shape (candidate_id, profile, result,
timestamp) so `GET /career/recommendations/{candidate_id}` has
something real to read from now.

Swap-out point: replace `_connect()` with a Postgres connection and
this module's public functions (`save_run`, `get_latest_run`,
`get_runs`) can stay the same — nothing outside this file needs to
change.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from core.config import GlobalConfig

DB_PATH = Path(GlobalConfig.DB_DIR) / "career_recommendation_runs.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    profile_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_candidate ON recommendation_runs(candidate_id);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def save_run(candidate_id: str, profile: dict, result: dict, status: str) -> int:
    """Persists one recommendation run. Returns the run's row id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO recommendation_runs (candidate_id, created_at, profile_json, result_json, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (candidate_id, time.time(), json.dumps(profile), json.dumps(result), status),
        )
        return cur.lastrowid


def get_latest_run(candidate_id: str) -> dict | None:
    """Returns the most recent recommendation run for a candidate, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT candidate_id, created_at, result_json, status FROM recommendation_runs "
            "WHERE candidate_id = ? ORDER BY created_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
    if row is None:
        return None
    candidate_id, created_at, result_json, status = row
    return {
        "candidate_id": candidate_id,
        "created_at": created_at,
        "status": status,
        "result": json.loads(result_json),
    }


def get_runs(candidate_id: str, limit: int = 10) -> list[dict]:
    """Returns up to `limit` past runs for a candidate, most recent first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT candidate_id, created_at, result_json, status FROM recommendation_runs "
            "WHERE candidate_id = ? ORDER BY created_at DESC LIMIT ?",
            (candidate_id, limit),
        ).fetchall()
    return [
        {
            "candidate_id": candidate_id,
            "created_at": created_at,
            "status": status,
            "result": json.loads(result_json),
        }
        for candidate_id, created_at, result_json, status in rows
    ]
