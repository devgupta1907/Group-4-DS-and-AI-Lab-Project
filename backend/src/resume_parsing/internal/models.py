"""ORM tables owned by the Resume Parsing module.

Three tables, all prefixed `resume_`. No other module declares tables here and
this module declares none elsewhere.

What is deliberately *not* stored: the uploaded file, the rendered page images,
the raw model response, and any resume text. The profile itself is stored only
as ciphertext.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base


class ResumeParseJob(Base):
    """One upload attempt and how it went. Provenance only — never content."""

    __tablename__ = "resume_parse_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    filename: Mapped[str] = mapped_column(String(512))
    media_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    route: Mapped[str] = mapped_column(String(16))

    status: Mapped[str] = mapped_column(String(32), default="running")
    stage: Mapped[str] = mapped_column(String(32), default="received")
    model_used: Mapped[str] = mapped_column(String(128), default="")
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    coverage: Mapped[float] = mapped_column(Float, default=0.0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[CandidateProfileRecord | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )


class CandidateProfileRecord(Base):
    """The validated profile, sealed. `profile_encrypted` is the whole payload."""

    __tablename__ = "resume_candidate_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("resume_parse_jobs.id", ondelete="CASCADE"), unique=True, index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    profile_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    needs_review: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[ResumeParseJob] = relationship(back_populates="profile")


class ResumeAuditLog(Base):
    """Append-only. Records that something happened, never what was in it."""

    __tablename__ = "resume_audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[UUID | None] = mapped_column(nullable=True)
    detail: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
