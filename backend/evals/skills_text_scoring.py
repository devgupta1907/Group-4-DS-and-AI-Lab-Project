"""Simple whole-section TF-IDF diagnostics for resume skills."""

from __future__ import annotations

from collections.abc import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _skill_text(profile: dict) -> str:
    values = profile.get("skills") or []
    return " ; ".join(str(value).strip() for value in values if str(value).strip())


def _cosine(predicted: str, expected: str) -> float:
    if not predicted.strip() or not expected.strip():
        return 0.0
    try:
        vectors = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b[\w+#.]+\b",
            ngram_range=(1, 2),
            sublinear_tf=True,
        ).fit_transform([predicted, expected])
    except ValueError:
        return 0.0
    return float(cosine_similarity(vectors[0], vectors[1])[0, 0])


def score_skills_record(record: dict) -> dict:
    predicted = _skill_text(record.get("prediction") or {})
    expected = _skill_text(record.get("reference") or {})
    applicable = bool(expected)
    found = bool(predicted)
    return {
        "resume_id": record.get("resume_id"),
        "gold_skills_text": expected,
        "predicted_skills_text": predicted,
        "skills_applicable": int(applicable),
        "skills_section_found": int(applicable and found),
        "skills_text_cosine": _cosine(predicted, expected) if applicable else None,
    }


def score_skills_records(records: Iterable[dict]) -> list[dict]:
    return [score_skills_record(record) for record in records]
