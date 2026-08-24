from src.cv_review.schemas import CvFinding, CvReview
from src.cv_review.service import _compute_ats_score
from src.resume_parsing.schemas import CandidateProfile, Experience


def _profile(**overrides) -> CandidateProfile:
    defaults = {
        "skills": ["Python", "SQL", "dbt"],
        "job_titles": ["Data Analyst"],
        "experience": [
            Experience(
                job_title="Data Analyst",
                company="Acme",
                description="Cut reporting time by 40% across 12 dashboards.",
            )
        ],
    }
    defaults.update(overrides)
    return CandidateProfile(**defaults)


def test_a_complete_profile_with_no_findings_scores_highest() -> None:
    score, reason = _compute_ats_score(_profile(), CvReview())
    assert score == 100
    assert "no ats risk" in reason.lower()


def test_empty_skills_is_the_single_largest_deduction() -> None:
    score, reason = _compute_ats_score(_profile(skills=[]), CvReview())
    assert score == 80
    assert "skills section is empty" in reason.lower()


def test_missing_quantification_is_detected_from_experience_descriptions() -> None:
    unquantified = _profile(
        experience=[
            Experience(job_title="Data Analyst", company="Acme", description="Built dashboards.")
        ]
    )
    score, reason = _compute_ats_score(unquantified, CvReview())
    assert score == 90
    assert "quantified" in reason.lower()


def test_missing_sections_and_relevant_findings_both_deduct() -> None:
    review = CvReview(
        missing_sections=["certifications"],
        findings=[
            CvFinding(
                area="contact",
                severity="critical",
                issue="No location given.",
                fix="Add a city and country.",
            ),
            # A skills-area finding does not count toward the ATS deduction —
            # only the structural/contact areas do, so this should be ignored.
            CvFinding(
                area="skills",
                severity="critical",
                issue="Skills list is generic.",
                fix="Name specific tools.",
            ),
        ],
    )
    score, reason = _compute_ats_score(_profile(), review)
    # -10 (one missing section) and -8 (one relevant critical finding) = -18
    assert score == 82
    assert "missing sections: certifications" in reason.lower()
    assert "structural or contact" in reason.lower()


def test_score_never_drops_below_zero() -> None:
    empty_profile = CandidateProfile()
    review = CvReview(
        missing_sections=["skills", "experience", "education", "certifications", "projects"],
        findings=[
            CvFinding(area="ats", severity="critical", issue="x", fix="y")
            for _ in range(10)
        ],
    )
    score, _ = _compute_ats_score(empty_profile, review)
    assert score == 0


def test_reason_reports_at_most_the_three_biggest_deductions() -> None:
    review = CvReview(
        missing_sections=["a", "b", "c"],
        findings=[
            CvFinding(area="structure", severity="critical", issue="x", fix="y"),
        ],
    )
    _, reason = _compute_ats_score(CandidateProfile(), review)
    # Skills empty (20) + job_titles empty (10) + experience empty (20) +
    # missing sections (30) + finding (8) = 5 possible deductions, only the
    # top 3 by size should surface in the reason.
    assert reason.count(".") <= 3 or len(reason.split(". ")) <= 3
