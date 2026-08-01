"""Evaluators scoring one predicted profile against its gold profile.

Every metric is deterministic Python — no LLM judge — so a run costs exactly one
model call per resume and the numbers are reproducible.

Matching is case- and whitespace-insensitive. List sections are scored as sets
because resume order is not meaningful; multi-field sections (education,
experience) match on their identifying pair only, so a wrong end-date does not
destroy an otherwise correct entry.

Empty-vs-empty scores 1.0 by design: a fresher genuinely has no experience, and
the AGENTS.md model contract states absence is a valid state, not a failure.
"""

from __future__ import annotations

import re

from src.resume_parsing.internal.pipeline.validation import validate

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

# A loose span first, then two filters. Resumes are dense with date ranges, and
# "2010-2011" matches any digit-and-separator pattern permissive enough to catch
# "+91-7286852018". Requiring 10 digits separates them; the year-range guard
# covers the rest.
_PHONE_SPAN = re.compile(r"\+?\d[\d\s().–-]{7,}\d")
_YEAR_RANGE = re.compile(
    r"^\s*(?:19|20)\d{2}\s*[-–/]\s*(?:(?:19|20)\d{2}|present)\s*$", re.IGNORECASE
)
_MIN_PHONE_DIGITS = 10


def _norm(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().split())


def _prf(predicted: set[str], gold: set[str]) -> tuple[float, float, float]:
    """Precision, recall, F1 for one set pair."""
    if not predicted and not gold:
        return 1.0, 1.0, 1.0
    if not predicted or not gold:
        return 0.0, 0.0, 0.0
    hits = len(predicted & gold)
    precision = hits / len(predicted)
    recall = hits / len(gold)
    if precision + recall == 0:
        return 0.0, 0.0, 0.0
    return precision, recall, 2 * precision * recall / (precision + recall)


def _strings(profile: dict, section: str) -> set[str]:
    values = profile.get(section) or []
    return {_norm(v) for v in values if _norm(v)}


def _entities(profile: dict, section: str, keys: tuple[str, ...]) -> set[str]:
    """Identify an entry by its key fields only, joined into one comparable token."""
    out = set()
    for entry in profile.get(section) or []:
        if not isinstance(entry, dict):
            continue
        token = "|".join(_norm(entry.get(k)) for k in keys)
        if token.strip("|"):
            out.add(token)
    return out


def _phone_hits(blob: str) -> list[str]:
    return [
        span
        for span in _PHONE_SPAN.findall(blob)
        if sum(c.isdigit() for c in span) >= _MIN_PHONE_DIGITS
        and not _YEAR_RANGE.match(span)
    ]


def _contains_pii(profile: dict) -> bool:
    blob = repr(profile)
    return bool(_EMAIL.search(blob) or _phone_hits(blob))


def field_metrics(outputs: dict, reference_outputs: dict) -> list[dict]:
    """Per-field precision/recall/F1 plus the aggregate, as LangSmith feedback."""
    predicted, gold = outputs or {}, reference_outputs or {}
    scores: list[dict] = []

    sections = {
        "skills": _strings(predicted, "skills"),
        "job_titles": _strings(predicted, "job_titles"),
    }
    gold_sections = {
        "skills": _strings(gold, "skills"),
        "job_titles": _strings(gold, "job_titles"),
    }
    sections["education"] = _entities(predicted, "education", ("degree", "institution"))
    gold_sections["education"] = _entities(gold, "education", ("degree", "institution"))
    sections["experience"] = _entities(predicted, "experience", ("job_title", "company"))
    gold_sections["experience"] = _entities(gold, "experience", ("job_title", "company"))

    f1s = []
    for name, predicted_set in sections.items():
        precision, recall, f1 = _prf(predicted_set, gold_sections[name])
        f1s.append(f1)
        scores += [
            {"key": f"{name}_precision", "score": round(precision, 4)},
            {"key": f"{name}_recall", "score": round(recall, 4)},
            {"key": f"{name}_f1", "score": round(f1, 4)},
        ]

    predicted_name = _norm((predicted.get("contact") or {}).get("name"))
    gold_name = _norm((gold.get("contact") or {}).get("name"))
    # Two gold resumes print no name at all. Correctly returning null for them is
    # a hit, not a miss — same "absence is a valid state" rule the sets follow.
    name_score = float(predicted_name == gold_name)
    f1s.append(name_score)
    scores.append({"key": "name_match", "score": name_score})

    scores.append({"key": "profile_f1_macro", "score": round(sum(f1s) / len(f1s), 4)})
    return scores


def schema_metrics(outputs: dict) -> list[dict]:
    """The production gate, scored: schema validity, coverage, and PII leakage.

    Runs the same `validation.validate` the pipeline runs, so a green experiment
    means the profile would genuinely have been persisted.
    """
    profile = outputs or {}
    report = validate(profile)
    return [
        {"key": "schema_valid", "score": float(report.schema_ok)},
        {"key": "coverage", "score": report.coverage},
        # 1.0 == clean. Scored positively so every metric reads "higher is better".
        {"key": "pii_clean", "score": float(not _contains_pii(profile))},
    ]


EVALUATORS = [field_metrics, schema_metrics]
