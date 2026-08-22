"""
Job Discovery & Matching — profile mapping from Resume Parsing output.

THE MERGE POINT, same role as career_recommendation/profile_mapper.py.
This module ignores career-agent's own `CandidateProfile` (the schema it
shipped with, in app/schemas.py) entirely and instead maps from the one
real upstream contract in this repo: `resume_parsing.schemas.CandidateProfile`.

Field translation, and why:

    resume_parsing field                       -> internal candidate_json field
    ------------------------------------------    --------------------------------
    contact.location                           -> location
    job_titles                                 -> target_roles
    skills                                      -> skills                 (verbatim)
    most recent experience[].job_title          -> current_role
    (none — not modelled upstream)              -> domain            (left "")
    (none — not modelled upstream)              -> experience_years  (left None)
    (none — not modelled upstream)              -> remote_ok         (left False;
                                                      preferences.remote_only is the
                                                      real signal, applied in hard_filter)
    (none — not modelled upstream)              -> min_salary_lpa   (left 0.0)

`experience_years` and `domain` are not fields resume_parsing publishes
(see its CandidateProfile) and inferring them (e.g. by parsing date
ranges) is out of scope here. They are left at safe defaults, and
`internal/pipeline/nodes/hard_filter.py` treats an unknown
`experience_years` as "no signal, don't disqualify" rather than as zero
years of experience — so a sparse profile is never penalised for a field
resume_parsing simply doesn't send yet. If richer signal becomes
available upstream, extend this one function.
"""

from __future__ import annotations

from typing import Any

from src.resume_parsing.schemas import CandidateProfile as ParsedProfile


def _current_role(parsed: ParsedProfile) -> str:
    for entry in parsed.experience:
        if entry.current_role and entry.job_title:
            return entry.job_title
    if parsed.experience and parsed.experience[0].job_title:
        return parsed.experience[0].job_title
    if parsed.job_titles:
        return parsed.job_titles[0]
    return ""


def from_parsed_resume(
    parsed: ParsedProfile, preferences: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Translates a Resume Parsing profile into the internal candidate dict
    the ported job-discovery pipeline (query_generator, hard_filter,
    matching_module, judge_module) reads out of `state["candidate_json"]`.

    `preferences` (a `SearchPreferences.model_dump()`) overlays the
    candidate's SEARCH-TIME choices on top of what the resume says about
    them: `target_location` overrides the resume's `contact.location` for
    `location` (a candidate may live in Delhi but be searching for
    Bengaluru roles), `remote_only` sets `remote_ok`, and `min_salary_lpa`
    is no longer left at a hardcoded 0.0 -- it now reflects what the
    candidate actually asked for, since these three fields are exactly
    what query_generator/hard_filter/judge_module read `candidate_json`
    for. Falling back to the resume's own location keeps this backward
    compatible with any caller that doesn't pass preferences."""
    prefs = preferences or {}
    target_location = prefs.get("target_location") or (parsed.contact.location or "")
    return {
        "current_role": _current_role(parsed),
        "target_roles": list(parsed.job_titles),
        "skills": list(parsed.skills),
        "domain": "",
        "location": target_location,
        "remote_ok": bool(prefs.get("remote_only", False)),
        "experience_years": None,
        "min_salary_lpa": float(prefs.get("min_salary_lpa") or 0.0),
        "education": (parsed.education[0].degree or "") if parsed.education else "",
    }


def has_usable_signal(candidate_json: dict[str, Any]) -> bool:
    """A profile with nothing to search or embed against should be
    rejected before it reaches the pipeline, with a clear status, rather
    than silently producing zero search queries."""
    return bool(
        candidate_json.get("skills")
        or candidate_json.get("current_role")
        or candidate_json.get("target_roles")
    )
