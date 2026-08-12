"""Public wire contracts for the user feedback module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# Closed set, so the reasons can be grouped and counted rather than parsed out
# of free text later. "other" exists so a reason outside the list does not force
# the user to pick something inaccurate.
REASON_CHOICES: tuple[str, ...] = (
    "accurate_recommendations",
    "irrelevant_recommendations",
    "useful_job_matches",
    "poor_job_matches",
    "clear_explanations",
    "confusing_explanations",
    "resume_parsed_correctly",
    "resume_parsed_incorrectly",
    "helpful_action_plan",
    "too_slow",
    "easy_to_use",
    "other",
)

REASON_LABELS: dict[str, str] = {
    "accurate_recommendations": "Career recommendations felt accurate",
    "irrelevant_recommendations": "Career recommendations felt irrelevant",
    "useful_job_matches": "Job matches were useful",
    "poor_job_matches": "Job matches were poor",
    "clear_explanations": "Explanations were clear",
    "confusing_explanations": "Explanations were confusing",
    "resume_parsed_correctly": "My resume was read correctly",
    "resume_parsed_incorrectly": "My resume was read incorrectly",
    "helpful_action_plan": "The action plan was helpful",
    "too_slow": "It took too long",
    "easy_to_use": "It was easy to use",
    "other": "Something else",
}


class SubmitFeedbackRequest(BaseModel):
    # ge/le are enforced here rather than only in the UI, so a request made
    # outside the app cannot store a rating the scale does not define.
    rating: int = Field(ge=1, le=10, description="Overall rating, 1 to 10.")
    reasons: list[str] = Field(
        default_factory=list,
        description=f"Zero or more of: {', '.join(REASON_CHOICES)}.",
    )
    comment: str = Field(default="", max_length=2000)
    # Optional: feedback is worth collecting even from someone who never
    # completed a run, so this is not required.
    profile_id: UUID | None = None


class FeedbackRecord(BaseModel):
    """What the API returns after a successful submission."""

    feedback_id: UUID
    rating: int
    reasons: list[str]
    comment: str
    profile_id: UUID | None = None
    created_at: datetime


class FeedbackSummary(BaseModel):
    """Aggregate view, for reporting rather than for the end user."""

    responses: int
    mean_rating: float
    rating_distribution: dict[int, int]
    reason_counts: dict[str, int]
