"""
Job Discovery & Matching — service entry point.

This is the ONE function other modules (and the API layer) should call:

    from src.job_discovery_matching.service import discover_jobs_for_profile
    result = await discover_jobs_for_profile(profile, profile_id=..., user_id=...)

It maps a resume_parsing profile into the pipeline's candidate shape,
creates a run row up front (so a run_id exists even if the pipeline
later fails), runs the LangGraph pipeline, and finalizes the run's
status/message. Rankings and judge results are persisted inside
`internal/pipeline/nodes/judge_module.py` (the node that produces them),
not here — this function only owns the run-level lifecycle.
"""

from __future__ import annotations

import logging
from uuid import UUID

from src.core.config import GlobalConfig
from src.core.db import get_session_factory
from src.job_discovery_matching import store
from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.graph import pipeline
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
from src.job_discovery_matching.internal.services.embedding_client import embed_query
from src.job_discovery_matching.models import JobDiscoveryResult, SearchPreferences
from src.job_discovery_matching.profile_mapper import from_parsed_resume, has_usable_signal
from src.resume_parsing.schemas import CandidateProfile as ParsedProfile
from src.career_recommendation import store as career_store
logger = logging.getLogger(__name__)


def _candidate_profile_text(candidate: dict) -> str:
    return " ".join(
        [
            candidate.get("current_role", "") or "",
            candidate.get("domain", "") or "",
            " ".join(candidate.get("skills", []) or []),
            " ".join(candidate.get("target_roles", []) or []),
        ]
    ).strip()


async def discover_jobs_for_profile(
    profile: ParsedProfile,
    *,
    profile_id: UUID,
    user_id: str,
    preferences: SearchPreferences | None = None,
) -> JobDiscoveryResult:
    """
    Full Job Discovery pipeline: query-generate -> search -> crawl ->
    hard-filter -> hybrid-rank -> LLM judge.

    Args:
        profile: the decrypted resume_parsing CandidateProfile (read via
            resume_parsing's public service, same as career_recommendation
            does — never by querying its tables).
        profile_id: the resume_candidate_profiles.id this run is against.
            Always required (unlike career_recommendation's inline-profile
            testing path) because every posting/ranking this pipeline
            crawls is expensive and worth persisting against something.
        user_id: owner, for row-level access control on reads.
        preferences: optional location/remote/salary overrides.

    Returns:
        JobDiscoveryResult with status one of:
            ok               - normal path, LLM judge succeeded
            degraded_no_llm  - judge LLM call failed, hybrid-score-only ranking
            no_jobs          - search/crawl produced nothing after filtering
            no_candidates    - profile had no usable signal to search from
            error            - the pipeline itself raised
    """
    prefs = (preferences or SearchPreferences()).model_dump()
    candidate_json = from_parsed_resume(profile)

# Chain the modules: search on the ESCO occupations Career Recommendation
    # produced, not just the candidate's own past job titles. "agricultural
    # engineer" is a far better search term than "AGRICULTURAL CONNECTIVITY
    # VALIDATION TEST ENGINEER". Falls through silently when no recommendation
    # exists, so job discovery still works standalone.
    try:
        run = career_store.get_latest_run(profile_id, user_id=user_id)
        if run and run.get("result", {}).get("recommendations"):
            titles = [
                r["occupation_title"]
                for r in run["result"]["recommendations"][:2]
                if r.get("occupation_title")
            ]
            existing = candidate_json.get("target_roles") or []
            candidate_json["target_roles"] = titles + [t for t in existing if t not in titles]
            logger.info("Seeded target_roles from career recommendation: %s", titles)
    except Exception:
        logger.warning("Could not read career recommendation for %s; continuing.", profile_id, exc_info=True)




    session_factory = get_session_factory()

    if not has_usable_signal(candidate_json):
        logger.info("Profile %s has no usable signal; skipping job discovery.", profile_id)
        async with session_factory() as session:
            repo = JobDiscoveryRepository(session)
            run_id = await repo.create_run(
                profile_id=profile_id, user_id=user_id, preferences=prefs
            )
            await repo.finish_run(
                run_id,
                status="no_candidates",
                message=(
                    "This profile has no target roles or skills to search jobs "
                    "against — nothing to discover from."
                ),
                search_queries=[],
                jobs_discovered=0,
                jobs_after_filter=0,
                embedding_provider="",
                llm_model="",
            )
        return JobDiscoveryResult(
            run_id=run_id,
            status="no_candidates",
            message="This profile has no target roles or skills to search jobs against.",
        )

    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        run_id = await repo.create_run(profile_id=profile_id, user_id=user_id, preferences=prefs)

    candidate_embedding = embed_query(
        _candidate_profile_text(candidate_json) or candidate_json.get("current_role", "")
    )

    initial_state: PipelineState = {
        "run_id": run_id,
        "profile_id": profile_id,
        "candidate_json": candidate_json,
        "candidate_embedding": candidate_embedding,
        "preferences": prefs,
        "progress": [],
    }

    try:
        result_state = await pipeline.ainvoke(initial_state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job discovery pipeline crashed for run %s", run_id)
        async with session_factory() as session:
            repo = JobDiscoveryRepository(session)
            await repo.finish_run(
                run_id,
                status="error",
                message=str(exc),
                search_queries=[],
                jobs_discovered=0,
                jobs_after_filter=0,
                embedding_provider=Cfg.EMBEDDING_PROVIDER,
                llm_model=Cfg.LLM_MODEL,
            )
        return JobDiscoveryResult(run_id=run_id, status="error", message=str(exc))

    search_queries = result_state.get("search_queries", [])
    jobs_discovered = len(result_state.get("raw_jobs", []))
    jobs_after_filter = len(result_state.get("filtered_jobs", []))
    final_jobs = result_state.get("final_jobs", [])

    if result_state.get("error"):
        status, message = "error", result_state["error"]
    elif not final_jobs:
        status, message = "no_jobs", "No jobs survived search, crawling and filtering for this run."
    elif not final_jobs[0]["judge"]["used_llm_judge"]:
        status, message = (
            "degraded_no_llm",
            "LLM judge unavailable this run; ranked by hybrid score only.",
        )
    else:
        status, message = "ok", ""

    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        await repo.finish_run(
            run_id,
            status=status,
            message=message,
            search_queries=search_queries,
            jobs_discovered=jobs_discovered,
            jobs_after_filter=jobs_after_filter,
            embedding_provider=Cfg.EMBEDDING_PROVIDER,
            llm_model=Cfg.LLM_MODEL if GlobalConfig.GOOGLE_API_KEY else "",
        )

    return store._result_from_state(
        run_id=run_id,
        status=status,
        message=message,
        search_queries=search_queries,
        jobs_discovered=jobs_discovered,
        jobs_after_filter=jobs_after_filter,
        final_jobs=final_jobs,
    )


async def get_run(run_id: UUID, user_id: str | None = None) -> JobDiscoveryResult | None:
    """Read back one run by id. `user_id` is optional so internal
    module-to-module calls can read without an authenticated user, but
    any request originating from a user MUST pass it."""
    return await store.get_run(run_id, user_id=user_id)


async def get_latest_run(profile_id: UUID, user_id: str | None = None) -> JobDiscoveryResult | None:
    """Most recent job discovery run for a profile, or None."""
    return await store.get_latest_run(profile_id, user_id=user_id)


async def get_runs(
    profile_id: UUID, user_id: str | None = None, limit: int = 10
) -> list[JobDiscoveryResult]:
    """Up to `limit` past runs for a profile, most recent first."""
    return await store.get_runs(profile_id, user_id=user_id, limit=limit)


async def get_run_profile_id(run_id: UUID, user_id: str) -> UUID | None:
    """Resolve an owned run to its source profile for cross-module validation."""
    async with get_session_factory()() as session:
        return await JobDiscoveryRepository(session).get_profile_id(run_id, user_id)
