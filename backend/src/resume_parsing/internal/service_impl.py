"""The orchestrator — the linear state machine behind `ResumeParsingService`.

    route -> preprocess -> extract -> merge -> validate -> [repair] -> persist

Two invariants this file is responsible for:

* **`parse` never raises for an expected failure.** Its first yield has already
  committed a 200 response with an open event stream, so a raised exception
  would reach the client as a truncated stream with no explanation. Expected
  failures are yielded as `ErrorEvent` instead.
* **Transient artifacts do not outlive the call.** Page bytes are dropped in a
  `finally` block on every exit path, including cancellation.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from time import perf_counter
from uuid import UUID

from src.core.config import get_settings
from src.core.security import CurrentUser
from src.resume_parsing.errors import (
    ExtractionFailed,
    ProfileNotFound,
    ResumeParsingError,
)
from src.resume_parsing.internal.document_conversion import (
    DocumentTextConversionError,
    DocumentTextConverter,
)
from src.resume_parsing.internal.domain import PageArtifact, ValidationReport
from src.resume_parsing.internal.pipeline import (
    events,
    extraction,
    postprocess,
    routing,
    validation,
)
from src.resume_parsing.internal.pipeline import preprocess as preprocessing
from src.resume_parsing.internal.providers.base import ExtractionProvider, ProviderError
from src.resume_parsing.internal.repository import ResumeParsingRepository, content_hash
from src.resume_parsing.schemas import (
    CandidateProfile,
    ParseEvent,
    ParseStage,
    ProfileRecord,
    ProfileSummary,
)
from src.resume_parsing.service import UploadedResume

logger = logging.getLogger(__name__)


class ResumeParsingServiceImpl:
    """Implements the module contract. Constructed per request in `dependencies`."""

    def __init__(
        self,
        repository: ResumeParsingRepository,
        provider_factory: Callable[[], ExtractionProvider],
        text_converter_factory: Callable[[], DocumentTextConverter],
    ) -> None:
        self._repository = repository
        self._provider_factory = provider_factory
        self._provider: ExtractionProvider | None = None
        self._text_converter_factory = text_converter_factory
        self._text_converter: DocumentTextConverter | None = None
        self._settings = get_settings()

    @property
    def _extraction(self) -> ExtractionProvider:
        """Resolved on first use, so read-only calls need no model configured."""
        if self._provider is None:
            self._provider = self._provider_factory()
        return self._provider

    @property
    def _document_text(self) -> DocumentTextConverter:
        """Resolve Docling only when the configured branch actually needs it."""
        if self._text_converter is None:
            self._text_converter = self._text_converter_factory()
        return self._text_converter

    # ------------------------------------------------------------------ parse --

    async def parse(
        self, upload: UploadedResume, user: CurrentUser
    ) -> AsyncIterator[ParseEvent]:
        job_id: UUID | None = None
        pages: list[PageArtifact] = []
        try:
            yield events.stage(ParseStage.RECEIVED, upload.filename)

            document = routing.route(upload.filename, upload.content_type, upload.content)
            job_id = await self._repository.create_job(
                user_id=user.id,
                filename=upload.filename,
                media_type=document.media_type,
                size_bytes=len(upload.content),
            )
            await self._repository.update_job(
                job_id,
                route=document.route.value,
                page_count=document.page_count,
                stage=ParseStage.READING.value,
            )
            await self._repository.audit(
                user_id=user.id, action="resume.upload", outcome="accepted", subject_id=job_id
            )

            yield events.stage(
                ParseStage.READING,
                f"{document.page_count} page(s), {document.route.value} path",
            )
            preprocess_started = perf_counter()
            if document.route.value == "text":
                strategy = "native_text"
            elif document.media_type == "application/pdf":
                strategy = self._settings.resume_scanned_pdf_strategy
            else:
                # Docling is a scanned-PDF option; standalone image uploads
                # continue through the direct-vision branch.
                strategy = "direct_vision"
            if strategy == "docling_text":
                try:
                    converted = await asyncio.to_thread(
                        self._document_text.convert, document
                    )
                except DocumentTextConversionError as exc:
                    logger.warning("Docling preprocessing failed: %s", type(exc).__name__)
                    raise ExtractionFailed(
                        "Docling could not read this resume."
                    ) from exc
                pages = preprocessing.text_artifact(converted)
            else:
                pages = preprocessing.to_pages(document)
            preprocess_seconds = perf_counter() - preprocess_started
            logger.info(
                "Resume preprocessing completed strategy=%s pages=%d "
                "input_units=%d duration_seconds=%.3f",
                strategy,
                len(pages),
                sum(
                    len(page.text or "")
                    if page.text is not None
                    else len(page.image_png or b"")
                    for page in pages
                ),
                preprocess_seconds,
            )

            yield events.stage(ParseStage.EXTRACTING, self._extraction.primary_model)
            merged, report, model_used, fallback_used = await self._run_extraction(
                pages, job_id
            )

            if fallback_used:
                yield events.stage(ParseStage.REFINING, self._extraction.fallback_model)

            yield events.stage(ParseStage.PERSISTING)
            record = await self._persist(
                job_id=job_id,
                user=user,
                document_hash=content_hash(upload.content),
                profile=merged,
                report=report,
                model_used=model_used,
                fallback_used=fallback_used,
            )

            yield events.stage(ParseStage.READY)
            yield events.profile(record)

        except ResumeParsingError as error:
            await self._fail(job_id, user, error)
            yield events.failure(error)
        except Exception:
            logger.exception("Unexpected failure while parsing a resume")
            error = ResumeParsingError()
            await self._fail(job_id, user, error)
            yield events.failure(error)
        finally:
            # Rendered pages and file bytes never outlive the request.
            pages.clear()

    async def _run_extraction(
        self, pages: list[PageArtifact], job_id: UUID
    ) -> tuple[CandidateProfile, ValidationReport, str, bool]:
        """Primary attempt, then a single repair attempt on a different model.

        The two models never run together. Flash is reached only when the
        primary result fails the gate, which keeps the fallback rate — and so
        the cost — bounded by validation rather than by traffic.
        """
        threshold = self._settings.resume_completeness_threshold
        primary = self._extraction.primary_model
        fallback = self._extraction.fallback_model

        first = await self._attempt(pages, primary)
        if first is not None:
            merged, report = first
            if report.is_acceptable(threshold):
                return merged, report, primary, False
            logger.info(
                "Primary output rejected (schema_ok=%s coverage=%.2f); repairing",
                report.schema_ok,
                report.coverage,
            )

        await self._repository.update_job(job_id, stage=ParseStage.REFINING.value)
        second = await self._attempt(pages, fallback)

        if second is None:
            if first is None:
                raise ExtractionFailed()
            # Repair unavailable: keep the primary's partial result rather than
            # discarding a usable profile. MS3 §3.4 — emit partial, never nothing.
            return first[0], first[1], primary, True

        repaired, repaired_report = second
        if first is None or repaired_report.schema_ok:
            return repaired, repaired_report, fallback, True
        return first[0], first[1], primary, True

    async def _attempt(
        self, pages: list[PageArtifact], model: str
    ) -> tuple[CandidateProfile, ValidationReport] | None:
        """One extraction pass, or `None` if the model produced nothing usable."""
        try:
            merged = postprocess.merge(
                await extraction.extract_pages(self._extraction, pages, model=model)
            )
        except ProviderError as exc:
            logger.warning("Extraction produced nothing on %s: %s", model, exc)
            return None
        return merged, validation.validate(merged.model_dump(mode="json"))

    async def _persist(
        self,
        *,
        job_id: UUID,
        user: CurrentUser,
        document_hash: str,
        profile: CandidateProfile,
        report: ValidationReport,
        model_used: str,
        fallback_used: bool,
    ) -> ProfileRecord:
        await self._repository.update_job(
            job_id,
            stage=ParseStage.PERSISTING.value,
            model_used=model_used,
            fallback_used=fallback_used,
            coverage=report.coverage,
        )
        profile_id = await self._repository.save_profile(
            job_id=job_id,
            user_id=user.id,
            profile=profile,
            source_hash=document_hash,
            needs_review=report.needs_review,
            is_valid=report.schema_ok,
        )
        await self._repository.finish_job(job_id, status="succeeded")
        await self._repository.audit(
            user_id=user.id,
            action="resume.parse",
            outcome="succeeded",
            subject_id=profile_id,
            detail=model_used,
        )

        record = await self._repository.get_profile(profile_id, user.id)
        if record is None:  # pragma: no cover - the row was just written
            raise ProfileNotFound()
        return record

    async def _fail(
        self, job_id: UUID | None, user: CurrentUser, error: ResumeParsingError
    ) -> None:
        if job_id is not None:
            await self._repository.finish_job(job_id, status="failed", error_code=error.code)
        await self._repository.audit(
            user_id=user.id,
            action="resume.parse",
            outcome="failed",
            subject_id=job_id,
            detail=error.code,
        )

    # --------------------------------------------------------------- retrieval --

    async def get_profile(self, profile_id: UUID, user: CurrentUser) -> ProfileRecord:
        record = await self._repository.get_profile(profile_id, user.id)
        if record is None:
            raise ProfileNotFound()
        return record

    async def list_profiles(self, user: CurrentUser) -> list[ProfileSummary]:
        return await self._repository.list_profiles(user.id)

    async def delete_profile(self, profile_id: UUID, user: CurrentUser) -> None:
        deleted = await self._repository.delete_profile(profile_id, user.id)
        await self._repository.audit(
            user_id=user.id,
            action="resume.delete",
            outcome="succeeded" if deleted else "not_found",
            subject_id=profile_id,
        )
        if not deleted:
            raise ProfileNotFound()

    async def update_profile(
        self, profile_id: UUID, profile: CandidateProfile, user: CurrentUser
    ) -> ProfileRecord:
        # Same gate the parse pipeline runs through — an edit that clears a
        # flagged field should clear it from needs_review too, and one that
        # (somehow) breaks schema shape should not silently ship. Coverage
        # is computed but unused here: repair-vs-accept is a parse-time
        # decision, there is no "fallback model" to repair a human edit.
        report = validation.validate(profile.model_dump(mode="json"))

        updated = await self._repository.update_profile(
            profile_id,
            user.id,
            profile=profile,
            needs_review=report.needs_review,
            is_valid=report.schema_ok,
        )
        await self._repository.audit(
            user_id=user.id,
            action="resume.edit",
            outcome="succeeded" if updated else "not_found",
            subject_id=profile_id,
        )
        if not updated:
            raise ProfileNotFound()

        record = await self._repository.get_profile(profile_id, user.id)
        if record is None:  # pragma: no cover - just written
            raise ProfileNotFound()
        return record
