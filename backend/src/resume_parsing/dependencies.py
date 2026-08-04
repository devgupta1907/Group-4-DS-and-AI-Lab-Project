"""Composition root for the Resume Parsing module.

This is the one place that knows how the module is assembled: it reaches into
`internal/` to build the concrete service and hands the router something that
satisfies `ResumeParsingService` and nothing more.

It is also the only file outside `internal/` permitted to name an infrastructure
type (`AsyncSession`), because wiring is precisely its job.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.resume_parsing.errors import ProviderNotConfigured
from src.resume_parsing.internal.crypto import ProfileCipherUnavailable, build_cipher
from src.resume_parsing.internal.providers.base import ExtractionProvider
from src.resume_parsing.internal.providers.google_ai_studio import build_provider
from src.resume_parsing.internal.repository import ResumeParsingRepository
from src.resume_parsing.internal.service_impl import ResumeParsingServiceImpl
from src.resume_parsing.service import ResumeParsingService


def _provider_factory() -> ExtractionProvider:
    """Built on demand, not at request time.

    Only `parse` needs a model; listing and reading profiles do not. Building
    eagerly would make every read fail with 503 on a server that has no API key
    configured, which is both wrong and confusing to debug.
    """
    try:
        return build_provider()
    except Exception as exc:
        raise ProviderNotConfigured(
            "GOOGLE_AI_STUDIO_API_KEY is missing or invalid."
        ) from exc


def get_resume_parsing_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResumeParsingService:
    try:
        cipher = build_cipher()
    except ProfileCipherUnavailable as exc:
        raise ProviderNotConfigured(str(exc)) from exc

    return ResumeParsingServiceImpl(
        repository=ResumeParsingRepository(session, cipher),
        provider_factory=_provider_factory,
    )


ServiceDep = Annotated[ResumeParsingService, Depends(get_resume_parsing_service)]
