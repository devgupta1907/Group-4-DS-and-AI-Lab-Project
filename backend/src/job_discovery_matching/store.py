"""
Job Discovery & Matching — result reconstruction.

READING FROM OTHER MODULES
    Other modules (or a future frontend) should call `service.get_run()` /
    `service.get_latest_run()` rather than querying `job_discovery_runs`,
    `job_discovery_rankings`, or `job_discovery_judge_results` directly,
    so those tables' shapes stay private to this module — the same rule
    career_recommendation/store.py documents for its own tables.
"""

from __future__ import annotations

from uuid import UUID

from src.core.db import get_session_factory
from src.job_discovery_matching.internal.models import JobDiscoveryRanking, JobDiscoveryRun
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
from src.job_discovery_matching.models import (
    JobDiscoveryResult,
    JobPostingView,
    JudgeResultView,
    RankedJob,
)


def _ranking_to_view(ranking: JobDiscoveryRanking) -> RankedJob:
    posting = ranking.posting
    job_json = posting.job_json or {}
    judge_view = None
    final_score = ranking.hybrid_score
    if ranking.judge_result is not None:
        jr = ranking.judge_result
        judge_view = JudgeResultView(
            interview_probability=jr.interview_probability,
            strengths=jr.strengths,
            gaps=jr.gaps,
            recommendation=jr.recommendation,
            one_line_reason=jr.one_line_reason,
            used_llm_judge=jr.used_llm_judge,
        )
        final_score = jr.final_score

    return RankedJob(
        job=JobPostingView(
            title=job_json.get("title", ""),
            company=job_json.get("company", ""),
            location=job_json.get("location", ""),
            is_remote=bool(job_json.get("is_remote", False)),
            required_skills=job_json.get("required_skills", []) or [],
            employment_type=job_json.get("employment_type", ""),
            description=job_json.get("description", ""),
            source_url=posting.source_url,
        ),
        bm25_score=ranking.bm25_score,
        embedding_score=ranking.embedding_score,
        hybrid_score=ranking.hybrid_score,
        rank_position=ranking.rank_position,
        judge=judge_view,
        final_score=final_score,
    )


async def _result_from_run(run: JobDiscoveryRun, rankings: list[JobDiscoveryRanking]) -> JobDiscoveryResult:
    judged_only = [r for r in rankings if r.judge_result is not None]
    judged_only.sort(key=lambda r: r.judge_result.final_score, reverse=True)

    return JobDiscoveryResult(
        run_id=run.id,
        status=run.status,  # type: ignore[arg-type]
        message=run.message,
        search_queries=run.search_queries or [],
        jobs_discovered=run.jobs_discovered,
        jobs_after_filter=run.jobs_after_filter,
        top_jobs=[_ranking_to_view(r) for r in judged_only],
    )


def _result_from_state(
    *,
    run_id: UUID,
    status: str,
    message: str,
    search_queries: list[str],
    jobs_discovered: int,
    jobs_after_filter: int,
    final_jobs: list[dict],
) -> JobDiscoveryResult:
    """Builds a JobDiscoveryResult straight from the just-finished
    pipeline state, without a round-trip back to the database. Used by
    `service.discover_jobs_for_profile()` right after a live run; reads
    that come later (`get_run`, `get_latest_run`) go through
    `_result_from_run` instead, against what was actually persisted."""
    top_jobs = [
        RankedJob(
            job=JobPostingView(
                title=entry["job_json"].get("title", ""),
                company=entry["job_json"].get("company", ""),
                location=entry["job_json"].get("location", ""),
                is_remote=bool(entry["job_json"].get("is_remote", False)),
                required_skills=entry["job_json"].get("required_skills", []) or [],
                employment_type=entry["job_json"].get("employment_type", ""),
                description=entry["job_json"].get("description", ""),
                source_url=entry["source_url"],
            ),
            bm25_score=entry["bm25_score"],
            embedding_score=entry["embedding_score"],
            hybrid_score=entry["hybrid_score"],
            rank_position=i + 1,
            judge=JudgeResultView(**entry["judge"]),
            final_score=entry["final_score"],
        )
        for i, entry in enumerate(final_jobs)
    ]
    return JobDiscoveryResult(
        run_id=run_id,
        status=status,  # type: ignore[arg-type]
        message=message,
        search_queries=search_queries,
        jobs_discovered=jobs_discovered,
        jobs_after_filter=jobs_after_filter,
        top_jobs=top_jobs,
    )


async def get_run(run_id: UUID, user_id: str | None = None) -> JobDiscoveryResult | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        run = await repo.get_run(run_id, user_id=user_id)
        if run is None:
            return None
        rankings = await repo.get_rankings_with_judge(run_id)
        return await _result_from_run(run, rankings)


async def get_latest_run(profile_id: UUID, user_id: str | None = None) -> JobDiscoveryResult | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        run = await repo.get_latest_run(profile_id, user_id=user_id)
        if run is None:
            return None
        rankings = await repo.get_rankings_with_judge(run.id)
        return await _result_from_run(run, rankings)


async def get_runs(profile_id: UUID, user_id: str | None = None, limit: int = 10) -> list[JobDiscoveryResult]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        runs = await repo.get_runs(profile_id, user_id=user_id, limit=limit)
        results = []
        for run in runs:
            rankings = await repo.get_rankings_with_judge(run.id)
            results.append(await _result_from_run(run, rankings))
        return results
