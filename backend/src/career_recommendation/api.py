"""
Career Recommendation — API layer.

    POST /career/recommend                       run against a stored profile
    GET  /career/recommendations/{profile_id}    read the latest saved run
    POST /career/index/rebuild                   re-embed the ESCO taxonomy
    GET  /career/health                          vector index reachable?

MERGE NOTE
    `POST /career/recommend` now takes a `profile_id` produced by
    Resume Parsing rather than a raw profile body. The profile is read
    back through resume_parsing's public service (which decrypts it),
    never by querying its tables — `.importlinter` forbids reaching into
    `resume_parsing.internal`, and that rule is what keeps the two
    modules independently testable.

    A raw profile can still be posted for testing by sending `profile`
    instead of `profile_id`; that path does not persist, because there
    is no profile row to attach the run to.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, model_validator

from src.career_recommendation import ingestion, store
from src.career_recommendation.models import CandidateProfile
from src.career_recommendation.re_ranker import CareerRecommendationResult
from src.career_recommendation.service import recommend_and_persist, recommend_for_profile
from src.core.config import GlobalConfig
from src.core.security import CurrentUser, get_current_user
from src.db.supabase_manager import get_vector_store
from src.resume_parsing.dependencies import get_resume_parsing_service
from src.resume_parsing.errors import ProfileNotFound
from src.resume_parsing.service import ResumeParsingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/career", tags=["career-recommendation"])

# Guards against overlapping rebuilds: build_vector_store() truncates the
# documents table before rewriting it, so two concurrent runs would leave
# the index partially populated.
_rebuild_in_progress = {"value": False}


class RecommendRequest(BaseModel):
    """Either a stored profile_id (normal path) or an inline profile (testing)."""

    profile_id: UUID | None = None
    profile: CandidateProfile | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> RecommendRequest:
        if (self.profile_id is None) == (self.profile is None):
            raise ValueError("Provide exactly one of profile_id or profile.")
        return self


@router.get("/health")
def health() -> dict:
    """Reports whether the ESCO vector index is reachable and populated."""
    try:
        vectorstore = get_vector_store()
        response = (
            vectorstore._client.table(GlobalConfig.SUPABASE_TABLE)
            .select("*", count="exact", head=True)
            .execute()
        )
        count = response.count
        return {
            "status": "ok" if count else "empty_index",
            "vector_store": f"supabase:{GlobalConfig.SUPABASE_TABLE}",
            "indexed_occupations": count,
            "embedding_provider": GlobalConfig.EMBEDDING_PROVIDER,
        }
    except Exception as exc:
        logger.exception("Health check failed")
        raise HTTPException(status_code=503, detail=f"Vector store unreachable: {exc}") from exc


@router.post("/recommend", response_model=CareerRecommendationResult)
async def recommend(
    request: RecommendRequest,
    user: CurrentUser = Depends(get_current_user),
    resume_service: ResumeParsingService = Depends(get_resume_parsing_service),
) -> CareerRecommendationResult:
    """
    Runs retrieve -> re-rank -> explain for one candidate.

    With `profile_id`, the run is persisted against that profile and can
    be read back by this module or any other. With an inline `profile`,
    it is computed and returned without being stored.
    """
    if request.profile is not None:
        return _run(request.profile)

    try:
        record = await resume_service.get_profile(request.profile_id, user)
    except ProfileNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=f"No profile {request.profile_id} for this user.",
        ) from exc

    try:
        return recommend_and_persist(
            record.profile,
            profile_id=request.profile_id,
            user_id=user.id,
        )
    except Exception as exc:
        logger.exception("Recommendation pipeline failed")
        raise HTTPException(status_code=500, detail="Career recommendation failed.") from exc


def _run(profile: CandidateProfile) -> CareerRecommendationResult:
    try:
        return recommend_for_profile(profile, persist=False)
    except Exception as exc:
        logger.exception("Recommendation pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/recommendations/{profile_id}")
def get_recommendations(
    profile_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Returns the most recently saved run for a profile."""
    run = store.get_latest_run(profile_id, user_id=user.id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"No saved recommendations for profile {profile_id}. "
            "Runs are only saved when POST /career/recommend is called with a profile_id.",
        )
    return run


@router.post("/index/rebuild")
def rebuild_index(background_tasks: BackgroundTasks) -> dict:
    """
    Kicks off a full ESCO re-embed in the background and returns at once.

    This truncates and rewrites the whole index (a few minutes on CPU),
    so /career/health will report a falling then rising occupation count
    while it runs. Poll it for progress.
    """
    if _rebuild_in_progress["value"]:
        raise HTTPException(status_code=409, detail="An index rebuild is already in progress.")

    def _rebuild() -> None:
        _rebuild_in_progress["value"] = True
        try:
            ingestion.build_vector_store()
        except Exception:
            logger.exception("Index rebuild failed")
        finally:
            _rebuild_in_progress["value"] = False

    background_tasks.add_task(_rebuild)
    return {"status": "started", "message": "Index rebuild started in the background."}
