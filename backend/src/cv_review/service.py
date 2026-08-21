"""
CV review — tells the candidate what is wrong with their resume.

An add-on rather than a pipeline stage: it reads the already-parsed profile
and returns criticism. It writes nothing, so there is no table and no
migration, and a failure here cannot affect the recommendation or report
paths.

The critique runs against the PARSED PROFILE, not the original file. That is
a deliberate limit and is stated to the user: anything the parser dropped is
invisible here, and formatting problems in the source document cannot be seen
at all. What it does see well is the substance — missing quantification, weak
verbs, absent sections, vague skill lists — which is where most resume
weakness actually lives.
"""

from __future__ import annotations

import logging
from uuid import UUID

from src.core.config import GlobalConfig
from src.cv_review.schemas import CvReview
from src.resume_parsing.schemas import CandidateProfile
from src.services.llm_client import llm

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a blunt, experienced technical recruiter reviewing a resume. You "
    "are speaking DIRECTLY TO THE CANDIDATE, who is reading this. Address them "
    "as 'you' and 'your resume' throughout — never by name, never in the third "
    "person. Write 'Your experience section lists duties, not results', not "
    "'The candidate lists duties'. They asked what is wrong with it, so vague "
    "encouragement wastes their time."
)

_INSTRUCTIONS = """\
Review the parsed resume below and report what is wrong with it.

Rules:
- Every finding must point at something actually present in, or actually absent
  from, the profile. Do not invent experience, employers, or skills.
- `fix` must be a concrete rewrite or action the candidate can apply today.
  "Add metrics to your bullet points" is not acceptable; "Rewrite 'Managed
  data migration' as 'Migrated 500GB across 12 databases with 98% accuracy'"
  is.
- `evidence` quotes the specific text you are criticising. Leave it empty only
  when the finding is about something missing entirely.
- Severity: critical if it would get the resume rejected at screening,
  important if it materially weakens it, minor if it is polish.
- Do not report the absence of an email address or phone number. Those are
  removed before this review by design and are not the candidate's mistake.
- Report between 3 and 8 findings. If the resume is genuinely strong, say so
  in `overall` and return fewer findings rather than padding the list.
- Leave `ats_score` at 0 and `ats_score_reason` empty. That number is computed
  separately from parsed-profile signals, not by you.
- Every field is read by the candidate, so `overall`, `issue`, `fix` and each
  entry in `strengths` all use second person. The only exception is
  `evidence`, which quotes their resume verbatim.

Parsed resume:
{profile}
"""


def _compute_ats_score(profile: CandidateProfile, review: CvReview) -> tuple[int, str]:
    """
    Deterministic 0-100 ATS-readiness score.

    Computed from the parsed profile and this review's own findings — never
    asked of the model, so it can't drift between two runs of the same
    resume the way an LLM-estimated number would, and it still works when
    the model call itself fails (the `except` path below).

    Scope: content signals only — section completeness, keyword surface area
    (skills, titles), quantified evidence, and any structural/contact
    findings the review raised. It cannot see file formatting (columns,
    tables, fonts, headers/footers), because the review only has the parsed
    profile, not the original document — see this module's docstring. Real
    ATS parsers reject on formatting as often as content, so read this as a
    floor on ATS risk, not a full prediction.
    """
    deductions: list[tuple[int, str]] = []

    if not profile.skills:
        deductions.append((20, "Your skills section is empty, so there's nothing for keyword matching to find."))
    elif len(profile.skills) < 3:
        deductions.append((10, "Your skills section is thin — only a few keywords to match against."))

    if not profile.job_titles:
        deductions.append((10, "No job titles are listed for title-based keyword matching."))

    if not profile.experience:
        deductions.append((20, "No work experience is listed."))
    elif not any(
        any(ch.isdigit() for ch in (item.description or "")) for item in profile.experience
    ):
        deductions.append(
            (10, "None of your experience entries include a number — no quantified achievement for a screener to latch onto.")
        )

    if review.missing_sections:
        missing = review.missing_sections[:3]
        deductions.append((min(10 * len(missing), 30), f"Missing sections: {', '.join(missing)}."))

    weight = {"critical": 8, "important": 4}
    relevant_areas = {"ats", "structure", "contact"}
    finding_points = min(
        sum(
            weight[f.severity]
            for f in review.findings
            if f.area in relevant_areas and f.severity in weight
        ),
        24,
    )
    if finding_points:
        deductions.append((finding_points, "Structural or contact issues found below also hurt ATS parsing."))

    score = max(0, 100 - sum(points for points, _ in deductions))
    top_reasons = [phrase for _, phrase in sorted(deductions, key=lambda d: -d[0])[:3]]
    reason = " ".join(top_reasons) if top_reasons else "No ATS risk signals found in your parsed content."
    return score, reason


def review_profile(profile, profile_id: UUID | None = None) -> CvReview:
    """
    Runs the critique. Never raises: on model failure it returns a degraded
    review rather than propagating, because this is an optional add-on and a
    failure here should not surface as a broken page.

    ats_score is always computed, even in the degraded branch — it only needs
    the profile plus whatever findings did come back, not a working LLM call.
    """
    prompt = f"{_SYSTEM}\n\n{_INSTRUCTIONS.format(profile=profile.model_dump())}"

    try:
        # Schema-constrained at the API, the same mechanism the report
        # generator uses: the provider is given CvReview as a response schema,
        # so the closed `area` and `severity` sets cannot be violated and the
        # frontend can switch on them without validation of its own.
        result = llm.with_structured_output(CvReview).invoke(prompt)
        result.profile_id = profile_id
        result.status = "ok"
    except Exception:
        logger.exception("CV review failed for profile %s", profile_id)
        result = CvReview(
            profile_id=profile_id,
            overall=(
                "The review could not be generated this time. This does not "
                f"indicate a problem with your resume. (Model unavailable: {GlobalConfig.LLM_MODEL}.)"
            ),
            status="degraded",
        )

    result.ats_score, result.ats_score_reason = _compute_ats_score(profile, result)
    return result
