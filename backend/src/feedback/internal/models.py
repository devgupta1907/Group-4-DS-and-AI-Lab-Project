"""ORM table owned by the feedback module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base


class Feedback(Base):
    """One feedback submission."""

    __tablename__ = "feedback"

    # The check constraint duplicates the Pydantic bound on purpose: the schema
    # protects the API, this protects the table from anything that writes to it
    # directly, including a future migration or an admin fix.
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 10", name="ck_feedback_rating_range"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    # Nullable, and SET NULL rather than CASCADE: feedback is evidence about the
    # system, so deleting a candidate profile must not erase what that person
    # said about it. The link is dropped, the response survives.
    profile_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("resume_candidate_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    rating: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    comment: Mapped[str] = mapped_column(String(2000), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
