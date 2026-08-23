"""resume_parsing: track manual edits to a parsed profile

Revision ID: 0007_profile_edited_at
Revises: 0006_last_seen_idx
Create Date: 2026-08-20

Was `0006_profile_edited_at`, forked off `0005_feedback` in parallel
with Praveena's `0006_last_seen_idx`. Renumbered to 0007 and rechained
onto her migration instead, since the shared Supabase database's
`alembic_version` already points at `0006_last_seen_idx` (she ran hers
against it first) — this is the direction that matches reality; see
`0006_last_seen_idx.py`'s docstring for why the other direction
(renumbering hers) doesn't work.

If you already ran the original `0006_profile_edited_at` against any
database (a personal/local Postgres, say) before this rename, that
database's `alembic_version` will still say `0006_profile_edited_at`,
which no longer exists under that id — you'd need
`alembic stamp 0007_profile_edited_at` there once, since the actual
schema change (the `edited_at` column) is identical and already
present; nothing to re-run. If you never ran the original against
anything, ignore this paragraph.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_profile_edited_at"
down_revision: str | None = "0006_last_seen_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF NOT EXISTS: defensive only. Nothing found so far suggests this
    # column exists on the shared DB yet — the DB's current stamped
    # revision (0006_last_seen_idx, pre-rename) predates it entirely —
    # but this costs nothing and protects against re-running on a
    # database that's already been through some other path.
    op.execute(
        "ALTER TABLE resume_candidate_profiles "
        "ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE resume_candidate_profiles DROP COLUMN IF EXISTS edited_at")
