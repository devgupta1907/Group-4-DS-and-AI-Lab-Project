"""
Career Recommendation — API layer.

Implements the four endpoints listed in the handoff notes:
    POST /career/recommend
    GET  /career/recommendations/{candidate_id}
    POST /career/index/rebuild
    GET  /career/health

UNTESTED: written against the existing service.py / store.py / db
modules but not yet run against a live server — flagging per working
preference. Exercise with, e.g.:
    uv run uvicorn main:app --reload
    curl -X POST localhost:8000/career/recommend -H "Content-Type: application/json" -d '{"skills": ["Python", "SQL"]}'
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from career_recommendation.models import CandidateProfile
from career_recommendation.re_ranker import CareerRecommendationResult
from career_recommendation.service import get_recommendations_for_candidate, recommend_for_profile
from career_recommendation import ingestion
from core.config import GlobalConfig
from db.chroma_manager import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/career", tags=["career-recommendation"])

# Guards against overlapping /career/index/rebuild calls, since
# ingestion.build_vector_store() is a single long-running batch job
# (minutes to well over an hour on the Gemini free tier — see M4
# report section 4.1) rather than something safe to run concurrently
# against the same persisted Chroma directory.
_rebuild_in_progress = {"value": False}


@router.get("/health")
def health():
    """
    Reports whether the ESCO vector index is reachable and populated.
    Does not call any LLM — this is meant to be cheap enough to poll.
    """
    try:
        vectorstore = get_vector_store()
        count = vectorstore._collection.count()
        return {
            "status": "ok" if count > 0 else "empty_index",
            "collection": GlobalConfig.CHROMA_COLLECTION,
            "indexed_occupations": count,
            "embedding_provider": GlobalConfig.EMBEDDING_PROVIDER,
        }
    except Exception as exc:
        logger.exception("Health check failed")
        raise HTTPException(status_code=503, detail=f"Vector store unreachable: {exc}") from exc


@router.post("/recommend", response_model=CareerRecommendationResult)
def recommend(profile: CandidateProfile):
    """
    Runs the full pipeline (retrieve -> re-rank -> explain) for one
    candidate profile. If the profile carries a candidate_id, the run
    is persisted and can later be fetched via GET /recommendations/{id}.
    """
    try:
        return recommend_for_profile(profile)
    except Exception as exc:
        logger.exception("Recommendation pipeline failed for candidate %s", profile.candidate_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/recommendations/{candidate_id}")
def get_recommendations(candidate_id: str):
    """Returns the most recently saved recommendation run for a candidate."""
    run = get_recommendations_for_candidate(candidate_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"No saved recommendations for candidate_id={candidate_id!r}. "
            "Recommendations are only saved when POST /career/recommend is called "
            "with a candidate_id set.",
        )
    return run


@router.post("/index/rebuild")
def rebuild_index(background_tasks: BackgroundTasks):
    """
    Kicks off a full ESCO re-embed in the background and returns
    immediately. ingestion.build_vector_store() already resumes from
    where it left off (skips occupation URIs already in the index), so
    a rebuild after a partial failure is safe to re-run.

    This does NOT block the request for the full duration, since a
    Gemini-backed rebuild can take well over an hour (see M4 report,
    section 4.1, free-tier rate limits). Poll GET /career/health for
    indexed_occupations to see progress.
    """
    if _rebuild_in_progress["value"]:
        raise HTTPException(status_code=409, detail="An index rebuild is already in progress.")

    def _run():
        _rebuild_in_progress["value"] = True
        try:
            ingestion.build_vector_store()
        except Exception:
            logger.exception("Index rebuild failed")
        finally:
            _rebuild_in_progress["value"] = False

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Index rebuild started in the background."}
