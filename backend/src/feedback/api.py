"""
User feedback API.

    POST /api/feedback           submit a rating, reasons and a comment
    GET  /api/feedback/mine      the current user's past submissions
    GET  /api/feedback/summary   aggregate across all responses
    GET  /api/feedback/reasons   the reason list, so the UI is not a second
                                 copy of it

The summary endpoint exists so the response rate and mean rating can be
reported without querying the database by hand. It is unauthenticated by
design in this build — see the note on it below.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.security import CurrentUserDep
from src.feedback.internal.repository import FeedbackRepository
from src.feedback.schemas import (
    REASON_CHOICES,
    REASON_LABELS,
    FeedbackRecord,
    FeedbackSummary,
    SubmitFeedbackRequest,
)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _to_record(row) -> FeedbackRecord:
    return FeedbackRecord(
        feedback_id=row.id,
        rating=row.rating,
        reasons=row.reasons or [],
        comment=row.comment or "",
        profile_id=row.profile_id,
        created_at=row.created_at,
    )


@router.get("/reasons")
def list_reasons() -> list[dict[str, str]]:
    """The reason options, served from the same constant the validator uses."""
    return [{"value": value, "label": REASON_LABELS[value]} for value in REASON_CHOICES]


@router.post("", response_model=FeedbackRecord, status_code=201)
async def submit_feedback(
    request: SubmitFeedbackRequest, user: CurrentUserDep, session: SessionDep
) -> FeedbackRecord:
    unknown = [r for r in request.reasons if r not in REASON_CHOICES]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown reason(s): {', '.join(unknown)}. Call /api/feedback/reasons for the list.",
        )

    # De-duplicated but order preserved, so a UI that sends a value twice does
    # not distort the counts.
    reasons = list(dict.fromkeys(request.reasons))

    row = await FeedbackRepository(session).save(
        user_id=user.id,
        rating=request.rating,
        reasons=reasons,
        comment=request.comment.strip(),
        profile_id=request.profile_id,
    )
    return _to_record(row)


@router.get("/mine", response_model=list[FeedbackRecord])
async def my_feedback(user: CurrentUserDep, session: SessionDep) -> list[FeedbackRecord]:
    rows = await FeedbackRepository(session).list_for_user(user.id)
    return [_to_record(row) for row in rows]


@router.get("/summary", response_model=FeedbackSummary)
async def summary(session: SessionDep) -> FeedbackSummary:
    """
    Aggregate across all responses.

    No user filter: this is the reporting view, and per-user aggregates of a
    handful of responses would not be meaningful. It returns counts only —
    never comments or identifiers — so it exposes no individual response.
    Before any deployment beyond coursework this should sit behind an admin
    check rather than being open.
    """
    responses, mean, distribution, reason_counts = await FeedbackRepository(session).summarise()
    return FeedbackSummary(
        responses=responses,
        mean_rating=mean,
        rating_distribution=distribution,
        reason_counts=reason_counts,
    )
