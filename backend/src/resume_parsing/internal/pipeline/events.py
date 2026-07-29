"""Progress event construction.

Kept in one place so the wording the user sees is defined once, next to the
stage it describes, rather than scattered through the orchestrator.
"""

from __future__ import annotations

from src.resume_parsing.errors import ResumeParsingError
from src.resume_parsing.schemas import (
    STAGE_LABELS,
    ErrorEvent,
    ParseStage,
    ProfileEvent,
    ProfileRecord,
    StageEvent,
)


def stage(stage: ParseStage, detail: str | None = None) -> StageEvent:
    return StageEvent(stage=stage, label=STAGE_LABELS[stage], detail=detail)


def profile(record: ProfileRecord) -> ProfileEvent:
    return ProfileEvent(record=record)


def failure(error: ResumeParsingError) -> ErrorEvent:
    return ErrorEvent(code=error.code, message=error.message)
