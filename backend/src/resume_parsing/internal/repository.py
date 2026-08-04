"""★ The only place in this module that executes SQL. ★

Every ownership check lives here too: a query that can return another user's row
is a bug in this file, not somewhere else. Callers pass a `user_id` and get back
plain values — no ORM object ever leaves this module boundary.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.resume_parsing.internal.crypto import ProfileCipher
from src.resume_parsing.internal.models import (
    CandidateProfileRecord,
    ResumeAuditLog,
    ResumeParseJob,
)
from src.resume_parsing.schemas import (
    CandidateProfile,
    ParseRoute,
    ProfileRecord,
    ProfileSummary,
)


def content_hash(payload: bytes) -> str:
    """Stable id for a file, so downstream embedding work can be cached."""
    return hashlib.sha256(payload).hexdigest()


class ResumeParsingRepository:
    """Persistence for parse jobs, profiles and the audit trail."""

    def __init__(self, session: AsyncSession, cipher: ProfileCipher) -> None:
        self._session = session
        self._cipher = cipher

    # ----------------------------------------------------------------- jobs --

    async def create_job(
        self,
        *,
        user_id: str,
        filename: str,
        media_type: str,
        size_bytes: int,
    ) -> UUID:
        job = ResumeParseJob(
            id=uuid4(),
            user_id=user_id,
            filename=filename,
            media_type=media_type,
            size_bytes=size_bytes,
            route=ParseRoute.VISION.value,
        )
        self._session.add(job)
        await self._session.commit()
        return job.id

    async def update_job(self, job_id: UUID, **fields: object) -> None:
        job = await self._session.get(ResumeParseJob, job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        await self._session.commit()

    async def finish_job(
        self,
        job_id: UUID,
        *,
        status: str,
        error_code: str | None = None,
    ) -> None:
        await self.update_job(
            job_id,
            status=status,
            error_code=error_code,
            completed_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------- profiles --

    async def save_profile(
        self,
        *,
        job_id: UUID,
        user_id: str,
        profile: CandidateProfile,
        source_hash: str,
        needs_review: list[str],
        is_valid: bool,
    ) -> UUID:
        record = CandidateProfileRecord(
            id=uuid4(),
            job_id=job_id,
            user_id=user_id,
            content_hash=source_hash,
            profile_encrypted=self._cipher.seal(profile.model_dump(mode="json")),
            needs_review=needs_review,
            is_valid=is_valid,
        )
        self._session.add(record)
        await self._session.commit()
        return record.id

    async def get_profile(self, profile_id: UUID, user_id: str) -> ProfileRecord | None:
        stmt = (
            select(CandidateProfileRecord, ResumeParseJob)
            .join(ResumeParseJob, CandidateProfileRecord.job_id == ResumeParseJob.id)
            .where(
                CandidateProfileRecord.id == profile_id,
                CandidateProfileRecord.user_id == user_id,
            )
        )
        row = (await self._session.execute(stmt)).first()
        return None if row is None else self._to_record(row[0], row[1])

    async def list_profiles(self, user_id: str) -> list[ProfileSummary]:
        stmt = (
            select(CandidateProfileRecord, ResumeParseJob)
            .join(ResumeParseJob, CandidateProfileRecord.job_id == ResumeParseJob.id)
            .where(CandidateProfileRecord.user_id == user_id)
            .order_by(CandidateProfileRecord.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            ProfileSummary(
                id=record.id,
                filename=job.filename,
                route=ParseRoute(job.route),
                page_count=job.page_count,
                is_valid=record.is_valid,
                needs_review=list(record.needs_review or []),
                created_at=record.created_at,
            )
            for record, job in rows
        ]

    async def delete_profile(self, profile_id: UUID, user_id: str) -> bool:
        """Deleting the job cascades to the profile — DPDP erasure."""
        stmt = select(CandidateProfileRecord).where(
            CandidateProfileRecord.id == profile_id,
            CandidateProfileRecord.user_id == user_id,
        )
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        if record is None:
            return False
        await self._session.execute(
            delete(ResumeParseJob).where(ResumeParseJob.id == record.job_id)
        )
        await self._session.commit()
        return True

    # ---------------------------------------------------------------- audit --

    async def audit(
        self,
        *,
        user_id: str,
        action: str,
        outcome: str,
        subject_id: UUID | None = None,
        detail: str | None = None,
    ) -> None:
        self._session.add(
            ResumeAuditLog(
                id=uuid4(),
                user_id=user_id,
                action=action,
                outcome=outcome,
                subject_id=subject_id,
                detail=detail,
            )
        )
        await self._session.commit()

    # --------------------------------------------------------------- mapping --

    def _to_record(
        self, record: CandidateProfileRecord, job: ResumeParseJob
    ) -> ProfileRecord:
        return ProfileRecord(
            id=record.id,
            filename=job.filename,
            route=ParseRoute(job.route),
            page_count=job.page_count,
            is_valid=record.is_valid,
            needs_review=list(record.needs_review or []),
            model_used=job.model_used,
            fallback_used=job.fallback_used,
            created_at=record.created_at,
            profile=CandidateProfile.model_validate(
                self._cipher.open(record.profile_encrypted)
            ),
        )
