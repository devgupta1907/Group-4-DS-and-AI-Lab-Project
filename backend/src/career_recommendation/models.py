"""
Career Recommendation — Candidate Profile contract.

This is the validated input boundary between Resume Parsing (upstream,
writes it) and Career Recommendation (this module, reads it). Every
field here mirrors what `retrieval.build_query_text()` and
`re_ranker.deterministic_rerank()` already read out of a plain dict —
this model just makes that contract explicit and checkable, instead of
each function doing `.get(...)` against an unvalidated dict.

Nothing downstream changes: `retrieve_candidate_occupations()` and
`deterministic_rerank()` still take plain dicts (via `.model_dump()`),
so this model is additive. `service.py` is the one place that requires
a `CandidateProfile` on the way in.

NOTE: field names/shape are inferred from current usage in
retrieval.py and re_ranker.py (job_titles, skills, experience[].title,
projects[].description, education[].degree/field). If the actual
Resume Parsing output schema (parsed_resume_schema.json) differs in
field naming, reconcile the two at merge time — this is the piece
flagged as "merge-critical" in the handoff notes.
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
        description="Stable identifier for this candidate, if known. "
        "Required to persist/retrieve recommendations via the API "
        "layer; optional for a one-off `service.recommend_for_profile` call.",
    )
    job_titles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)

    @field_validator("job_titles", "skills", mode="before")
    @classmethod
    def _drop_blank_strings(cls, value):
        if value is None:
            return []
        return [v for v in value if isinstance(v, str) and v.strip()]

    def has_usable_signal(self) -> bool:
        """
        Mirrors the check in retrieval.build_query_text(): a profile
        with nothing to embed should be rejected before it reaches the
        vector store, with a clear error, rather than raising deep
        inside retrieval.
        """
        return bool(
            self.job_titles
            or self.skills
            or any(e.title for e in self.experience)
            or any(p.description for p in self.projects)
            or any(e.degree or e.field for e in self.education)
        )
