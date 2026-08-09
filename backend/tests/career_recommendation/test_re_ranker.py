"""
Unit tests for career_recommendation.re_ranker.deterministic_rerank.

These cover only the pure scoring/ranking logic — no LLM call, no
vector store, no network. Run with:

    uv run pytest tests/career_recommendation/test_re_ranker.py -v
"""

from langchain_core.documents import Document

from src.career_recommendation.config import CareerRecommendationModuleConfig as Cfg
from src.career_recommendation.re_ranker import deterministic_rerank


def _doc(title, uri, essential="", optional=""):
    return Document(
        page_content="",
        metadata={
            "occupation_title": title,
            "occupation_uri": uri,
            "essential_skills": essential,
            "optional_skills": optional,
        },
    )


def test_pass_through_at_zero_weight_preserves_similarity_order(monkeypatch):
    """
    At SKILL_BONUS_WEIGHT = 0.0 the re-ranker must reproduce the
    retrieval (similarity) ordering exactly. This is the same
    reference check the M4 report's weight sweep uses to confirm the
    implementation is correct.
    """
    monkeypatch.setattr(Cfg, "SKILL_BONUS_WEIGHT", 0.0)

    retrieved = [
        (_doc("occupation A", "urn:a", essential="python"), 0.90),
        (_doc("occupation B", "urn:b", essential="python; sql"), 0.80),
        (_doc("occupation C", "urn:c"), 0.70),
    ]
    profile = {"skills": ["python", "sql"]}

    ranked, _ = deterministic_rerank(profile, retrieved)

    assert [r["occupation_uri"] for r in ranked] == ["urn:a", "urn:b", "urn:c"]


def test_essential_skill_weighted_above_optional():
    """
    An essential-skill match must contribute more to weighted_skill_score
    than an optional-skill match, per ESSENTIAL_SKILL_WEIGHT (1.0) vs
    OPTIONAL_SKILL_WEIGHT (0.5).
    """
    retrieved = [
        (_doc("essential match", "urn:ess", essential="python"), 0.5),
        (_doc("optional match", "urn:opt", optional="python"), 0.5),
    ]
    profile = {"skills": ["python"]}

    ranked, _ = deterministic_rerank(profile, retrieved)
    by_uri = {r["occupation_uri"]: r for r in ranked}

    assert by_uri["urn:ess"]["weighted_skill_score"] > by_uri["urn:opt"]["weighted_skill_score"]
    assert by_uri["urn:ess"]["weighted_skill_score"] == Cfg.ESSENTIAL_SKILL_WEIGHT
    assert by_uri["urn:opt"]["weighted_skill_score"] == Cfg.OPTIONAL_SKILL_WEIGHT


def test_skill_in_both_essential_and_optional_counts_once_as_essential():
    """A candidate skill matching both lists must not be double counted."""
    retrieved = [(_doc("occ", "urn:x", essential="python", optional="python"), 0.5)]
    profile = {"skills": ["python"]}

    ranked, _ = deterministic_rerank(profile, retrieved)

    assert ranked[0]["matched_essential"] == ["python"]
    assert ranked[0]["matched_optional"] == []
    assert ranked[0]["weighted_skill_score"] == Cfg.ESSENTIAL_SKILL_WEIGHT


def test_skill_matching_is_case_and_whitespace_insensitive():
    retrieved = [(_doc("occ", "urn:x", essential=" Python ; SQL "), 0.5)]
    profile = {"skills": ["python", "sql"]}

    ranked, _ = deterministic_rerank(profile, retrieved)

    assert set(ranked[0]["matched_essential"]) == {"python", "sql"}


def test_no_skills_listed_is_not_relaxed_matching():
    """
    had_skills=False (candidate listed nothing) is a distinct case from
    used_relaxed_matching=True (candidate listed skills, none matched).
    The prompt/message logic in re_ranker.py branches on this, so the
    two must not be conflated.
    """
    retrieved = [(_doc("occ", "urn:x"), 0.9)]
    profile = {"skills": []}

    ranked, meta = deterministic_rerank(profile, retrieved)

    assert meta["had_skills"] is False
    assert meta["used_relaxed_matching"] is False
    assert len(ranked) == 1


def test_zero_overlap_with_listed_skills_triggers_relaxed_matching():
    retrieved = [(_doc("occ", "urn:x", essential="excel"), 0.9)]
    profile = {"skills": ["python", "sql"]}

    ranked, meta = deterministic_rerank(profile, retrieved)

    assert meta["had_skills"] is True
    assert meta["used_relaxed_matching"] is True
    # Nothing is hard-excluded even with zero overlap (see M4 report,
    # "hard exclusion removed after evaluation on real resumes").
    assert len(ranked) == 1


def test_final_top_k_truncation(monkeypatch):
    monkeypatch.setattr(Cfg, "FINAL_TOP_K", 2)

    retrieved = [
        (_doc(f"occ {i}", f"urn:{i}"), 1.0 - i * 0.1)
        for i in range(5)
    ]
    profile = {"skills": []}

    ranked, _ = deterministic_rerank(profile, retrieved)

    assert len(ranked) == 2
    assert [r["occupation_uri"] for r in ranked] == ["urn:0", "urn:1"]


def test_higher_similarity_beats_lower_skill_bonus_within_bounded_weight():
    """
    Regression guard for the failure mode the M4 report documents: a
    skill-dominant setting lets one incidental match outrank strong
    semantic similarity. At the selected small weight (0.02), a large
    similarity gap must still win over a skill-only edge.
    """
    retrieved = [
        (_doc("strong semantic match", "urn:sim", essential=""), 0.95),
        (_doc("weak semantic, one skill match", "urn:skill", essential="python"), 0.50),
    ]
    profile = {"skills": ["python"]}

    ranked, _ = deterministic_rerank(profile, retrieved)

    assert ranked[0]["occupation_uri"] == "urn:sim"


def test_empty_retrieved_list_returns_empty_ranking():
    """
    With nothing retrieved, `used_relaxed_matching` ends up True by
    vacuous truth (`not any([])`). That's harmless in practice: this
    edge case is caught upstream by `explain_recommendations`, which
    returns status="no_candidates" whenever `ranked` is empty and never
    inspects `meta` in that branch — but it's worth knowing this flag
    isn't a reliable "some skill-matching happened" signal on its own
    when the candidate list is empty.
    """
    ranked, meta = deterministic_rerank({"skills": ["python"]}, [])

    assert ranked == []
    assert meta["had_skills"] is True
