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

from langgraph.types import Command

from src.core.config import GlobalConfig
from src.core.db import get_session_factory
from src.job_discovery_matching import store
from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.graph import get_pipeline
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
from src.job_discovery_matching.internal.services.embedding_client import embed_query
from src.job_discovery_matching.models import JobDiscoveryResult, SearchPreferences
from src.job_discovery_matching.profile_mapper import from_parsed_resume, has_usable_signal
from src.resume_parsing.schemas import CandidateProfile as ParsedProfile
from src.career_recommendation import store as career_store
logger = logging.getLogger(__name__)


def _thread_config(run_id: UUID) -> dict:
    """Every checkpointed call for a given run uses this SAME thread_id —
    it's what lets `resume_query_selection()`, invoked from a completely
    separate HTTP request (and possibly a different worker process), find
    and continue the exact paused graph state `start_job_discovery()` left
    behind at query_selection_gate."""
    return {"configurable": {"thread_id": str(run_id)}}


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
    candidate_json = from_parsed_resume(profile, preferences=prefs)

    # Chain the modules: search on the ESCO occupations Career Recommendation
    # produced, not just the candidate's own past job titles. "agricultural
    # engineer" is a far better search term than "AGRICULTURAL CONNECTIVITY
    # VALIDATION TEST ENGINEER". Falls through silently when no recommendation
    # exists, so job discovery still works standalone.
    #
    # If the candidate explicitly SELECTED one or more occupations from that
    # run (via POST /career/recommendations/{run_id}/select), those choices
    # win outright — a direct signal of intent, stronger than any ranking
    # heuristic. Only when nothing was selected do we fall back to the top
    # 2 recommendations, same as before.
    try:
        run = career_store.get_latest_run(profile_id, user_id=user_id)
        recommendations = (run or {}).get("result", {}).get("recommendations", [])
        if recommendations:
            selected_uris = run["result"].get("selected_occupation_uris") or []
            if selected_uris:
                selected_titles = run["result"].get("selected_occupation_titles") or []
                titles = [t for t in selected_titles if t]
                logger.info(
                    "Seeded target_roles from user-selected occupations: %s", titles
                )
            else:
                titles = [
                    r["occupation_title"]
                    for r in recommendations[:2]
                    if r.get("occupation_title")
                ]
                logger.info("Seeded target_roles from career recommendation: %s", titles)
            existing = candidate_json.get("target_roles") or []
            candidate_json["target_roles"] = titles + [t for t in existing if t not in titles]
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

    pipeline = await get_pipeline()
    config = _thread_config(run_id)

    try:
        result_state = await pipeline.ainvoke(initial_state, config=config)
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

    return await _handle_result_state(run_id, result_state, session_factory)


async def resume_query_selection(
    run_id: UUID,
    *,
    user_id: str,
    selected_queries: list[str],
) -> JobDiscoveryResult:
    """Continues a run paused at query_selection_gate (status
    "awaiting_query_selection") with the queries the user actually picked.
    Runs db_cache_module -> ... -> rank_persist_module -> judge_confirmation_gate
    from there, using the SAME thread_id (run_id) so the checkpointer
    resumes the exact state `discover_jobs_for_profile()` left behind —
    nothing before query_selection_gate re-runs. Lands on the SECOND
    interrupt (judge_confirmation_gate) in the normal case, same as
    `discover_jobs_for_profile()` lands on the first — see
    `_handle_result_state()`."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        run = await repo.get_run(run_id, user_id=user_id)
    if run is None:
        return JobDiscoveryResult(run_id=run_id, status="error", message="Run not found.")
    if run.status != "awaiting_query_selection":
        return JobDiscoveryResult(
            run_id=run_id,
            status="error",
            message=f"Run is not awaiting query selection (status={run.status!r}).",
        )

    pipeline = await get_pipeline()
    config = _thread_config(run_id)

    try:
        result_state = await pipeline.ainvoke(Command(resume=selected_queries), config=config)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job discovery pipeline crashed resuming run %s", run_id)
        async with session_factory() as session:
            repo = JobDiscoveryRepository(session)
            await repo.finish_run(
                run_id,
                status="error",
                message=str(exc),
                search_queries=selected_queries,
                jobs_discovered=0,
                jobs_after_filter=0,
                embedding_provider=Cfg.EMBEDDING_PROVIDER,
                llm_model=Cfg.LLM_MODEL,
            )
        return JobDiscoveryResult(run_id=run_id, status="error", message=str(exc))

    return await _handle_result_state(run_id, result_state, session_factory)


async def resume_judge_confirmation(
    run_id: UUID,
    *,
    user_id: str,
    proceed: bool,
    selected_job_urls: list[str] | None = None,
) -> JobDiscoveryResult:
    """Continues a run paused at judge_confirmation_gate (status
    "awaiting_judge_confirmation"). proceed=True runs judge_module (the
    LLM judge call) over the already-persisted hybrid rankings;
    proceed=False runs hybrid_finalize_module instead — both are terminal,
    this always reaches END, never a third interrupt.

    `selected_job_urls`, when non-empty, restricts judge_module to only
    those jobs (matched on source_url) instead of the full ranked list —
    the user picking a subset of `top_jobs` in the confirmation step."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        run = await repo.get_run(run_id, user_id=user_id)
    if run is None:
        return JobDiscoveryResult(run_id=run_id, status="error", message="Run not found.")
    if run.status != "awaiting_judge_confirmation":
        return JobDiscoveryResult(
            run_id=run_id,
            status="error",
            message=f"Run is not awaiting judge confirmation (status={run.status!r}).",
        )

    pipeline = await get_pipeline()
    config = _thread_config(run_id)

    try:
        result_state = await pipeline.ainvoke(
            Command(resume={"proceed": proceed, "selected_job_urls": selected_job_urls}),
            config=config,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job discovery pipeline crashed resuming run %s", run_id)
        async with session_factory() as session:
            repo = JobDiscoveryRepository(session)
            await repo.finish_run(
                run_id,
                status="error",
                message=str(exc),
                search_queries=run.search_queries or [],
                jobs_discovered=run.jobs_discovered,
                jobs_after_filter=run.jobs_after_filter,
                embedding_provider=Cfg.EMBEDDING_PROVIDER,
                llm_model=Cfg.LLM_MODEL,
            )
        return JobDiscoveryResult(run_id=run_id, status="error", message=str(exc))

    return await _handle_result_state(run_id, result_state, session_factory)


async def _handle_result_state(run_id: UUID, result_state: PipelineState, session_factory) -> JobDiscoveryResult:
    """Every call into the pipeline (initial invoke, or either resume) ends
    up here. Inspects `result_state["__interrupt__"]` to tell which of the
    three outcomes happened:

      - no interrupt              -> run reached END, persist + return final result
      - kind="select_search_queries" -> paused at query_selection_gate (1st gate)
      - kind="confirm_judge"          -> paused at judge_confirmation_gate (2nd gate)

    Centralizing this means a node execution order change (e.g. adding a
    third gate later) only needs a new `elif` here, not new duplicate
    interrupt-handling code in every resume function."""
    interrupts = result_state.get("__interrupt__")
    if not interrupts:
        return await _finalize_run(run_id, result_state, session_factory)

    payload = interrupts[0].value
    kind = payload.get("kind") if isinstance(payload, dict) else None

    if kind == "select_search_queries":
        generated_queries = payload.get("generated_queries", [])
        async with session_factory() as session:
            repo = JobDiscoveryRepository(session)
            await repo.set_awaiting_query_selection(run_id, generated_queries=generated_queries)
        return JobDiscoveryResult(
            run_id=run_id,
            status="awaiting_query_selection",
            message="Pick which generated search queries to actually run.",
            generated_queries=generated_queries,
        )

    if kind == "confirm_judge":
        # ranked_jobs already carries bm25/embedding/hybrid_score + job_json
        # + source_url + rank_position (rank_persist_module ran before this
        # gate) — store._result_from_state tolerates the missing "judge"/
        # "final_score" keys (falls back to hybrid_score), so the SAME
        # helper builds this preview as the terminal result.
        ranked_jobs = result_state.get("ranked_jobs", [])
        async with session_factory() as session:
            repo = JobDiscoveryRepository(session)
            await repo.set_awaiting_judge_confirmation(run_id)
        preview = store._result_from_state(
            run_id=run_id,
            status="awaiting_judge_confirmation",
            message="Hybrid-ranked jobs are ready. Run the LLM judge for interview-probability scoring?",
            search_queries=result_state.get("search_queries", []),
            jobs_discovered=len(result_state.get("raw_jobs", [])),
            jobs_after_filter=len(result_state.get("filtered_jobs", [])),
            final_jobs=ranked_jobs,
        )
        return preview

    # Unknown interrupt kind — shouldn't happen outside active development
    # on the graph itself. Fail loudly rather than silently finalizing with
    # a run stuck mid-pipeline in the DB.
    logger.error("Unhandled interrupt kind %r for run %s", kind, run_id)
    return JobDiscoveryResult(
        run_id=run_id, status="error", message=f"Pipeline paused with an unrecognized interrupt: {kind!r}"
    )


async def _finalize_run(run_id: UUID, result_state: PipelineState, session_factory) -> JobDiscoveryResult:
    """Shared by the (rare) defensive path in discover_jobs_for_profile()
    and the normal completion path in resume_query_selection() — persists
    the run's terminal status and builds the API-facing result."""
    search_queries = result_state.get("search_queries", [])
    jobs_discovered = len(result_state.get("raw_jobs", []))
    jobs_after_filter = len(result_state.get("filtered_jobs", []))
    final_jobs = result_state.get("final_jobs", [])

    node_timings = result_state.get("node_timings", [])
    if node_timings:
        total_ms = sum(t["duration_ms"] for t in node_timings)
        breakdown = " | ".join(f"{t['node']}={t['duration_ms']:.0f}ms" for t in node_timings)
        slowest = max(node_timings, key=lambda t: t["duration_ms"])
        logger.info(
            "Run %s node timings (total %.0fms, slowest: %s @ %.0fms): %s",
            run_id, total_ms, slowest["node"], slowest["duration_ms"], breakdown,
        )

    if result_state.get("error"):
        status, message = "error", result_state["error"]
    elif not final_jobs:
        status, message = "no_jobs", "No jobs survived search, crawling and filtering for this run."
    elif final_jobs[0].get("judge") is None:
        # hybrid_finalize_module ran — the user deliberately declined the
        # judge stage at judge_confirmation_gate, not a failure.
        status, message = "hybrid_only", "Ranked by hybrid score only — LLM judge stage was skipped."
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
