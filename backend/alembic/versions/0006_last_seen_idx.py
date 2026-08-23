"""job_discovery_matching: index last_seen_at for the DB-cache-first check

Revision ID: 0006_last_seen_idx
Revises: 0005_feedback
Create Date: 2026-08-19

Ported from Praveena's branch UNCHANGED — same revision id as her
original file, not renumbered. Your shared Supabase database's
`alembic_version` already points at this exact id (Dev Gupta ran this
migration against it directly before the 0006 fork was discovered), so
this file has to exist under this id for alembic to recognize the DB
as being at a known point in history at all. Renumbering it (as an
earlier version of this plan did) breaks that recognition — alembic
can't locate a revision the live database is already stamped at.

Your own migration (originally `0006_profile_edited_at`) is now
`0007_profile_edited_at.py`, chained on top of THIS revision instead
of forking off `0005_feedback` in parallel — see that file.

`internal/pipeline/nodes/db_cache_module.py` (checked before Adzuna and
before SearXNG+crawl4ai) filters `job_discovery_postings.last_seen_at
>= cutoff` and orders by it on every single pipeline run. Only
`url_hash` was indexed at table creation (0003) — that query was a
full table scan + sort without this index, which only gets worse as
the postings cache grows.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_last_seen_idx"
down_revision: str | None = "0005_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF NOT EXISTS: the index likely already physically exists on the
    # shared DB from the original run of this same migration — this
    # makes re-running it (e.g. against a fresh local/dev DB that's
    # never seen it) and "it's already there" both safe.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_discovery_postings_last_seen_at "
        "ON job_discovery_postings (last_seen_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_job_discovery_postings_last_seen_at")
