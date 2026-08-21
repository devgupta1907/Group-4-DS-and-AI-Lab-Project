"""resume_parsing: track manual edits to a parsed profile

Revision ID: 0006_profile_edited_at
Revises: 0005_feedback
Create Date: 2026-08-20

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_profile_edited_at"
down_revision: str | None = "0005_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL means "exactly what the model extracted." A timestamp means a user
    # corrected it after parsing, and everything downstream (recommendation,
    # job discovery, the report) has been reading the corrected version since.
    op.add_column(
        "resume_candidate_profiles",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("resume_candidate_profiles", "edited_at")
