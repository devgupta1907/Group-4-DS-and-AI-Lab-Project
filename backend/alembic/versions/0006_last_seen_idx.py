"""job_discovery_matching: index last_seen_at for the DB-cache-first check

Revision ID: 0006_job_discovery_postings_last_seen_idx
Revises: 0005_feedback
Create Date: 2026-08-19

`internal/pipeline/nodes/db_cache_module.py` (Node 1.5, checked before
Adzuna and before SearXNG+crawl4ai) filters
`job_discovery_postings.last_seen_at >= cutoff` and orders by it on
every single pipeline run. Only `url_hash` was indexed at table
creation (0003) — that query was a full table scan + sort without
this index, which only gets worse as the postings cache grows.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_last_seen_idx"
down_revision: str | None = "0005_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_job_discovery_postings_last_seen_at",
        "job_discovery_postings",
        ["last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_discovery_postings_last_seen_at", table_name="job_discovery_postings")
