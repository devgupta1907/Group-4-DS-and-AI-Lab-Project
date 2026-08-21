"""Wire models for the Resume Parsing module.

These mirror `internal/prompts/parsed_resume_schema.json` exactly. They are the
shape the frontend receives and the shape downstream modules may assume. Nothing
here knows about databases, providers or files.

PII note: there is deliberately no `email` or `phone` field anywhere in this
file. See `AGENTS.md` § PII contract.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.resume_parsing.location import locality_only


class _Strict(BaseModel):
    """Rejects unknown keys, so an off-schema field can never reach the client."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Profile sections
# --------------------------------------------------------------------------- #


class Contact(_Strict):
    name: str | None = None
    location: str | None = Field(
        default=None,
        description="Locality only; street, building, unit and postal data are removed.",
    )
    links: list[str] = Field(default_factory=list)

    _protect_location = field_validator("location", mode="before")(locality_only)


class Education(_Strict):
    degree: str | None = None
    field: str | None = None
    institution: str | None = None
    start_year: str | None = None
    end_year: str | None = None


class Experience(_Strict):
    job_title: str | None = None
    company: str | None = None
    location: str | None = Field(
        default=None,
        description="Locality only; street, building, unit and postal data are removed.",
    )
    start_date: str | None = None
    end_date: str | None = None
    current_role: bool | None = None
    description: str | None = None

    _protect_location = field_validator("location", mode="before")(locality_only)


class Project(_Strict):
    name: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class Certification(_Strict):
    name: str | None = None
    issuer: str | None = None
    year: str | None = None


class CandidateProfile(_Strict):
    """The one artifact this module publishes to the rest of the system."""

    contact: Contact = Field(default_factory=Contact)
    skills: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Parse lifecycle
# --------------------------------------------------------------------------- #


class ParseStage(StrEnum):
    """User-visible stages, streamed in order. Matches MS3 §3.6."""

    RECEIVED = "received"
    READING = "reading"
    EXTRACTING = "extracting"
    REFINING = "refining"
    PERSISTING = "persisting"
    READY = "ready"


STAGE_LABELS: dict[ParseStage, str] = {
    ParseStage.RECEIVED: "Upload received",
    ParseStage.READING: "Reading document",
    ParseStage.EXTRACTING: "Extracting fields",
    ParseStage.REFINING: "Refining",
    ParseStage.PERSISTING: "Saving profile",
    ParseStage.READY: "Profile ready",
}


class ParseRoute(StrEnum):
    TEXT = "text"
    VISION = "vision"


class ProfileSummary(_Strict):
    """Enough to list a profile without decrypting the whole thing."""

    id: UUID
    filename: str
    route: ParseRoute
    page_count: int
    is_valid: bool
    needs_review: list[str] = Field(default_factory=list)
    created_at: datetime


class ProfileRecord(_Strict):
    """A persisted profile plus the provenance the UI shows alongside it."""

    id: UUID
    filename: str
    route: ParseRoute
    page_count: int
    is_valid: bool
    needs_review: list[str] = Field(default_factory=list)
    model_used: str
    fallback_used: bool
    created_at: datetime
    edited_at: datetime | None = None
    profile: CandidateProfile


# --------------------------------------------------------------------------- #
# SSE event payloads — the router serialises these verbatim
# --------------------------------------------------------------------------- #


class StageEvent(_Strict):
    type: Literal["stage"] = "stage"
    stage: ParseStage
    label: str
    detail: str | None = None


class ProfileEvent(_Strict):
    type: Literal["profile"] = "profile"
    record: ProfileRecord


class ErrorEvent(_Strict):
    type: Literal["error"] = "error"
    code: str
    message: str


ParseEvent = StageEvent | ProfileEvent | ErrorEvent
