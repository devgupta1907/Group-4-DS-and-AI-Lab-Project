"""Public wire contracts for the CV review add-on."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Severity = Literal["critical", "important", "minor"]

# Kept as a closed set so the frontend can group and colour findings without
# defensive string handling, and so the model cannot invent a category.
Area = Literal[
    "contact",
    "structure",
    "experience",
    "skills",
    "education",
    "wording",
    "quantification",
    "ats",
]


class ReviewCvRequest(BaseModel):
    profile_id: UUID


class CvFinding(BaseModel):
    area: Area
    severity: Severity
    issue: str = Field(description="What is wrong, in one sentence.")
    evidence: str = Field(
        default="",
        description="The part of the CV this refers to. Empty when the finding is about something absent.",
    )
    fix: str = Field(description="A concrete rewrite or action, not general advice.")


class CvReview(BaseModel):
    """
    The whole review. Every field has a default so a partial model response
    still validates — the same fail-soft rule the report generator uses.
    """

    profile_id: UUID | None = None
    overall: str = Field(
        default="No assessment could be produced from the parsed profile.",
        description="Two or three sentences on the CV as a whole.",
    )
    strengths: list[str] = Field(default_factory=list)
    findings: list[CvFinding] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    # Computed deterministically from the parsed profile and this review's own
    # findings — never asked of the model, see cv_review/service.py:_compute_ats_score.
    # Scope is content signals only (sections, keywords, quantification): the
    # review has no access to the original file, so it cannot see formatting-
    # driven ATS rejections (columns, tables, unusual fonts). Treat this as a
    # floor on ATS risk, not a full prediction.
    ats_score: int = Field(default=0, ge=0, le=100)
    ats_score_reason: str = Field(default="")
    status: str = Field(default="ok", description="ok | degraded")
