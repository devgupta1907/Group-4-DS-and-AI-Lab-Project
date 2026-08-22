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

from fastapi import APIRouter, Body, File, UploadFile, status
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


@router.post(
    "/profiles/manual", response_model=ProfileRecord, status_code=status.HTTP_201_CREATED
)
async def submit_manual_profile(
    service: ServiceDep,
    user: CurrentUserDep,
    profile: Annotated[CandidateProfile, Body()],
) -> ProfileRecord:
    """Saves a profile typed in directly — no upload, no parsing. Body is a
    full `CandidateProfile` (the same shape `ManualProfileForm` on the
    frontend already builds). Returns a normal `ProfileRecord`, same shape
    a completed parse returns, with `route: "manual"`."""
    return await service.submit_manual_profile(profile, user)


@router.get("/profiles/{profile_id}", response_model=ProfileRecord)
async def get_profile(
    profile_id: UUID, service: ServiceDep, user: CurrentUserDep
) -> ProfileRecord:
    return await service.get_profile(profile_id, user)


@router.patch("/profiles/{profile_id}", response_model=ProfileRecord)
async def update_profile(
    profile_id: UUID,
    service: ServiceDep,
    user: CurrentUserDep,
    profile: Annotated[CandidateProfile, Body()],
) -> ProfileRecord:
    """Overwrites the stored profile with candidate-edited content — e.g.
    adding `contact.location` when the resume didn't state one, or fixing
    a misparsed job title, before career recommendation or job discovery
    runs against it. Body is the FULL `CandidateProfile` shape (same as
    `ProfileRecord.profile` from GET), not a partial patch: fetch first,
    edit client-side, send the whole thing back."""
    return await service.update_profile(profile_id, user, profile)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: UUID, service: ServiceDep, user: CurrentUserDep
) -> None:
    await service.delete_profile(profile_id, user)
