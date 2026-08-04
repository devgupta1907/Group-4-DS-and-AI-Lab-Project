"""Resume Parsing — the module that turns an uploaded resume into a profile.

The only things the rest of the application may use:

    register_resume_parsing(app)   mount the module
    ResumeParsingService           the behaviour contract
    UploadedResume, CandidateProfile, ProfileRecord, ...   its shapes

Everything under `internal/` is private. See `AGENTS.md` in this directory.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.resume_parsing.errors import ResumeParsingError, register_error_handlers
from src.resume_parsing.router import router
from src.resume_parsing.schemas import CandidateProfile, ProfileRecord, ProfileSummary
from src.resume_parsing.service import ResumeParsingService, UploadedResume


def register_resume_parsing(app: FastAPI) -> None:
    """Mount this module onto an application."""
    register_error_handlers(app)
    app.include_router(router)


__all__ = [
    "CandidateProfile",
    "ProfileRecord",
    "ProfileSummary",
    "ResumeParsingError",
    "ResumeParsingService",
    "UploadedResume",
    "register_resume_parsing",
]
