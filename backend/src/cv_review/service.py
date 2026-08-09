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
- Leave `score` at 0 and `score_reason` empty. A single number carries no
  scale or basis for the reader, so it is not shown.
- Every field is read by the candidate, so `overall`, `issue`, `fix`,
  `score_reason` and each entry in `strengths` all use second person. The only
  exception is `evidence`, which quotes their resume verbatim.

Parsed resume:
{profile}
"""


def review_profile(profile, profile_id: UUID | None = None) -> CvReview:
    """
    Runs the critique. Never raises: on model failure it returns a degraded
    review rather than propagating, because this is an optional add-on and a
    failure here should not surface as a broken page.
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
        return result
    except Exception:
        logger.exception("CV review failed for profile %s", profile_id)
        return CvReview(
            profile_id=profile_id,
            overall=(
                "The review could not be generated this time. This does not "
                "indicate a problem with your resume."
            ),
            status="degraded",
            score_reason=f"Model unavailable ({GlobalConfig.LLM_MODEL}).",
        )
