from src.career_report.internal.generator import (
    build_skill_unlocks,
    fallback_narrative,
    repeated_gaps,
)


def _job(*gaps: str) -> dict:
    return {
        "job": {"title": "Data Analyst"},
        "judge": {"gaps": list(gaps)},
    }


def test_skill_unlocks_require_repeated_evidence() -> None:
    jobs = [_job("SQL", "Tableau"), _job("SQL"), _job("Python")]
    assert repeated_gaps(jobs) == [("SQL", 2)]
    unlocks = build_skill_unlocks(jobs, ["Data Analyst"])
    assert [item.skill for item in unlocks] == ["SQL"]
    assert unlocks[0].evidence_count == 2


def test_fallback_guidance_uses_supplied_roles_and_gaps() -> None:
    recommendations = [
        {
            "occupation_title": "Data Analyst",
            "confidence": "high",
            "explanation": "Matches analytical evidence.",
            "matched_evidence": ["Python"],
        }
    ]
    narrative = fallback_narrative(
        {"skills": ["Python"], "job_titles": ["Analyst"]},
        recommendations,
        [_job("SQL"), _job("SQL")],
    )
    assert narrative.strongest_direction == "Data Analyst"
    assert narrative.roles[0].skills_to_learn == ["SQL"]
    assert all(action.based_on for action in narrative.actions)
