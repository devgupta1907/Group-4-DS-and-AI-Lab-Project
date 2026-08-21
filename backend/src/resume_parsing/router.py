"""HTTP surface for the Resume Parsing module.

This file transports and serialises. It does not decide anything.

It may import: `service`, `schemas`, `errors`, `dependencies`, `core.security`.
It may NOT import: `internal.*`, `sqlalchemy`, `core.db`, any repository or ORM
model. `tests/resume_parsing/test_architecture.py` and `.importlinter` both fail
the build if that changes.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import StreamingResponse

from src.core.security import CurrentUserDep
from src.resume_parsing.dependencies import ServiceDep
from src.resume_parsing.schemas import CandidateProfile, ParseEvent, ProfileRecord, ProfileSummary
from src.resume_parsing.service import ResumeParsingService, UploadedResume

router = APIRouter(prefix="/api/resume-parsing", tags=["resume-parsing"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    # Stops nginx and friends from buffering the stream into one lump.
    "X-Accel-Buffering": "no",
}


def _frame(event: ParseEvent) -> str:
    """One SSE frame. `event:` lets the client dispatch without inspecting data."""
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return f"event: {event.type}\ndata: {payload}\n\n"


async def _stream(
    service: ResumeParsingService, upload: UploadedResume, user: CurrentUserDep
) -> AsyncIterator[str]:
    async for event in service.parse(upload, user):
        yield _frame(event)
    yield "event: done\ndata: {}\n\n"


@router.post("/resumes")
async def parse_resume(
    service: ServiceDep,
    user: CurrentUserDep,
    file: Annotated[UploadFile, File()],
) -> StreamingResponse:
    """Upload a resume and stream parse progress, then the profile.

    Server-Sent Events. Frames are `stage`, then exactly one of `profile` or
    `error`, then `done`. The response is a stream from the first byte, so
    failures after it opens arrive as an `error` frame rather than a status code.
    """
    upload = UploadedResume(
        filename=file.filename or "resume",
        content_type=file.content_type,
        content=await file.read(),
    )
    return StreamingResponse(
        _stream(service, upload, user),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/profiles", response_model=list[ProfileSummary])
async def list_profiles(service: ServiceDep, user: CurrentUserDep) -> list[ProfileSummary]:
    return await service.list_profiles(user)


@router.get("/profiles/{profile_id}", response_model=ProfileRecord)
async def get_profile(
    profile_id: UUID, service: ServiceDep, user: CurrentUserDep
) -> ProfileRecord:
    return await service.get_profile(profile_id, user)


@router.put("/profiles/{profile_id}", response_model=ProfileRecord)
async def update_profile(
    profile_id: UUID,
    profile: CandidateProfile,
    service: ServiceDep,
    user: CurrentUserDep,
) -> ProfileRecord:
    """Save a user-corrected profile. Full replacement, not a patch.

    Pydantic rejects anything off-schema before this handler ever runs
    (`CandidateProfile` still has `extra="forbid"`), so a client cannot smuggle
    an email or phone field back in through the edit path either.
    """
    return await service.update_profile(profile_id, profile, user)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: UUID, service: ServiceDep, user: CurrentUserDep
) -> None:
    await service.delete_profile(profile_id, user)
