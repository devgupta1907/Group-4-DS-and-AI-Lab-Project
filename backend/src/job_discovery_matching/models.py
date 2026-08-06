"""
Job Discovery & Matching — public result contracts.

These are what `service.discover_jobs_for_profile()` returns, and what
`store.get_run()` reconstructs from the database. Nothing here knows
about SQLAlchemy, the LangGraph pipeline state, or crawling internals —
that shape lives in `internal/pipeline/state.py` and stays private.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SearchPreferences(BaseModel):
    """Optional overrides a candidate can supply alongside their profile."""

    target_location: str | None = None
    remote_only: bool = False
    min_salary_lpa: float | None = None


class JobPostingView(BaseModel):
    """Job fields as shown to the user. Populated from zero-LLM sources
    (JSON-LD / page metadata) and refined by the LLM judge for the jobs
    that make the final shortlist."""

    title: str = ""
    company: str = ""
    location: str = ""
    is_remote: bool = False
    required_skills: list[str] = Field(default_factory=list)
    employment_type: str = ""
    description: str = ""
    source_url: str = ""


class JudgeResultView(BaseModel):
    interview_probability: int = 0
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendation: Literal["Apply Immediately", "Apply", "Skip"] = "Skip"
    one_line_reason: str = ""
    used_llm_judge: bool = True


class RankedJob(BaseModel):
    job: JobPostingView
    bm25_score: float
    embedding_score: float
    hybrid_score: float
    rank_position: int
    judge: JudgeResultView | None = None
    final_score: float


class JobDiscoveryResult(BaseModel):
    """
    Full result of one job discovery run.

    `status` is one of:
        ok               - normal path, LLM judge succeeded
        degraded_no_llm  - judge LLM call failed; hybrid-score-only ranking
        no_jobs          - search/crawl produced nothing after filtering
        no_candidates    - profile had no usable signal to search from
        error            - the pipeline itself raised
    """

    run_id: UUID | None = None
    status: Literal["ok", "degraded_no_llm", "no_jobs", "no_candidates", "error"]
    message: str = ""
    search_queries: list[str] = Field(default_factory=list)
    jobs_discovered: int = 0
    jobs_after_filter: int = 0
    top_jobs: list[RankedJob] = Field(default_factory=list)
