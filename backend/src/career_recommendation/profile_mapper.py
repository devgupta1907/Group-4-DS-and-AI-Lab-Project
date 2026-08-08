"""
Career Recommendation — profile mapping from Resume Parsing output.

The merge point between two independently-built modules. Resume
Parsing and Career Recommendation each define their own
CandidateProfile, and the field names don't line up everywhere:

    resume_parsing.schemas.Experience.job_title
        -> career_recommendation.models.ExperienceEntry.title


Fields deliberately dropped on the way through:
  - contact (name, location, links): pure PII, and nothing downstream
    (retrieval.build_query_text, re_ranker.deterministic_rerank) reads
    it for matching.
  - certifications: not currently used as a retrieval signal.
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
                title=e.job_title,
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
