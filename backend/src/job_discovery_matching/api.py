"""
Job Discovery & Matching — API layer.

    POST /jobs/search                     run job discovery against a stored profile
    GET  /jobs/status/{run_id}            read one run back by id
    GET  /jobs/runs/{profile_id}          read the most recent run for a profile
    GET  /jobs/runs/{profile_id}/history  read up to 10 past runs for a profile

MERGE NOTE
    Same rule career_recommendation's api.py already documents: the
    candidate profile is always read back through resume_parsing's
    public service (which decrypts it), never by querying its tables —
    `.importlinter` forbids reaching into `resume_parsing.internal`.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.core.security import CurrentUser, get_current_user
from src.job_discovery_matching import service
from src.job_discovery_matching.models import (
    JobDiscoveryResult,
    JudgeConfirmationRequest,
    QuerySelectionRequest,
    SearchPreferences,
)
from src.resume_parsing.dependencies import get_resume_parsing_service
from src.resume_parsing.errors import ProfileNotFound
from src.resume_parsing.service import ResumeParsingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["job-discovery-matching"])


class SearchRequest(SearchPreferences):
    """Extends SearchPreferences with the profile to search against.

    Unlike career_recommendation's /recommend, there is no inline-profile
    testing path here: every job discovery run crawls real external
    pages and is worth persisting, so `profile_id` is always required.
    """

    profile_id: UUID


@router.post("/search", response_model=JobDiscoveryResult)
async def search(
    request: SearchRequest,
    user: CurrentUser = Depends(get_current_user),
    resume_service: ResumeParsingService = Depends(get_resume_parsing_service),
) -> JobDiscoveryResult:
    """
    Runs query-generate, then PAUSES — see `models.JobDiscoveryResult`'s
    "awaiting_query_selection" status. The response for a healthy run
    always looks like:

        {"run_id": "...", "status": "awaiting_query_selection",
         "generated_queries": ["Data Analyst jobs", "SQL Python analyst jobs", ...]}

    Show `generated_queries` to the user, then call
    POST /api/jobs/search/{run_id}/select-queries with whichever they pick
    (edited or not) to continue: search -> crawl -> filter -> rank -> judge.
    """
    try:
        record = await resume_service.get_profile(request.profile_id, user)
    except ProfileNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=f"No profile {request.profile_id} for this user.",
        ) from exc

    preferences = SearchPreferences(
        target_location=request.target_location,
        remote_only=request.remote_only,
        min_salary_lpa=request.min_salary_lpa,
    )

    try:
        return await service.discover_jobs_for_profile(
            record.profile,
            profile_id=request.profile_id,
            user_id=user.id,
            preferences=preferences,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job discovery pipeline failed for profile %s", request.profile_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/search/{run_id}/select-queries", response_model=JobDiscoveryResult)
async def select_queries(
    run_id: UUID,
    request: QuerySelectionRequest,
    user: CurrentUser = Depends(get_current_user),
) -> JobDiscoveryResult:
    """Resumes a run paused at status="awaiting_query_selection" with the
    queries the user picked (a subset, all of them, or edited text — the
    pipeline doesn't distinguish). Runs through hybrid ranking and PAUSES
    AGAIN at status="awaiting_judge_confirmation" — see `confirm_judge`
    below — rather than running the LLM judge automatically."""
    try:
        return await service.resume_query_selection(
            run_id,
            user_id=user.id,
            selected_queries=request.selected_queries,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job discovery pipeline failed resuming run %s", run_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/search/{run_id}/confirm-judge", response_model=JobDiscoveryResult)
async def confirm_judge(
    run_id: UUID,
    request: JudgeConfirmationRequest,
    user: CurrentUser = Depends(get_current_user),
) -> JobDiscoveryResult:
    """Resumes a run paused at status="awaiting_judge_confirmation" (whose
    `top_jobs` already show the hybrid-ranked jobs — judge=None on each).
    `proceed=True` spends the LLM judge call and returns status "ok" or
    "degraded_no_llm"; `proceed=False` returns status "hybrid_only" with
    the SAME jobs, unmodified, no LLM call made."""
    try:
        logger.info(
            "confirm_judge received: run_id=%s proceed=%r selected_job_urls=%r",
            run_id, request.proceed, request.selected_job_urls,
        )
        return await service.resume_judge_confirmation(
            run_id,
            user_id=user.id,
            proceed=request.proceed,
            selected_job_urls=request.selected_job_urls,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job discovery pipeline failed resuming run %s", run_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status/{run_id}", response_model=JobDiscoveryResult)
async def get_status(
    run_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> JobDiscoveryResult:
    result = await service.get_run(run_id, user_id=user.id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No job discovery run {run_id} for this user.")
    return result


@router.get("/runs/{profile_id}", response_model=JobDiscoveryResult)
async def get_latest(
    profile_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> JobDiscoveryResult:
    """Returns the most recently saved run for a profile."""
    result = await service.get_latest_run(profile_id, user_id=user.id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No saved job discovery runs for profile {profile_id}. "
            "Runs are only saved when POST /jobs/search is called with this profile_id.",
        )
    return result


@router.get("/runs/{profile_id}/history", response_model=list[JobDiscoveryResult])
async def get_history(
    profile_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> list[JobDiscoveryResult]:
    return await service.get_runs(profile_id, user_id=user.id, limit=10)
