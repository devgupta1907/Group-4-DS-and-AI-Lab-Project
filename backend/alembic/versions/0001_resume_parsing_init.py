"""resume_parsing: parse jobs, encrypted candidate profiles, audit log

Revision ID: 0001_resume_parsing
Revises:
Create Date: 2026-07-28

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_resume_parsing"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_parse_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("route", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="received"),
        sa.Column("model_used", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("coverage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_parse_jobs_user_id", "resume_parse_jobs", ["user_id"])

    op.create_table(
        "resume_candidate_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        # The whole profile, Fernet-sealed. Never queryable in clear.
        sa.Column("profile_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column(
            "needs_review",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["resume_parse_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resume_candidate_profiles_job_id",
        "resume_candidate_profiles",
        ["job_id"],
        unique=True,
    )
    op.create_index(
        "ix_resume_candidate_profiles_user_id", "resume_candidate_profiles", ["user_id"]
    )
    op.create_index(
        "ix_resume_candidate_profiles_content_hash",
        "resume_candidate_profiles",
        ["content_hash"],
    )

    op.create_table(
        "resume_audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("detail", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_audit_log_user_id", "resume_audit_log", ["user_id"])


def downgrade() -> None:
    op.drop_table("resume_audit_log")
    op.drop_table("resume_candidate_profiles")
    op.drop_table("resume_parse_jobs")
