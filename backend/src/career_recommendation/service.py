"""
Career Recommendation — service entry point.

This is the ONE function other modules (and the API layer) should
call. It's the merge surface referenced in the handoff notes: Resume
Parsing produces a profile, this function turns it into ranked,
explained career recommendations, and nothing outside this module
should need to import retrieval.py / re_ranker.py internals directly.

    from career_recommendation.service import recommend_for_profile
    result = recommend_for_profile(profile_dict_or_model)

Persistence is opt-in: if the profile carries a candidate_id, the run
is saved via store.py and can be re-fetched later; if not, this is a
pure request/response call with no side effects.
"""

from __future__ import annotations
import logging
from career_recommendation.models import CandidateProfile
from career_recommendation.re_ranker import CareerRecommendationResult, deterministic_rerank, explain_recommendations
from career_recommendation.retrieval import retrieve_candidate_occupations
from career_recommendation import store

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
        logger.exception("Failed to persist recommendation run for candidate %s", profile.candidate_id)


def get_recommendations_for_candidate(candidate_id: str) -> dict | None:
    """Returns the most recent saved recommendation run for a candidate, or None."""
    return store.get_latest_run(candidate_id)
