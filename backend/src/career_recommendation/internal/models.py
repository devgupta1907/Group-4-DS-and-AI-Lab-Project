"""ORM tables owned by the Career Recommendation module.

One table, prefixed `career_`. Declared against the SAME shared Base as
resume_parsing so Alembic sees a single metadata and both modules live in
one database.

The recommendation result is stored as JSONB rather than normalised into
columns: it is a read-mostly document consumed whole by downstream
modules (Job Discovery reads the top occupation), and its shape is owned
by `re_ranker.CareerRecommendationResult`, which should be free to evolve
without a migration.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base


class CareerRecommendationRun(Base):
    """One recommendation run against one parsed profile."""

    __tablename__ = "career_recommendation_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # The profile this was computed from. FK to resume_parsing's table:
    # deleting a profile (DPDP erasure) removes its recommendations too.
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("resume_candidate_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    # ok | degraded_no_llm | no_candidates
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(1024), default="")

    # Full CareerRecommendationResult, exactly as returned by the service.
    result: Mapped[dict] = mapped_column(JSONB)

    # Provenance, so a run can be reproduced or invalidated when config changes.
    embedding_provider: Mapped[str] = mapped_column(String(32), default="")
    llm_model: Mapped[str] = mapped_column(String(128), default="")
    skill_bonus_weight: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
