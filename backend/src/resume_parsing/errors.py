"""Error taxonomy for the Resume Parsing module.

Every failure the module can surface has a stable machine-readable `code`, so
the UI can react to it without string-matching prose. Messages are safe to show
to a user: they never echo resume content.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class ResumeParsingError(Exception):
    """Base class. `code` is part of the module's public contract."""

    code = "resume_parsing_error"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "Resume parsing failed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class UnsupportedFileType(ResumeParsingError):
    code = "unsupported_file_type"
    http_status = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    message = "Upload a PDF, DOCX, PNG or JPEG resume."


class FileTooLarge(ResumeParsingError):
    code = "file_too_large"
    http_status = 413
    message = "That file is larger than the upload limit."


class TooManyPages(ResumeParsingError):
    code = "too_many_pages"
    http_status = 422
    message = "That resume has more pages than this module accepts."


class UnreadableDocument(ResumeParsingError):
    code = "unreadable_document"
    http_status = 422
    message = "That file could not be opened. It may be corrupt or password-protected."


class ExtractionFailed(ResumeParsingError):
    code = "extraction_failed"
    http_status = status.HTTP_502_BAD_GATEWAY
    message = "The extraction model could not be reached. Try again shortly."


class ProviderNotConfigured(ResumeParsingError):
    code = "provider_not_configured"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "The extraction provider is not configured on this server."


class ProfileNotFound(ResumeParsingError):
    code = "profile_not_found"
    http_status = status.HTTP_404_NOT_FOUND
    message = "No such profile."


class EmptyManualProfile(ResumeParsingError):
    code = "empty_manual_profile"
    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = (
        "Add at least one skill, job title, piece of experience, education "
        "or project before saving."
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ResumeParsingError)
    async def _handle(_: Request, exc: ResumeParsingError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": exc.message},
        )
