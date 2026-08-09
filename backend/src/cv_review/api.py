"""
CV review API.

    POST /api/cv-review    critique the stored parsed profile

Reads the profile through resume_parsing's public service, the same boundary
career_recommendation and job_discovery_matching cross. Nothing is persisted,
so repeat calls are recomputed rather than cached — the review is cheap
(one model call) and a candidate editing their CV wants the new answer, not
the old one.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from src.core.security import CurrentUserDep
from src.cv_review import service
from src.cv_review.schemas import CvReview, ReviewCvRequest
from src.resume_parsing.dependencies import ServiceDep
from src.resume_parsing.errors import ProfileNotFound

router = APIRouter(prefix="/api/cv-review", tags=["cv-review"])


@router.post("", response_model=CvReview)
async def review_cv(
    request: ReviewCvRequest, user: CurrentUserDep, resume_service: ServiceDep
) -> CvReview:
    try:
        record = await resume_service.get_profile(request.profile_id, user)
    except ProfileNotFound as exc:
        raise HTTPException(
            status_code=404, detail=f"No profile {request.profile_id} for this user."
        ) from exc

    # The model call is synchronous and blocking, so it goes to a worker
    # thread rather than stalling the event loop for the ~5 seconds it takes.
    return await asyncio.to_thread(
        service.review_profile, record.profile, request.profile_id
    )
