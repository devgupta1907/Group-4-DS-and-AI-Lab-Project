"""Stage 4 — normalise raw model output and merge multi-page results.

Rules applied here, all from MS3 §8.5:
  * trim whitespace; empty scalars become null, missing lists become []
  * keys are never dropped, so the shape is stable for downstream modules
  * dates are preserved exactly as written
  * skills are deduplicated case-insensitively, keeping first-seen casing
  * repeated experience / education / project entries across pages collapse
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.resume_parsing.internal.location import locality_only
from src.resume_parsing.schemas import CandidateProfile

_LIST_SECTIONS = ("skills", "education", "experience", "projects", "certifications")


def normalise(payload: dict) -> dict:
    """Coerce one page's raw output into the schema's shape."""
    contact = payload.get("contact") or {}
    if not isinstance(contact, dict):
        contact = {}

    experience = [_experience(e) for e in _objects(payload.get("experience"))]
    return {
        "contact": {
            "name": _scalar(contact.get("name")),
            "location": locality_only(contact.get("location")),
            "links": _unique_strings(contact.get("links")),
        },
        "skills": _unique_strings(payload.get("skills")),
        "education": [_entry(e, ("degree", "field", "institution", "start_year",
                                "end_year")) for e in _objects(payload.get("education"))],
        "experience": experience,
        "projects": [_project(p) for p in _objects(payload.get("projects"))],
        "certifications": [
            _entry(c, ("name", "issuer", "year")) for c in _objects(payload.get("certifications"))
        ],
        "job_titles": _titles_from_experience(experience),
    }


def merge(pages: Iterable[dict]) -> CandidateProfile:
    """Fold per-page results into one profile.

    Contact scalars take the first non-empty value seen, because identity
    appears on page one. List sections concatenate and then deduplicate.
    """
    merged: dict[str, Any] = {
        "contact": {"name": None, "location": None, "links": []},
        **{section: [] for section in _LIST_SECTIONS},
    }

    for page in pages:
        contact = page.get("contact", {})
        for key in ("name", "location"):
            if merged["contact"][key] is None:
                merged["contact"][key] = contact.get(key)
        merged["contact"]["links"].extend(contact.get("links", []))
        for section in _LIST_SECTIONS:
            merged[section].extend(page.get(section, []))

    merged["contact"]["links"] = _unique_strings(merged["contact"]["links"])
    merged["skills"] = _unique_strings(merged["skills"])
    merged["job_titles"] = _titles_from_experience(merged["experience"])
    for section in ("education", "experience", "projects", "certifications"):
        merged[section] = _unique_objects(merged[section])

    return CandidateProfile.model_validate(merged)


# ------------------------------------------------------------------ coercion --


def _scalar(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "present", "current"}:
            return True
        if lowered in {"false", "no"}:
            return False
    return None


def _objects(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _unique_strings(value: Any) -> list[str]:
    """Deduplicate case-insensitively while preserving first-seen casing."""
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        text = _scalar(item)
        if text is None:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _titles_from_experience(entries: list[dict]) -> list[str]:
    """Derive the downstream title list; the model never predicts it twice."""
    return _unique_strings([entry.get("job_title") for entry in entries])


def _entry(raw: dict, keys: tuple[str, ...]) -> dict:
    return {key: _scalar(raw.get(key)) for key in keys}


def _experience(raw: dict) -> dict:
    entry = _entry(raw, ("job_title", "company", "location", "start_date",
                         "end_date", "description"))
    entry["location"] = locality_only(raw.get("location"))
    entry["current_role"] = _boolean(raw.get("current_role"))
    return entry


def _project(raw: dict) -> dict:
    entry = _entry(raw, ("name", "description"))
    entry["technologies"] = _unique_strings(raw.get("technologies"))
    return entry


def _unique_objects(entries: list[dict]) -> list[dict]:
    """Drop entries that are duplicates ignoring case and free-text description."""
    seen: set[tuple] = set()
    result: list[dict] = []
    for entry in entries:
        key = tuple(
            (k, v.casefold() if isinstance(v, str) else v)
            for k, v in sorted(entry.items())
            if k not in {"description", "technologies"}
        )
        if key in seen or not any(v for _, v in key):
            continue
        seen.add(key)
        result.append(entry)
    return result
