"""ORM tables owned by the Job Discovery & Matching module.

Four tables, all prefixed `job_discovery_`. Declared against the SAME
shared Base as resume_parsing/career_recommendation, so Alembic sees one
metadata and every module lives in one database/one migration history.

DELIBERATE CHOICE: this does NOT reuse the existing `public.jobs` table
(the Adzuna-sourced schema in Schema.pdf). That table's shape belongs to
a different, older ingestion path and is not written to or read from
anywhere in this module. Job Discovery owns its own job cache instead,
named distinctly (`job_discovery_postings`) so the two can never be
confused, and so this module's schema can evolve independently.

Embeddings are stored as a plain JSONB float array rather than a
pgvector column. Nothing here needs an in-database ANN search — ranking
is computed in Python, in-process, once per run (see
internal/pipeline/nodes/matching_module.py) — so a pgvector column would
add a migration/extension dependency for no query benefit. If a future
need for SQL-side nearest-neighbour search over the whole postings cache
arises, swap this column for `pgvector.sqlalchemy.Vector(768)` and add
an ivfflat/hnsw index, following career_recommendation's `documents`
table as the existing example of that pattern.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base


class JobDiscoveryRun(Base):
    """One job-search invocation against one resume_parsing profile.

    Mirrors career_recommendation_runs's shape/intent: FK to the
    upstream profile so a DPDP erasure of the profile cascades here too.
    """

    __tablename__ = "job_discovery_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("resume_candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    # running | ok | degraded_no_llm | hybrid_only | no_jobs | no_candidates
    # | error | awaiting_query_selection | awaiting_judge_confirmation
    status: Mapped[str] = mapped_column(String(32), default="running")
    message: Mapped[str] = mapped_column(String(1024), default="")

    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    search_queries: Mapped[list] = mapped_column(JSONB, default=list)

    embedding_provider: Mapped[str] = mapped_column(String(64), default="")
    llm_model: Mapped[str] = mapped_column(String(128), default="")

    jobs_discovered: Mapped[int] = mapped_column(Integer, default=0)
    jobs_after_filter: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rankings: Mapped[list[JobDiscoveryRanking]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class JobPosting(Base):
    """Cross-run, cross-user cache of crawled job postings, keyed by URL.

    Populated with ZERO LLM calls (schema.org JSON-LD / page metadata —
    see internal/services/crawler_service.py). `url_hash` is what makes a
    posting reusable across every candidate's run within
    `JobDiscoveryModuleConfig.POSTING_CACHE_TTL_HOURS`, so the same
    listing is never re-crawled or re-embedded twice.
    """

    __tablename__ = "job_discovery_postings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_url: Mapped[str] = mapped_column(String(2048))

    job_json: Mapped[dict] = mapped_column(JSONB)
    job_text: Mapped[str] = mapped_column(Text)  # pruned page markdown; ranked against + read by the judge
    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class JobDiscoveryRanking(Base):
    """The SEARCH + RANKING record: one (run, posting) pair with its
    hybrid score.

    Every posting that survives the hard filter for a run gets exactly
    one row here, ordered by `hybrid_score` via `rank_position`. Only the
    top `JobDiscoveryModuleConfig.TOP_N_JUDGED` of those also get a
    `JobDiscoveryJudgeResult`.
    """

    __tablename__ = "job_discovery_rankings"
    __table_args__ = (
        UniqueConstraint("run_id", "posting_id", name="uq_job_discovery_ranking_run_posting"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_discovery_runs.id", ondelete="CASCADE"), index=True
    )
    posting_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_discovery_postings.id", ondelete="CASCADE"), index=True
    )

    bm25_score: Mapped[float] = mapped_column(Float, default=0.0)
    embedding_score: Mapped[float] = mapped_column(Float, default=0.0)
    hybrid_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank_position: Mapped[int] = mapped_column(Integer)  # 1-based, within this run

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[JobDiscoveryRun] = relationship(back_populates="rankings")
    posting: Mapped[JobPosting] = relationship()
    judge_result: Mapped[JobDiscoveryJudgeResult | None] = relationship(
        back_populates="ranking", cascade="all, delete-orphan", uselist=False
    )


class JobDiscoveryJudgeResult(Base):
    """The JUDGE record: the LLM judge's structured response for one
    ranked job in one run.

    A strict subset of JobDiscoveryRanking rows — only the top
    `TOP_N_JUDGED` per run. Written by a SINGLE batched LLM call per run
    (see internal/pipeline/nodes/judge_module.py), never one call per job.
    `used_llm_judge=False` marks rows written by the hybrid-score-only
    fallback path when that batched call fails outright.
    """

    __tablename__ = "job_discovery_judge_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ranking_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_discovery_rankings.id", ondelete="CASCADE"), unique=True, index=True
    )

    interview_probability: Mapped[int] = mapped_column(Integer, default=0)
    strengths: Mapped[list[str]] = mapped_column(JSONB, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSONB, default=list)
    recommendation: Mapped[str] = mapped_column(String(32), default="Skip")
    one_line_reason: Mapped[str] = mapped_column(String(256), default="")
    final_score: Mapped[float] = mapped_column(Float, default=0.0)
    used_llm_judge: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ranking: Mapped[JobDiscoveryRanking] = relationship(back_populates="judge_result")
