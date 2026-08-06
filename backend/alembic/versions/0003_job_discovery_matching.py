"""job_discovery_matching: postings cache, runs, rankings, judge results

Revision ID: 0003_job_discovery_matching
Revises: 0002_career_recommendation
Create Date: 2026-08-06


this module owns an entirely separate cache table, `job_discovery_postings`,
so the two schemas never collide and `public.jobs` is left untouched.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_job_discovery_matching"
down_revision: str | None = "0002_career_recommendation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- job_discovery_runs -------------------------------------------------
    # FK -> resume_candidate_profiles.id must exist already (0001).
    op.create_table(
        "job_discovery_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("message", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("search_queries", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("llm_model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("jobs_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_after_filter", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["resume_candidate_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_discovery_runs_profile_id", "job_discovery_runs", ["profile_id"])
    op.create_index("ix_job_discovery_runs_user_id", "job_discovery_runs", ["user_id"])
    op.create_index("ix_job_discovery_runs_created_at", "job_discovery_runs", ["created_at"])

    # -- job_discovery_postings ----------------------------------------------
    # No FKs — this is the cross-run, cross-user crawl cache. Independent of
    # everything else, so its creation order doesn't matter relative to runs.
    op.create_table(
        "job_discovery_postings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("job_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("job_text", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_discovery_postings_url_hash", "job_discovery_postings", ["url_hash"], unique=True
    )

    # -- job_discovery_rankings ----------------------------------------------
    # FKs into both tables above, so must be created after them.
    op.create_table(
        "job_discovery_rankings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("posting_id", sa.Uuid(), nullable=False),
        sa.Column("bm25_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("embedding_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hybrid_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["run_id"], ["job_discovery_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["posting_id"], ["job_discovery_postings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "posting_id", name="uq_job_discovery_ranking_run_posting"),
    )
    op.create_index("ix_job_discovery_rankings_run_id", "job_discovery_rankings", ["run_id"])
    op.create_index("ix_job_discovery_rankings_posting_id", "job_discovery_rankings", ["posting_id"])

    # -- job_discovery_judge_results ------------------------------------------
    # FK into rankings, so it must be created last.
    op.create_table(
        "job_discovery_judge_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ranking_id", sa.Uuid(), nullable=False),
        sa.Column("interview_probability", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("recommendation", sa.String(length=32), nullable=False, server_default="Skip"),
        sa.Column("one_line_reason", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("final_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("used_llm_judge", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["ranking_id"], ["job_discovery_rankings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_discovery_judge_results_ranking_id",
        "job_discovery_judge_results",
        ["ranking_id"],
        unique=True,
    )


def downgrade() -> None:
    # Reverse order: judge_results -> rankings -> postings -> runs.
    op.drop_index("ix_job_discovery_judge_results_ranking_id", table_name="job_discovery_judge_results")
    op.drop_table("job_discovery_judge_results")

    op.drop_index("ix_job_discovery_rankings_posting_id", table_name="job_discovery_rankings")
    op.drop_index("ix_job_discovery_rankings_run_id", table_name="job_discovery_rankings")
    op.drop_table("job_discovery_rankings")

    op.drop_index("ix_job_discovery_postings_url_hash", table_name="job_discovery_postings")
    op.drop_table("job_discovery_postings")

    op.drop_index("ix_job_discovery_runs_created_at", table_name="job_discovery_runs")
    op.drop_index("ix_job_discovery_runs_user_id", table_name="job_discovery_runs")
    op.drop_index("ix_job_discovery_runs_profile_id", table_name="job_discovery_runs")
    op.drop_table("job_discovery_runs")
