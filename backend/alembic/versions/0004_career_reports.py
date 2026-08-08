"""career report snapshots

Revision ID: 0004_career_reports
Revises: 0003_job_discovery_matching
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_career_reports"
down_revision: str | None = "0003_job_discovery_matching"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "career_report_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("career_run_id", sa.Uuid(), nullable=False),
        sa.Column("job_run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("model_used", sa.String(128), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["resume_candidate_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["career_run_id"], ["career_recommendation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_run_id"], ["job_discovery_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_career_report_snapshots_profile_id", "career_report_snapshots", ["profile_id"])
    op.create_index("ix_career_report_snapshots_user_id", "career_report_snapshots", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_career_report_snapshots_user_id", table_name="career_report_snapshots")
    op.drop_index("ix_career_report_snapshots_profile_id", table_name="career_report_snapshots")
    op.drop_table("career_report_snapshots")
