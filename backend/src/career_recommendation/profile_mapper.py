"""
Career Recommendation — profile mapping from Resume Parsing output.

THE MERGE POINT. Resume Parsing and Career Recommendation each define
their own `CandidateProfile`, and the field names do NOT line up:

    resume_parsing.schemas.Experience.job_title
        -> career_recommendation.models.ExperienceEntry.title

Everything else matches by name. Rather than change either module's
schema (each is validated against its own tests and, for resume parsing,
against parsed_resume_schema.json), the translation lives here — one
function, one place to look when a field goes missing downstream.

Fields deliberately dropped: `contact` (name, location, links) and
`certifications`. Neither is read by retrieval.build_query_text() or
re_ranker.deterministic_rerank(), and contact is PII with no career
signal. If certifications later prove useful as retrieval signal, add
them to career_recommendation.models.CandidateProfile first, then map
them here.
"""

from __future__ import annotations

from src.career_recommendation.models import (
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
)
from src.resume_parsing.schemas import CandidateProfile as ParsedProfile


def from_parsed_resume(parsed: ParsedProfile) -> CandidateProfile:
    """Translates a Resume Parsing profile into the Career Recommendation one."""
    return CandidateProfile(
        job_titles=list(parsed.job_titles),
        skills=list(parsed.skills),
        experience=[
            ExperienceEntry(
                title=e.job_title,  # <- the one field that is renamed
                company=e.company,
                location=e.location,
                start_date=e.start_date,
                end_date=e.end_date,
                current_role=e.current_role,
                description=e.description,
            )
            for e in parsed.experience
        ],
        education=[
            EducationEntry(
                degree=e.degree,
                field=e.field,
                institution=e.institution,
                start_year=e.start_year,
                end_year=e.end_year,
            )
            for e in parsed.education
        ],
        projects=[
            ProjectEntry(name=p.name, description=p.description)
            for p in parsed.projects
        ],
    )
