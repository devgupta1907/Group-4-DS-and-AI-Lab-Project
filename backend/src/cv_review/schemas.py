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
    # Scored 0-100 so the UI can show a single headline number. It is a
    # heuristic quality signal, not a prediction of hiring outcome.
    score: int = Field(default=0, ge=0, le=100)
    score_reason: str = Field(default="")
    status: str = Field(default="ok", description="ok | degraded")
