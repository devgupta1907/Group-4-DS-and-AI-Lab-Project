"""Unit tests for the pure pipeline stages.

No database, no API key, no fixtures — which is the payoff for keeping these
stages free of I/O.
"""

from __future__ import annotations

import io

import fitz
import pytest

from src.resume_parsing.errors import TooManyPages, UnreadableDocument, UnsupportedFileType
from src.resume_parsing.internal.pipeline import postprocess, routing, validation
from src.resume_parsing.internal.providers.base import ProviderError
from src.resume_parsing.internal.providers.google_ai_studio import (
    extract_json_object,
    to_gemini_schema,
)
from src.resume_parsing.schemas import ParseRoute


def _pdf(lines: list[str] | None, pages: int = 1) -> bytes:
    """A synthetic PDF. `lines=None` produces a page with no text layer at all."""
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page()
        for i, line in enumerate(lines or []):
            page.insert_text((72, 72 + i * 16), line, fontsize=11)
    buffer = io.BytesIO(doc.tobytes())
    doc.close()
    return buffer.getvalue()


TEXT_RESUME = ["Jane Doe — Data Analyst"] + [f"Skill line {i}: Python, SQL" for i in range(8)]


# ------------------------------------------------------------------- routing --


def test_pdf_with_a_text_layer_takes_the_text_path() -> None:
    document = routing.route("cv.pdf", "application/pdf", _pdf(TEXT_RESUME))
    assert document.route is ParseRoute.TEXT
    assert document.page_count == 1


def test_image_only_pdf_falls_back_to_vision() -> None:
    """The working corpus is entirely image-only, so this is the common path."""
    document = routing.route("scan.pdf", "application/pdf", _pdf(None))
    assert document.route is ParseRoute.VISION


def test_sparse_text_is_treated_as_image_only() -> None:
    """A few stray characters must not be mistaken for a usable text layer."""
    document = routing.route("scan.pdf", "application/pdf", _pdf(["Page 1"]))
    assert document.route is ParseRoute.VISION


def test_extension_beats_a_wrong_declared_content_type() -> None:
    document = routing.route("cv.pdf", "application/octet-stream", _pdf(TEXT_RESUME))
    assert document.media_type == "application/pdf"


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(UnsupportedFileType):
        routing.route("notes.txt", "text/plain", b"hello")


def test_empty_upload_is_rejected() -> None:
    with pytest.raises(UnreadableDocument):
        routing.route("cv.pdf", "application/pdf", b"")


def test_page_limit_is_enforced() -> None:
    with pytest.raises(TooManyPages):
        routing.route("long.pdf", "application/pdf", _pdf(None, pages=25))


# --------------------------------------------------------------- postprocess --


def test_normalise_fills_missing_keys_rather_than_dropping_them() -> None:
    result = postprocess.normalise({"skills": ["Python"]})
    assert set(result) == {
        "contact", "skills", "education", "experience",
        "projects", "certifications", "job_titles",
    }
    assert result["contact"] == {"name": None, "location": None, "links": []}
    assert result["education"] == []


def test_blank_scalars_become_null() -> None:
    result = postprocess.normalise({"contact": {"name": "   ", "location": "Pune"}})
    assert result["contact"]["name"] is None
    assert result["contact"]["location"] == "Pune"


def test_skills_deduplicate_case_insensitively_keeping_first_casing() -> None:
    result = postprocess.normalise({"skills": ["Python", "python", "PYTHON", "SQL"]})
    assert result["skills"] == ["Python", "SQL"]


def test_dates_are_preserved_exactly_as_written() -> None:
    result = postprocess.normalise(
        {"experience": [{"job_title": "Dev", "start_date": "Jan '21", "end_date": "Present"}]}
    )
    assert result["experience"][0]["start_date"] == "Jan '21"
    assert result["experience"][0]["end_date"] == "Present"


def test_merge_takes_contact_from_the_first_page_that_has_it() -> None:
    profile = postprocess.merge([
        postprocess.normalise({"contact": {"name": "Jane Doe"}, "skills": ["Python"]}),
        postprocess.normalise({"contact": {"name": "Page Two Header"}, "skills": ["SQL"]}),
    ])
    assert profile.contact.name == "Jane Doe"
    assert profile.skills == ["Python", "SQL"]


def test_merge_deduplicates_experience_repeated_across_pages() -> None:
    page = postprocess.normalise(
        {"experience": [{"job_title": "Analyst", "company": "Acme", "start_date": "2020"}]}
    )
    profile = postprocess.merge([page, page])
    assert len(profile.experience) == 1


def test_merge_of_an_empty_resume_is_a_valid_empty_profile() -> None:
    profile = postprocess.merge([postprocess.normalise({})])
    assert profile.skills == []
    assert profile.contact.name is None


# ---------------------------------------------------------------- validation --


def _profile(**overrides) -> dict:
    base = postprocess.normalise({
        "contact": {"name": "Jane Doe", "location": "Pune"},
        "skills": ["Python", "SQL"],
        "education": [{"degree": "BTech", "institution": "IITM"}],
        "experience": [{"job_title": "Analyst", "company": "Acme"}],
        "job_titles": ["Analyst"],
    })
    base.update(overrides)
    return base


def test_a_complete_profile_passes_the_gate() -> None:
    report = validation.validate(_profile())
    assert report.schema_ok
    assert report.coverage == pytest.approx(1.0)
    assert report.is_acceptable(0.4)


def test_a_fresher_with_no_experience_is_still_valid() -> None:
    """Absence is a valid state, not a schema failure."""
    report = validation.validate(_profile(experience=[], projects=[], certifications=[]))
    assert report.schema_ok
    assert "experience" in report.needs_review


def test_a_transcribed_email_makes_the_profile_invalid() -> None:
    """The validator, not the prompt, is what actually keeps PII out."""
    payload = _profile()
    payload["contact"]["email"] = "jane@example.com"
    report = validation.validate(payload)
    assert not report.schema_ok


def test_a_transcribed_phone_number_makes_the_profile_invalid() -> None:
    payload = _profile()
    payload["contact"]["phone"] = "+91 90000 00000"
    assert not validation.validate(payload).schema_ok


def test_a_nearly_empty_profile_falls_below_the_repair_threshold() -> None:
    report = validation.validate(postprocess.normalise({}))
    assert report.schema_ok
    assert not report.is_acceptable(0.4)


# ------------------------------------------------------------------ provider --


def test_json_is_recovered_from_a_fenced_reply() -> None:
    assert extract_json_object('```json\n{"skills": ["Go"]}\n```') == {"skills": ["Go"]}


def test_json_is_recovered_from_a_reply_wrapped_in_prose() -> None:
    text = 'Here is the profile:\n{"skills": ["Go"]}\nHope that helps.'
    assert extract_json_object(text) == {"skills": ["Go"]}


def test_braces_inside_strings_do_not_break_recovery() -> None:
    text = 'prefix {"contact": {"name": "A } B"}, "skills": []} suffix'
    assert extract_json_object(text)["contact"]["name"] == "A } B"


def test_a_reply_with_no_object_is_a_provider_error() -> None:
    with pytest.raises(ProviderError):
        extract_json_object("I could not read this resume.")


def test_empty_reply_is_a_provider_error() -> None:
    with pytest.raises(ProviderError):
        extract_json_object("")


def test_nullable_types_convert_to_the_gemini_dialect() -> None:
    converted = to_gemini_schema({"type": ["string", "null"], "additionalProperties": False})
    assert converted == {"type": "string", "nullable": True}


def test_conversion_recurses_through_arrays_and_objects() -> None:
    converted = to_gemini_schema({
        "type": "object",
        "properties": {"links": {"type": "array", "items": {"type": ["string", "null"]}}},
    })
    assert converted["properties"]["links"]["items"] == {"type": "string", "nullable": True}
