"""The SSE wire contract, verified against a doubled service.

The double satisfies `ResumeParsingService` and nothing else — which is exactly
what the router is allowed to know about. That these tests need no database, no
encryption key and no API key is the practical proof that rule 3 holds.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.security import CurrentUser
from src.resume_parsing import register_resume_parsing
from src.resume_parsing.dependencies import get_resume_parsing_service
from src.resume_parsing.errors import ProfileNotFound, UnsupportedFileType
from src.resume_parsing.internal.pipeline import events
from src.resume_parsing.schemas import (
    CandidateProfile,
    Contact,
    ParseEvent,
    ParseRoute,
    ParseStage,
    ProfileRecord,
    ProfileSummary,
)
from src.resume_parsing.service import ResumeParsingService, UploadedResume

PROFILE_ID = UUID("11111111-1111-1111-1111-111111111111")


def _record() -> ProfileRecord:
    return ProfileRecord(
        id=PROFILE_ID,
        filename="cv.pdf",
        route=ParseRoute.VISION,
        page_count=1,
        is_valid=True,
        needs_review=["projects"],
        model_used="gemma-3-27b-it",
        fallback_used=False,
        created_at=datetime.now(UTC),
        profile=CandidateProfile(contact=Contact(name="Jane Doe"), skills=["Python"]),
    )


class StubService:
    """A stand-in that satisfies the contract in `service.py`."""

    def __init__(self, *, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.deleted: list[UUID] = []

    async def parse(
        self, upload: UploadedResume, user: CurrentUser
    ) -> AsyncIterator[ParseEvent]:
        yield events.stage(ParseStage.RECEIVED, upload.filename)
        if isinstance(self.fail_with, UnsupportedFileType):
            yield events.failure(self.fail_with)
            return
        yield events.stage(ParseStage.EXTRACTING)
        yield events.stage(ParseStage.READY)
        yield events.profile(_record())

    async def get_profile(self, profile_id: UUID, user: CurrentUser) -> ProfileRecord:
        if profile_id != PROFILE_ID:
            raise ProfileNotFound()
        return _record()

    async def list_profiles(self, user: CurrentUser) -> list[ProfileSummary]:
        record = _record()
        return [
            ProfileSummary(
                id=record.id,
                filename=record.filename,
                route=record.route,
                page_count=record.page_count,
                is_valid=record.is_valid,
                needs_review=record.needs_review,
                created_at=record.created_at,
            )
        ]

    async def delete_profile(self, profile_id: UUID, user: CurrentUser) -> None:
        if profile_id != PROFILE_ID:
            raise ProfileNotFound()
        self.deleted.append(profile_id)


def build_client(service: StubService) -> AsyncClient:
    app = FastAPI()
    register_resume_parsing(app)
    app.dependency_overrides[get_resume_parsing_service] = lambda: service
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def parse_frames(body: str) -> list[tuple[str, dict]]:
    """Decode an SSE body into (event name, payload) pairs."""
    frames = []
    for block in body.strip().split("\n\n"):
        lines = dict(
            line.split(": ", 1) for line in block.splitlines() if ": " in line
        )
        if "event" in lines:
            frames.append((lines["event"], json.loads(lines.get("data", "{}"))))
    return frames


@pytest.fixture
def stub() -> StubService:
    return StubService()


async def test_upload_streams_stages_then_the_profile(stub: StubService) -> None:
    async with build_client(stub) as client:
        response = await client.post(
            "/api/resume-parsing/resumes",
            files={"file": ("cv.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    frames = parse_frames(response.text)
    assert [name for name, _ in frames] == [
        "stage", "stage", "stage", "profile", "done",
    ]

    stages = [payload["stage"] for name, payload in frames if name == "stage"]
    assert stages == ["received", "extracting", "ready"]

    _, profile_frame = frames[3]
    assert profile_frame["record"]["profile"]["contact"]["name"] == "Jane Doe"
    assert profile_frame["record"]["needs_review"] == ["projects"]


async def test_stage_frames_carry_a_human_label(stub: StubService) -> None:
    async with build_client(stub) as client:
        response = await client.post(
            "/api/resume-parsing/resumes",
            files={"file": ("cv.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
    labels = [p["label"] for name, p in parse_frames(response.text) if name == "stage"]
    assert labels == ["Upload received", "Extracting fields", "Profile ready"]


async def test_a_rejected_upload_arrives_as_an_error_frame_on_a_200() -> None:
    """The stream has already committed 200, so failures ride the stream."""
    service = StubService(fail_with=UnsupportedFileType())
    async with build_client(service) as client:
        response = await client.post(
            "/api/resume-parsing/resumes",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

    assert response.status_code == 200
    frames = parse_frames(response.text)
    names = [name for name, _ in frames]
    assert names == ["stage", "error", "done"]
    assert frames[1][1]["code"] == "unsupported_file_type"


async def test_no_profile_payload_ever_carries_contact_pii(stub: StubService) -> None:
    async with build_client(stub) as client:
        response = await client.post(
            "/api/resume-parsing/resumes",
            files={"file": ("cv.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
    body = response.text.lower()
    assert '"email"' not in body
    assert '"phone"' not in body


async def test_profile_is_retrievable_after_the_stream(stub: StubService) -> None:
    async with build_client(stub) as client:
        response = await client.get(f"/api/resume-parsing/profiles/{PROFILE_ID}")
    assert response.status_code == 200
    assert response.json()["profile"]["skills"] == ["Python"]


async def test_listing_returns_summaries(stub: StubService) -> None:
    async with build_client(stub) as client:
        response = await client.get("/api/resume-parsing/profiles")
    assert response.status_code == 200
    assert response.json()[0]["filename"] == "cv.pdf"


async def test_a_missing_profile_maps_to_404_with_a_stable_code(stub: StubService) -> None:
    async with build_client(stub) as client:
        response = await client.get(f"/api/resume-parsing/profiles/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "profile_not_found"


async def test_deleting_a_profile_returns_204(stub: StubService) -> None:
    async with build_client(stub) as client:
        response = await client.delete(f"/api/resume-parsing/profiles/{PROFILE_ID}")
    assert response.status_code == 204
    assert stub.deleted == [PROFILE_ID]


def test_the_stub_actually_satisfies_the_contract() -> None:
    """If this fails, the tests above are checking a shape nobody implements."""
    assert isinstance(StubService(), ResumeParsingService)
