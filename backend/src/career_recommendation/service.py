"""
Career Recommendation — service entry point.

This is the ONE function other modules (and the API layer) should
call. It's the merge surface referenced in the handoff notes: Resume
Parsing produces a profile, this function turns it into ranked,
explained career recommendations, and nothing outside this module
should need to import retrieval.py / re_ranker.py internals directly.

    from career_recommendation.service import recommend_for_profile
    result = recommend_for_profile(profile_dict_or_model)
"""

from __future__ import annotations
import logging
from uuid import UUID

from src.career_recommendation import store
from src.career_recommendation.config import CareerRecommendationModuleConfig as Cfg
from src.career_recommendation.models import CandidateProfile
from src.career_recommendation.re_ranker import (
    CareerRecommendationResult,
    deterministic_rerank,
    explain_recommendations,
)
from src.career_recommendation.retrieval import retrieve_candidate_occupations
from src.career_recommendation.profile_mapper import from_parsed_resume
from src.core.config import GlobalConfig
from src.resume_parsing.schemas import CandidateProfile as ParsedProfile

logger = logging.getLogger(__name__)


def recommend_for_profile(
    profile: CandidateProfile | dict,
    persist: bool = True,
) -> CareerRecommendationResult:
    """
    Full Career Recommendation pipeline: validate -> retrieve ->
    deterministic re-rank -> LLM explanation -> (optionally) persist.

    Args:
        profile: a CandidateProfile, or a plain dict with the same
            shape (job_titles, skills, experience, education, projects,
            optionally candidate_id). Dicts are validated on the way in.
        persist: if True (default) and the profile has a candidate_id,
            the run is saved via store.save_run() so it can later be
            fetched with get_recommendations_for_candidate().

    Returns:
        CareerRecommendationResult with status one of:
            ok               - normal path, LLM explanation succeeded
            degraded_no_llm  - LLM call failed, deterministic-only explanations
            no_candidates    - nothing retrieved, or profile had no usable signal
    """
    if isinstance(profile, dict):
        profile = CandidateProfile.model_validate(profile)

    if not profile.has_usable_signal():
        logger.info("Profile %s has no usable signal; skipping retrieval.", profile.candidate_id)
        result = CareerRecommendationResult(
            status="no_candidates",
            message=(
                "This profile has no job titles, skills, experience, education, or "
                "project descriptions to match against — nothing to recommend from."
            ),
            recommendations=[],
        )
        if persist and profile.candidate_id:
            _save(profile, result)
        return result

    profile_dict = profile.model_dump(exclude_none=False)

    retrieved = retrieve_candidate_occupations(profile_dict)
    ranked, meta = deterministic_rerank(profile_dict, retrieved)
    result = explain_recommendations(profile_dict, ranked, meta)

    if persist and profile.candidate_id:
        _save(profile, result)

    return result


def recommend_and_persist(
    profile: ParsedProfile,
    *,
    profile_id: UUID,
    user_id: str,
) -> CareerRecommendationResult:
    """Run against the canonical parsed profile and return its exact saved run."""
    result = recommend_for_profile(from_parsed_resume(profile), persist=False)
    run_id = store.save_run(
        profile_id=profile_id,
        user_id=user_id,
        result=result.model_dump(mode="json"),
        status=result.status,
        message=result.message,
        embedding_provider=GlobalConfig.EMBEDDING_PROVIDER,
        llm_model=GlobalConfig.LLM_MODEL,
        skill_bonus_weight=Cfg.SKILL_BONUS_WEIGHT,
    )
    result.run_id = run_id
    return result


def _save(profile: CandidateProfile, result: CareerRecommendationResult) -> None:
    try:
        store.save_run(
            candidate_id=profile.candidate_id,
            profile=profile.model_dump(),
            result=result.model_dump(),
            status=result.status,
        )
    except Exception:
        # Persistence is a convenience, not core to producing a
        # recommendation — a save failure should never take down a
        # response that was already computed successfully.
        logger.exception(
            "Failed to persist recommendation run for candidate %s",
            profile.candidate_id,
        )


def get_recommendations_for_candidate(candidate_id: str) -> dict | None:
    """Returns the most recent saved recommendation run for a candidate, or None."""
    return store.get_latest_run(candidate_id)
