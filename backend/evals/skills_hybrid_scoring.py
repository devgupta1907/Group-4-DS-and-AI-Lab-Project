"""Hybrid normalized-entity and TF-IDF scoring for mixed-granularity skills."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from evals.normalization import normalize_skill_values
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CORRECTED_PROFILES_JSONL = (
    Path(__file__).resolve().parent / "data" / "gold_corrected_profiles_v001.jsonl"
)
COSINE_THRESHOLD = 0.50
def load_original_skills(path: Path = CORRECTED_PROFILES_JSONL) -> dict[str, list[str]]:
    return {
        row["resume_id"]: list(row["profile"].get("skills") or [])
        for row in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }


def _is_phrase(value: str) -> bool:
    return len(value.split()) > 3 or bool(re.search(r"[,;/()]", value))


def _cosine(left: str, right: str) -> float:
    try:
        vectors = TfidfVectorizer(
            lowercase=True, token_pattern=r"(?u)\b[\w+#.]+\b", ngram_range=(1, 2),
            sublinear_tf=True,
        ).fit_transform([left, right])
    except ValueError:
        return 0.0
    score = float(cosine_similarity(vectors[0], vectors[1])[0, 0])
    return score if score >= COSINE_THRESHOLD else 0.0


def skill_similarity(left: str, right: str) -> float:
    if normalize_skill_values(left) & normalize_skill_values(right):
        return 1.0
    if _is_phrase(left) or _is_phrase(right):
        return _cosine(left, right)
    return 0.0


def _directional(values: list[str], candidates: list[str]) -> float:
    if not values:
        return 1.0 if not candidates else 0.0
    return sum(max((skill_similarity(value, candidate) for candidate in candidates), default=0.0) for value in values) / len(values)


def score_record(record: dict, original_skills: dict[str, list[str]]) -> dict:
    predicted = [str(value) for value in (record.get("prediction") or {}).get("skills") or []]
    expected = original_skills.get(str(record.get("resume_id")), [])
    precision = _directional(predicted, expected)
    coverage = _directional(expected, predicted)
    f1 = 2 * precision * coverage / (precision + coverage) if precision + coverage else 0.0
    return {
        "resume_id": record.get("resume_id"), "predicted_count": len(predicted),
        "gold_count": len(expected), "hybrid_precision": precision,
        "hybrid_coverage": coverage, "hybrid_f1": f1,
    }


def score_records(records: Iterable[dict], original_skills: dict[str, list[str]]) -> list[dict]:
    return [score_record(record, original_skills) for record in records]
