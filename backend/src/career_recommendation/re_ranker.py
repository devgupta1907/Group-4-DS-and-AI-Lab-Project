"""
Career Recommendation — Deterministic re-ranking + LLM explanation.

Pipeline:
  1. Weighted ESCO skill-match score (essential match = 1.0, optional match = 0.5)
  2. Blend with the retrieval similarity score
  3. Cut to FINAL_TOP_K (5), send those to the explanation LLM

Reads essential/optional skills from DOCUMENT METADATA (written by
ingestion.py).

Robustness behaviour:
  - No skills listed at all: nothing is excluded on skills; ranking
    falls back to similarity, and the LLM is told to reason from
    role/experience instead and say so.
  - Skills listed but zero overlap with anything retrieved: instead of
    returning nothing, fall back to similarity-only ranking, flag it
    as low-confidence, and tell the user their skill list may be
    incomplete.
  - LLM call fails: fall back to a deterministic-only explanation
    built purely from the re-ranker's own numbers, rather than
    raising. (Retrying against a backup model is a possible future
    improvement, not done here.)
"""

import logging

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from services.llm_client import llm
from career_recommendation.config import CareerRecommendationModuleConfig as Cfg
from career_recommendation.retrieval import retrieve_candidate_occupations

logger = logging.getLogger(__name__)


def _normalize_skill(skill: str) -> str:
    return skill.strip().lower()


def _split_meta_skills(value: str) -> set[str]:
    """Skills are stored in metadata as a '; '-joined string."""
    if not value:
        return set()
    return {_normalize_skill(s) for s in value.split(";") if s.strip()}


def _get_occupation_skills(doc: Document) -> tuple[set[str], set[str]]:
    """
    Returns (essential_skills, optional_skills) for an occupation, read
    directly from metadata written at ingestion time.
    """
    md = doc.metadata or {}
    essential = _split_meta_skills(md.get("essential_skills", ""))
    optional = _split_meta_skills(md.get("optional_skills", ""))
    return essential, optional


def deterministic_rerank(candidate_profile: dict, retrieved: list[tuple[Document, float]]) -> tuple[list[dict], dict]:
    """
    takes the 20 occupations from retrieval and re-scores them using exact skill overlap, blended with the semantic similarity score. Cuts down to FINAL_TOP_K (5)

    Returns (ranked, meta). `meta` records HOW the ranking was produced
    so the LLM prompt and user-facing message can adapt:
        {"had_skills": bool, "used_relaxed_matching": bool}
    """
    candidate_skills = {_normalize_skill(s) for s in candidate_profile.get("skills", [])}
    had_skills = len(candidate_skills) > 0

    scored = []
    for doc, similarity_score in retrieved:
        ess_skills, opt_skills = _get_occupation_skills(doc)

        matched_ess = candidate_skills & ess_skills
        matched_opt = candidate_skills & opt_skills
        # A skill listed as both essential and optional counts once, as
        # essential (the stronger signal).
        matched_opt -= matched_ess

        weighted = (
            len(matched_ess) * Cfg.ESSENTIAL_SKILL_WEIGHT
            + len(matched_opt) * Cfg.OPTIONAL_SKILL_WEIGHT
        )

        scored.append({
            "document": doc,
            "occupation_title": doc.metadata.get("occupation_title"),
            "occupation_uri": doc.metadata.get("occupation_uri"),
            "similarity_score": similarity_score,
            "weighted_skill_score": weighted,
            "matched_skill_count": len(matched_ess) + len(matched_opt),
            "matched_essential": sorted(matched_ess),
            "matched_optional": sorted(matched_opt),
            "matched_skills": sorted(matched_ess | matched_opt),
        })

    # --- Stage 1: hard-requirement exclusion ---
    # Only applies if the candidate actually listed skills.
    # --- Hard exclusion removed after evaluation on real resumes ---
    # Exact skill-string matching does not transfer from ESCO vocabulary
    # to resume vocabulary, so excluding zero-overlap occupations discarded
    # good candidates far more often than it removed bad ones.
    filtered = scored

    # Flag profiles where no skill evidence was found at all, so the LLM
    # prompt and user message can say so honestly.
    used_relaxed_matching = had_skills and not any(
        r["weighted_skill_score"] > 0 for r in scored
    )

    # --- Blended ranking ---
    # Semantic similarity is the primary signal; exact skill overlap is a
    # bounded bonus rather than an override. The previous lexicographic
    # sort let a single spurious skill match outrank the entire embedding
    # signal, which measurably degraded MRR on real resumes.
    max_score = max((r["weighted_skill_score"] for r in filtered), default=0.0)
    for r in filtered:
        norm_skill = (r["weighted_skill_score"] / max_score) if max_score > 0 else 0.0
        r["final_score"] = r["similarity_score"] + Cfg.SKILL_BONUS_WEIGHT * norm_skill

    filtered.sort(key=lambda r: r["final_score"], reverse=True)

    ranked = filtered[:Cfg.FINAL_TOP_K]
    meta = {"had_skills": had_skills, "used_relaxed_matching": used_relaxed_matching}
    return ranked, meta


# ---------------------------------------------------------------------
# LLM explanation step
# ---------------------------------------------------------------------

class OccupationExplanation(BaseModel):
    occupation_title: str = Field(description="Exact occupation title, must match one of the provided candidates.")
    occupation_uri: str = Field(description="Exact ESCO URI, must match one of the provided candidates.")
    confidence: str = Field(description="One of: high, medium, low.")
    explanation: str = Field(description="1-3 sentence recruiter-style explanation of why this occupation fits.")
    matched_evidence: list[str] = Field(description="Specific candidate skills/experience supporting this match.")


class CareerRecommendationResult(BaseModel):
    #   "ok"              -> normal path, LLM call succeeded
    #   "degraded_no_llm" -> LLM failed; deterministic-only explanations
    #   "no_candidates"   -> nothing retrieved at all
    status: str = Field(description="ok | degraded_no_llm | no_candidates")
    message: str = Field(default="", description="Optional user-facing note.")
    recommendations: list[OccupationExplanation]


def _fallback_explanation(r: dict) -> OccupationExplanation:
    """
    Deterministic explanation used when the LLM call fails. Every field
    is derived from the re-ranker's own output, so it cannot hallucinate.
    """
    score = r["weighted_skill_score"]
    confidence = "high" if score >= 3 else "medium" if score >= 1 else "low"

    bits = []
    if r["matched_essential"]:
        bits.append(f"{len(r['matched_essential'])} essential skill(s): {', '.join(r['matched_essential'])}")
    if r["matched_optional"]:
        bits.append(f"{len(r['matched_optional'])} optional skill(s): {', '.join(r['matched_optional'])}")

    if bits:
        explanation = (
            f"Matched on {'; '.join(bits)} (weighted score {score:.1f}). "
            "(Automated fallback — AI-generated explanation unavailable this run.)"
        )
    else:
        explanation = (
            "Matched via semantic similarity to the candidate profile; no exact "
            "skill overlap found. (Automated fallback — AI-generated explanation "
            "unavailable this run.)"
        )

    return OccupationExplanation(
        occupation_title=r["occupation_title"],
        occupation_uri=r["occupation_uri"],
        confidence=confidence,
        explanation=explanation,
        matched_evidence=r["matched_skills"],
    )


def _build_prompt(candidate_profile: dict, ranked: list[dict], meta: dict) -> str:
    allowed_occupations = [
        {
            "occupation_title": r["occupation_title"],
            "occupation_uri": r["occupation_uri"],
            "matched_essential_skills": r["matched_essential"],
            "matched_optional_skills": r["matched_optional"],
        }
        for r in ranked
    ]

    base = (
        "You are a career recommendation assistant. You will be given a candidate's "
        "profile and a fixed, pre-selected list of ESCO occupations. Your only job is "
        "to write a short recruiter-style explanation for EACH occupation in the list, "
        "using ONLY the occupation_title and occupation_uri values exactly as given. "
        "Do NOT invent, add, remove, or reorder occupations. Do NOT invent skills that "
        "are not present in the candidate profile or the matched skill lists. "
        "Treat matched_essential_skills as stronger evidence of fit than "
        "matched_optional_skills. If evidence is weak, set confidence to 'low' rather "
        "than forcing a stronger claim."
    )

    if not meta["had_skills"]:
        mode = (
            "\n\nIMPORTANT: this candidate listed NO skills. Base your assessment on "
            "their job titles, past experience, education and project descriptions "
            "instead. In each explanation, note that the assessment is based on role "
            "and experience rather than listed skills, since none were provided (they "
            "may simply have forgotten to add them)."
        )
    elif meta["used_relaxed_matching"]:
        mode = (
            "\n\nIMPORTANT: none of these occupations had any skill overlap with the "
            "candidate's listed skills — this list was selected by semantic similarity "
            "alone as a fallback. Set confidence to 'low' for all of them and state "
            "explicitly that this is a weaker, similarity-only match."
        )
    else:
        mode = ""

    return (
        base + mode + "\n\n"
        f"Candidate profile:\n{candidate_profile}\n\n"
        f"Pre-selected occupations (already ranked, do not change):\n{allowed_occupations}"
    )


def explain_recommendations(
    candidate_profile: dict,
    ranked: list[dict],
    meta: dict,
) -> CareerRecommendationResult:
    """
    Step 2: explains the occupations that survived deterministic
    re-ranking. Never raises — on LLM failure it returns deterministic
    explanations instead.
    """
    if not ranked:
        return CareerRecommendationResult(
            status="no_candidates",
            message=(
                "No occupations could be matched. This can happen if the ESCO index "
                "is empty, or the candidate profile has no usable signal."
            ),
            recommendations=[],
        )

    message = ""
    if not meta["had_skills"]:
        message = (
            "No skills were listed on this profile — recommendations are based on job "
            "title and experience instead. Adding specific skills will produce more "
            "precise matches."
        )
    elif meta["used_relaxed_matching"]:
        message = (
            "None of the candidate's listed skills matched the top-retrieved "
            "occupations, so these results are based on overall profile similarity "
            "rather than confirmed skill overlap. Consider reviewing whether all "
            "relevant skills were added to the profile."
        )

    prompt = _build_prompt(candidate_profile, ranked, meta)
    allowed_uris = {r["occupation_uri"] for r in ranked}

    try:
        structured_llm = llm.with_structured_output(CareerRecommendationResult)
        result = structured_llm.invoke(prompt)
        # Guardrail: drop any hallucinated or altered ESCO URI.
        validated = [rec for rec in result.recommendations if rec.occupation_uri in allowed_uris]
        return CareerRecommendationResult(status="ok", message=message, recommendations=validated)

    except Exception as exc:
        logger.warning("LLM explanation call failed, using deterministic fallback", exc_info=exc)
        degraded = (message + " " if message else "") + (
            "AI-generated explanations were unavailable this run (LLM call failed); "
            "showing deterministic matches only."
        )
        return CareerRecommendationResult(
            status="degraded_no_llm",
            message=degraded,
            recommendations=[_fallback_explanation(r) for r in ranked],
        )


def recommend_careers(candidate_profile: dict) -> CareerRecommendationResult:
    """
    Full pipeline: retrieval -> deterministic re-rank -> LLM explanation.
    """
    retrieved = retrieve_candidate_occupations(candidate_profile)
    ranked, meta = deterministic_rerank(candidate_profile, retrieved)
    return explain_recommendations(candidate_profile, ranked, meta)


def _demo(label: str, profile: dict) -> None:
    print(f"\n=== {label} ===")
    retrieved = retrieve_candidate_occupations(profile)
    ranked, meta = deterministic_rerank(profile, retrieved)

    print(f"meta: {meta}")
    print("deterministic ranking (before LLM):")
    for r in ranked:
        print(
            f"  score={r['weighted_skill_score']:.1f}  sim={r['similarity_score']:.4f}  "
            f"{r['occupation_title']}"
        )
        print(f"     essential: {r['matched_essential']}  optional: {r['matched_optional']}")

    output = explain_recommendations(profile, ranked, meta)
    print(f"\nstatus: {output.status}")
    if output.message:
        print(f"message: {output.message}")
    for rec in output.recommendations:
        print(f"\n[{rec.confidence}] {rec.occupation_title}")
        print(f"   {rec.explanation}")
        print(f"   matched: {rec.matched_evidence}")


if __name__ == "__main__":
    _demo("Case 1: profile with skills", {
        "job_titles": ["Data Analyst"],
        "skills": ["Python", "SQL", "data visualisation", "statistics", "machine learning"],
        "experience": [{"title": "Junior Data Analyst"}],
        "projects": [],
    })

    _demo("Case 2: profile with NO skills listed", {
        "job_titles": ["Junior Data Analyst"],
        "skills": [],
        "experience": [{"title": "Junior Data Analyst"}],
        "projects": [{"description": "Built dashboards summarising sales data."}],
    })