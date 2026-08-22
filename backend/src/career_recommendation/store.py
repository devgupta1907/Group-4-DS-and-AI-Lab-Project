"""
Career Recommendation — recommendation persistence.

Replaces the earlier SQLite stand-in. Runs are now written to the same
Postgres database resume_parsing uses, keyed by `profile_id`, so any
other module can read a candidate's recommendations without calling this
module's API.

SYNC ON PURPOSE
    The recommendation pipeline (BGE embedding, Supabase retrieval,
    Gemini explanation) is synchronous and blocking. FastAPI runs plain
    `def` endpoints in a threadpool, so a sync session here is correct
    and avoids sprinkling `await` through a pipeline that has no async
    work to do. resume_parsing keeps its own async engine; both point at
    the same database, which is fine — SQLAlchemy models are engine
    agnostic.

READING FROM OTHER MODULES
    Job Discovery should call `get_latest_run(profile_id)` rather than
    querying `career_recommendation_runs` directly, so the table shape
    stays private to this module.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.career_recommendation.internal.models import CareerRecommendationRun
from src.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _get_session_factory() -> sessionmaker[Session]:
    """
    Sync engine over the same database as resume_parsing.

    `database_url` is stored in async form (postgresql+asyncpg://) for
    resume_parsing, so the driver prefix is swapped here rather than
    keeping two URLs in .env that could drift apart.
    """
    settings = get_settings()
    url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=300,
    )
    return sessionmaker(engine, expire_on_commit=False)


def save_run(
    *,
    profile_id: UUID,
    user_id: str,
    result: dict,
    status: str,
    message: str = "",
    embedding_provider: str = "",
    llm_model: str = "",
    skill_bonus_weight: float = 0.0,
) -> UUID:
    """
    Persists one recommendation run. Returns its row id.

    A write failure is logged and re-raised: unlike the resume pipeline,
    there is no partial-result path here worth preserving — if the run
    cannot be stored, downstream modules would silently read stale data.
    """
    with _get_session_factory()() as session:
        run = CareerRecommendationRun(
            profile_id=profile_id,
            user_id=user_id,
            status=status,
            message=message[:1024],
            result=result,
            embedding_provider=embedding_provider,
            llm_model=llm_model,
            skill_bonus_weight=skill_bonus_weight,
        )
        session.add(run)
        session.commit()
        logger.info("Saved recommendation run %s for profile %s", run.id, profile_id)
        return run.id


def get_latest_run(profile_id: UUID, user_id: str | None = None) -> dict | None:
    """
    Most recent run for a profile, or None.

    `user_id` is optional so internal module-to-module calls can read
    without an authenticated user, but any request originating from a
    user MUST pass it — omitting it returns another user's data.
    """
    stmt = (
        select(CareerRecommendationRun)
        .where(CareerRecommendationRun.profile_id == profile_id)
        .order_by(CareerRecommendationRun.created_at.desc())
        .limit(1)
    )
    if user_id is not None:
        stmt = stmt.where(CareerRecommendationRun.user_id == user_id)

    with _get_session_factory()() as session:
        run = session.execute(stmt).scalar_one_or_none()

    return None if run is None else _to_dict(run)


def get_run(run_id: UUID, user_id: str | None = None) -> dict | None:
    """One exact recommendation run, optionally constrained to its owner."""
    stmt = select(CareerRecommendationRun).where(CareerRecommendationRun.id == run_id)
    if user_id is not None:
        stmt = stmt.where(CareerRecommendationRun.user_id == user_id)
    with _get_session_factory()() as session:
        run = session.execute(stmt).scalar_one_or_none()
    return None if run is None else _to_dict(run)


def get_runs(profile_id: UUID, user_id: str | None = None, limit: int = 10) -> list[dict]:
    """Up to `limit` past runs for a profile, most recent first."""
    stmt = (
        select(CareerRecommendationRun)
        .where(CareerRecommendationRun.profile_id == profile_id)
        .order_by(CareerRecommendationRun.created_at.desc())
        .limit(limit)
    )
    if user_id is not None:
        stmt = stmt.where(CareerRecommendationRun.user_id == user_id)

    with _get_session_factory()() as session:
        runs = session.execute(stmt).scalars().all()

    return [_to_dict(r) for r in runs]


class RunNotFound(Exception):
    """No recommendation run exists for the given id (and owner, if checked)."""


class OccupationNotFound(Exception):
    """The occupation_uri does not appear among this run's recommendations."""


def select_occupation(run_id: UUID, *, user_id: str, occupation_uris: list[str]) -> dict:
    """
    Records which recommended occupation(s) the user picked to carry into
    the next steps (Job Discovery / Career Report). Accepts zero or more:
    a candidate open to several directions can carry all of them into the
    job search rather than being forced to whittle down to one, and an
    empty list clears the pick entirely (falls back to the top 2
    recommendations, same as never having selected anything).

    Stored inside the run's own `result` JSONB blob as
    `selected_occupation_uris` / `selected_occupation_titles` (both lists,
    order preserved from what was picked) rather than as new columns —
    same reasoning as the rest of this table: the result shape should be
    free to evolve without a migration.

    Raises:
        RunNotFound: no run with this id owned by this user.
        OccupationNotFound: one of `occupation_uris` isn't among this
            run's recommendations — selecting something that was never
            offered would silently corrupt downstream modules that trust it.
    """
    with _get_session_factory()() as session:
        stmt = select(CareerRecommendationRun).where(
            CareerRecommendationRun.id == run_id,
            CareerRecommendationRun.user_id == user_id,
        )
        run = session.execute(stmt).scalar_one_or_none()
        if run is None:
            raise RunNotFound(f"No recommendation run {run_id} for this user.")

        recommendations = (run.result or {}).get("recommendations", [])
        by_uri = {r.get("occupation_uri"): r for r in recommendations}

        missing = [uri for uri in occupation_uris if uri not in by_uri]
        if missing:
            raise OccupationNotFound(
                f"{missing!r} are not among the occupations recommended in run {run_id}."
            )

        # Reassign the whole dict (rather than mutating run.result in
        # place) so SQLAlchemy's change tracking picks it up regardless of
        # whether the JSONB column is wrapped in MutableDict.
        updated_result = dict(run.result)
        updated_result["selected_occupation_uris"] = list(occupation_uris)
        updated_result["selected_occupation_titles"] = [
            by_uri[uri].get("occupation_title") for uri in occupation_uris
        ]
        # Drop the old singular keys so nothing downstream reads a stale
        # pre-multi-select value alongside the new lists.
        updated_result.pop("selected_occupation_uri", None)
        updated_result.pop("selected_occupation_title", None)
        run.result = updated_result

        session.add(run)
        session.commit()
        session.refresh(run)
        logger.info(
            "Recorded occupation selection %r for run %s", occupation_uris, run_id
        )
        return _to_dict(run)


def _to_dict(run: CareerRecommendationRun) -> dict:
    return {
        "id": str(run.id),
        "profile_id": str(run.profile_id),
        "status": run.status,
        "message": run.message,
        "result": run.result,
        "embedding_provider": run.embedding_provider,
        "llm_model": run.llm_model,
        "skill_bonus_weight": run.skill_bonus_weight,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
