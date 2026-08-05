"""career_recommendation: recommendation runs keyed by parsed profile

Revision ID: 0002_career_recommendation
Revises: 0001_resume_parsing
Create Date: 2026-08-05

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_career_recommendation"
down_revision: str | None = "0001_resume_parsing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "career_recommendation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding_provider", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("llm_model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("skill_bonus_weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["resume_candidate_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_career_recommendation_runs_profile_id",
        "career_recommendation_runs",
        ["profile_id"],
    )
    op.create_index(
        "ix_career_recommendation_runs_user_id",
        "career_recommendation_runs",
        ["user_id"],
    )
    # Reading the latest run per profile is the common query.
    op.create_index(
        "ix_career_recommendation_runs_created_at",
        "career_recommendation_runs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_career_recommendation_runs_created_at", table_name="career_recommendation_runs")
    op.drop_index("ix_career_recommendation_runs_user_id", table_name="career_recommendation_runs")
    op.drop_index("ix_career_recommendation_runs_profile_id", table_name="career_recommendation_runs")
    op.drop_table("career_recommendation_runs")
