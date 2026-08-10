"""Position-aligned experience-description diagnostics for saved predictions."""

from __future__ import annotations

from collections.abc import Iterable

from evals.normalization import normalize_company, normalize_field_value
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_IDENTITY_FIELDS = ("job_title", "company", "start_date", "end_date")
_IDENTITY_WEIGHTS = {"job_title": 2, "company": 2, "start_date": 3, "end_date": 3}
def _cosine(predicted: object, expected: object) -> float:
    """Pair-local TF-IDF cosine; deterministic and requires no language model."""
    if not isinstance(predicted, str) or not isinstance(expected, str):
        return 0.0
    try:
        vectors = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b[\w+#.]+\b",
            sublinear_tf=True,
        ).fit_transform([predicted, expected])
    except ValueError:  # both strings contain no usable tokens
        return 0.0
    return float(cosine_similarity(vectors[0], vectors[1])[0, 0])


def _identity_value(entry: dict, field: str) -> str:
    value = entry.get(field)
    if field == "company":
        return normalize_company(value, location=entry.get("location"))
    return normalize_field_value(f"experience.{field}", value)


def _identity_score(predicted: dict, expected: dict) -> int:
    score = 0
    for field in _IDENTITY_FIELDS:
        left = _identity_value(predicted, field)
        right = _identity_value(expected, field)
        if left and right and left == right:
            score += _IDENTITY_WEIGHTS[field]
    return score


def _experience_entries(profile: dict) -> list[dict]:
    return [entry for entry in profile.get("experience") or [] if isinstance(entry, dict)]


def score_description_entries(record: dict) -> list[dict]:
    """Score each gold description against the predicted entry at the same index.

    Both profiles are expected to preserve resume reading order. Identity agreement
    is retained as a diagnostic, but does not gate description comparison because
    an extraction error in title/company/date must not masquerade as a missing
    description. A missing positional entry or description receives zero. Gold
    experiences without descriptions are not applicable and are omitted.
    """
    predicted = _experience_entries(record.get("prediction") or {})
    expected = _experience_entries(record.get("reference") or {})

    rows = []
    for gold_index, gold_entry in enumerate(expected):
        gold_description = gold_entry.get("description")
        if not isinstance(gold_description, str) or not gold_description.strip():
            continue
        predicted_entry = predicted[gold_index] if gold_index < len(predicted) else None
        predicted_description = predicted_entry.get("description") if predicted_entry else None
        has_description = isinstance(predicted_description, str) and predicted_description.strip()
        rows.append({
            "resume_id": record.get("resume_id"),
            "gold_experience_index": gold_index,
            "predicted_experience_index": gold_index if predicted_entry else None,
            "alignment_method": "list_index",
            "identity_match_score": (
                _identity_score(predicted_entry, gold_entry) if predicted_entry else 0
            ),
            "gold_job_title": gold_entry.get("job_title"),
            "gold_company": gold_entry.get("company"),
            "gold_start_date": gold_entry.get("start_date"),
            "gold_end_date": gold_entry.get("end_date"),
            "predicted_job_title": predicted_entry.get("job_title") if predicted_entry else None,
            "predicted_company": predicted_entry.get("company") if predicted_entry else None,
            "description_found": int(bool(has_description)),
            "description_cosine": (
                _cosine(predicted_description, gold_description)
                if has_description else 0.0
            ),
            "predicted_description": predicted_description,
            "gold_description": gold_description,
        })
    return rows


def score_description_record(record: dict) -> dict:
    """Resume-level coverage and cosine over applicable gold experiences."""
    rows = score_description_entries(record)
    count = len(rows)
    return {
        "resume_id": record.get("resume_id"),
        "gold_experience_descriptions": count,
        "matched_experience_descriptions": sum(row["description_found"] for row in rows),
        "description_coverage": (
            sum(row["description_found"] for row in rows) / count if count else None
        ),
        "description_cosine": (
            sum(row["description_cosine"] for row in rows) / count if count else None
        ),
    }


def score_description_records(records: Iterable[dict]) -> list[dict]:
    return [score_description_record(record) for record in records]


def score_all_description_entries(records: Iterable[dict]) -> list[dict]:
    return [row for record in records for row in score_description_entries(record)]
