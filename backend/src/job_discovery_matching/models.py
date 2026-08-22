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
        ok                        - normal path, LLM judge ran and succeeded
        degraded_no_llm           - LLM judge ran but its call failed; hybrid-score-only ranking
        hybrid_only                - user DECLINED the LLM judge stage at
                                     judge_confirmation_gate — ranked by hybrid
                                     score only, deliberately, not as a fallback
        no_jobs                   - search/crawl produced nothing after filtering
        no_candidates              - profile had no usable signal to search from
        error                      - the pipeline itself raised
        awaiting_query_selection  - paused after query_generator; call
                                     POST /api/jobs/search/{run_id}/select-queries
                                     with the queries to actually search (see
                                     `generated_queries` for what to show the user)
        awaiting_judge_confirmation - paused after hybrid ranking; call
                                     POST /api/jobs/search/{run_id}/confirm-judge
                                     with {"proceed": true|false} — `top_jobs` is
                                     already populated with the hybrid-ranked
                                     jobs (judge=None) so the frontend can show
                                     them WHILE asking the question
    """

    run_id: UUID | None = None
    status: Literal[
        "ok",
        "degraded_no_llm",
        "hybrid_only",
        "no_jobs",
        "no_candidates",
        "error",
        "awaiting_query_selection",
        "awaiting_judge_confirmation",
    ]
    message: str = ""
    search_queries: list[str] = Field(default_factory=list)
    generated_queries: list[str] | None = None
    jobs_discovered: int = 0
    jobs_after_filter: int = 0
    top_jobs: list[RankedJob] = Field(default_factory=list)


class QuerySelectionRequest(BaseModel):
    """Body for POST /api/jobs/search/{run_id}/select-queries — the queries
    the user actually picked/edited from `generated_queries`. Empty list is
    rejected by the endpoint (falls back to ALL generated queries instead,
    at the query_selection_gate node level, if this is ever sent empty)."""

    selected_queries: list[str] = Field(min_length=1)


class JudgeConfirmationRequest(BaseModel):
    """Body for POST /api/jobs/search/{run_id}/confirm-judge. `proceed=True`
    runs the LLM judge (judge_module.py) over the hybrid-ranked jobs already
    shown in the preceding "awaiting_judge_confirmation" response's
    `top_jobs`; `proceed=False` finalizes the run with those same jobs,
    hybrid-ranked only, no LLM call spent.

    `selected_job_urls` lets the user judge only the jobs they actually
    picked from `top_jobs` (matched by `JobPostingView.source_url`).
    Omitted or empty means "judge all of them" — the original behaviour —
    so existing callers that don't send it are unaffected."""

    proceed: bool
    selected_job_urls: list[str] | None = None
