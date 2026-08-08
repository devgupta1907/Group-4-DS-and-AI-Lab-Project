"""
Career Recommendation — Candidate Profile contract.

This is the validated boundary between Resume Parsing and this module. 
This model makes the contract explicit and checkable, instead of a bad
profile failing somewhere deep in the pipeline.

"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator


class ExperienceEntry(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    current_role: bool | None = None
    description: str | None = None


class EducationEntry(BaseModel):
    degree: str | None = None
    field: str | None = None
    institution: str | None = None
    start_year: str | None = None
    end_year: str | None = None


class ProjectEntry(BaseModel):
    name: str | None = None
    description: str | None = None


class CandidateProfile(BaseModel):
    """
    Validated candidate profile. All list fields default to empty
    rather than being required, since a sparse profile (e.g. no skills
    listed) is a real, handled case in re_ranker.py — not a validation
    failure.
    """

    candidate_id: str | None = Field(
        default=None,
        description="Identifier for this candidate; retrieve recommendations through the API layer (store.py);"
    )
    job_titles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)


    @field_validator("job_titles", "skills", mode="before")
    @classmethod
    def _drop_blank_strings(cls, value):
        """
        Resume-parsing output can realistically include empty or whitespace-only entries.
        This validator cleans them out so that the rest of the pipeline doesn't have to deal with them.
        """
        if value is None:
            return []
        return [v for v in value if isinstance(v, str) and v.strip()]


    def has_usable_signal(self) -> bool:
        """
        True if there's anything in this profile worth searching on.
        """
        return bool(
            self.job_titles
            or self.skills
            or any(e.title for e in self.experience)
            or any(p.description for p in self.projects)
            or any(e.degree or e.field for e in self.education)
        )
