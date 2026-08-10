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
import unicodedata
from difflib import SequenceMatcher

from src.resume_parsing.internal.location import locality_only
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
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_CURRENT = {"present", "current", "ongoing", "till date", "to date", "now"}
_DEGREE_ALIASES = {
    "ba": "bachelor of arts",
    "bachelorarts": "bachelor of arts",
    "be": "bachelor of engineering",
    "beng": "bachelor of engineering",
    "bachelorengineering": "bachelor of engineering",
    "bs": "bachelor of science",
    "bsc": "bachelor of science",
    "bachelorscience": "bachelor of science",
    "btech": "bachelor of technology",
    "bachelortechnology": "bachelor of technology",
    "ma": "master of arts",
    "masterarts": "master of arts",
    "me": "master of engineering",
    "meng": "master of engineering",
    "masterengineering": "master of engineering",
    "ms": "master of science",
    "msc": "master of science",
    "masterscience": "master of science",
    "mtech": "master of technology",
    "mastertechnology": "master of technology",
    "phd": "doctor of philosophy",
    "doctorphilosophy": "doctor of philosophy",
}
_EDUCATION_MATCH_THRESHOLD = 0.85


def _norm(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().split())


def _lookup_key(value: object) -> str:
    """Unicode/case/punctuation-insensitive key for controlled aliases."""
    text = unicodedata.normalize("NFKC", _norm(value))
    return "".join(character for character in text if character.isalnum())


def _norm_degree(value: object) -> str:
    text = _norm(value)
    return _DEGREE_ALIASES.get(_lookup_key(value), text)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return float(left == right)
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _education_entries(profile: dict) -> list[dict]:
    entries = []
    for entry in profile.get("education") or []:
        if not isinstance(entry, dict):
            continue
        degree = _norm_degree(entry.get("degree"))
        institution = _norm(entry.get("institution"))
        if degree or institution:
            entries.append(
                {
                    "degree": degree,
                    "institution": institution,
                    "source": entry,
                }
            )
    return entries


def _matched_education(
    predicted: dict, gold: dict
) -> tuple[list[tuple[dict, dict]], int, int]:
    """Best one-to-one education pairs plus predicted/gold counts."""
    predicted_entries = _education_entries(predicted)
    gold_entries = _education_entries(gold)

    candidates = []
    for predicted_index, predicted_entry in enumerate(predicted_entries):
        for gold_index, gold_entry in enumerate(gold_entries):
            degree_score = _similarity(
                predicted_entry["degree"], gold_entry["degree"]
            )
            institution_score = _similarity(
                predicted_entry["institution"], gold_entry["institution"]
            )
            score = 0.45 * degree_score + 0.55 * institution_score
            if score >= _EDUCATION_MATCH_THRESHOLD:
                candidates.append((score, predicted_index, gold_index))

    matched_predicted: set[int] = set()
    matched_gold: set[int] = set()
    pairs = []
    for _, predicted_index, gold_index in sorted(candidates, reverse=True):
        if predicted_index in matched_predicted or gold_index in matched_gold:
            continue
        matched_predicted.add(predicted_index)
        matched_gold.add(gold_index)
        pairs.append(
            (
                predicted_entries[predicted_index]["source"],
                gold_entries[gold_index]["source"],
            )
        )
    return pairs, len(predicted_entries), len(gold_entries)


def _education_prf(predicted: dict, gold: dict) -> tuple[float, float, float]:
    """One-to-one education matching tolerant of degree aliases/location suffixes."""
    pairs, predicted_count, gold_count = _matched_education(predicted, gold)
    if not predicted_count and not gold_count:
        return 1.0, 1.0, 1.0
    if not predicted_count or not gold_count:
        return 0.0, 0.0, 0.0

    hits = len(pairs)
    precision = hits / predicted_count
    recall = hits / gold_count
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _education_date_accuracy(predicted: dict, gold: dict) -> tuple[float, int]:
    pairs, _, _ = _matched_education(predicted, gold)
    correct = 0
    supported = 0
    for predicted_entry, gold_entry in pairs:
        for key in ("start_year", "end_year"):
            expected = _normalise_date(gold_entry.get(key))
            if not expected:
                continue
            supported += 1
            correct += int(_date_matches(predicted_entry.get(key), expected))
    return (correct / supported if supported else 1.0), supported


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


def _flat_strings(profile: dict, section: str, key: str) -> set[str]:
    """One repeated sub-field, flattened across every entry in a section.

    Scored apart from the entity key so a wrong institution does not also sink
    the degree field, and so list-valued sub-fields (project technologies) and
    scalar ones (education field, experience location) share one path.
    """
    out: set[str] = set()
    for entry in profile.get(section) or []:
        if not isinstance(entry, dict):
            continue
        value = entry.get(key)
        if isinstance(value, list):
            out |= {_norm(v) for v in value if _norm(v)}
        elif _norm(value):
            out.add(_norm(value))
    return out


def _flat_locations(profile: dict, section: str, key: str) -> set[str]:
    """Locality-level comparison using the production privacy sanitizer."""
    out: set[str] = set()
    for entry in profile.get(section) or []:
        if not isinstance(entry, dict):
            continue
        location = locality_only(entry.get(key))
        if location:
            out.add(_norm(location))
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


def _normalise_date(value: object) -> str:
    """Canonicalise common resume date spellings without inventing precision.

    `Aug 2022`, `08/2022`, and `2022-08` become `2022-08`; a year-only value
    remains `2022`, so it does not falsely match a month-specific annotation.
    """
    text = _norm(value).strip(".,")
    if not text:
        return ""
    if text in _CURRENT:
        return "present"

    year = re.search(r"\b((?:19|20)\d{2})\b", text)
    if not year:
        return text
    year_value = year.group(1)

    for name, number in _MONTHS.items():
        if re.search(rf"\b{re.escape(name)}\b", text):
            return f"{year_value}-{number:02d}"

    numeric_month = re.fullmatch(
        r"\s*(0?[1-9]|1[0-2])\s*[-/.]\s*((?:19|20)\d{2})\s*", text
    )
    if numeric_month:
        return f"{numeric_month.group(2)}-{int(numeric_month.group(1)):02d}"

    iso_month = re.fullmatch(
        r"\s*((?:19|20)\d{2})\s*[-/.]\s*(0?[1-9]|1[0-2])\s*", text
    )
    if iso_month:
        return f"{iso_month.group(1)}-{int(iso_month.group(2)):02d}"

    if re.fullmatch(r"(?:19|20)\d{2}", text):
        return year_value
    return text


def _date_matches(predicted: object, expected: object) -> bool:
    """Compare dates at the precision supplied by the gold annotation.

    A year-only gold value deliberately accepts a more precise predicted month
    in that year. A month-specific gold value still requires the same month.
    """
    predicted_date = _normalise_date(predicted)
    expected_date = _normalise_date(expected)
    if predicted_date == expected_date:
        return True
    if re.fullmatch(r"(?:19|20)\d{2}", expected_date):
        return predicted_date.startswith(f"{expected_date}-")
    return False


def _date_accuracy(
    predicted: dict,
    gold: dict,
    section: str,
    identity_keys: tuple[str, ...],
    date_keys: tuple[str, ...],
) -> tuple[float, int]:
    """Date accuracy for gold entities also found in the prediction."""

    def indexed(profile: dict) -> dict[str, dict]:
        result = {}
        for entry in profile.get(section) or []:
            if not isinstance(entry, dict):
                continue
            identity = "|".join(_norm(entry.get(key)) for key in identity_keys)
            if identity.strip("|"):
                result[identity] = entry
        return result

    predicted_entries = indexed(predicted)
    gold_entries = indexed(gold)
    correct = 0
    supported = 0
    for identity in predicted_entries.keys() & gold_entries.keys():
        for key in date_keys:
            expected = _normalise_date(gold_entries[identity].get(key))
            if not expected:
                continue
            supported += 1
            correct += int(_date_matches(predicted_entries[identity].get(key), expected))
    return (correct / supported if supported else 1.0), supported


def field_metrics(outputs: dict, reference_outputs: dict) -> list[dict]:
    """Per-field precision/recall/F1 plus the aggregate, as LangSmith feedback."""
    predicted, gold = outputs or {}, reference_outputs or {}
    scores: list[dict] = []

    def pair(extract, *args) -> tuple[set[str], set[str]]:
        return extract(predicted, *args), extract(gold, *args)

    # Dates and free-text descriptions are deliberately absent. Dates would need
    # ISO normalisation to compare fairly ("08/2013" and "Aug 2013" are the same
    # correct reading); descriptions are human summaries the model paraphrases,
    # so any string comparison would punish correct output.
    sections = {
        "skills": pair(_strings, "skills"),
        "job_titles": pair(_strings, "job_titles"),
        "education_field": pair(_flat_strings, "education", "field"),
        "experience": pair(_entities, "experience", ("job_title", "company")),
        "experience_location": pair(_flat_locations, "experience", "location"),
        "certifications": pair(_entities, "certifications", ("name", "issuer")),
        "projects": pair(_entities, "projects", ("name",)),
        "technologies": pair(_flat_strings, "projects", "technologies"),
    }

    f1s = []
    education_precision, education_recall, education_f1 = _education_prf(
        predicted, gold
    )
    f1s.append(education_f1)
    scores += [
        {"key": "education_precision", "score": round(education_precision, 4)},
        {"key": "education_recall", "score": round(education_recall, 4)},
        {"key": "education_f1", "score": round(education_f1, 4)},
    ]
    for name, (predicted_set, gold_set) in sections.items():
        precision, recall, f1 = _prf(predicted_set, gold_set)
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

    experience_date_accuracy, experience_date_support = _date_accuracy(
        predicted,
        gold,
        "experience",
        ("job_title", "company"),
        ("start_date", "end_date"),
    )
    education_date_accuracy, education_date_support = _education_date_accuracy(
        predicted, gold
    )
    scores += [
        {
            "key": "experience_date_accuracy",
            "score": round(experience_date_accuracy, 4),
        },
        {"key": "experience_date_support", "score": experience_date_support},
        {
            "key": "education_date_accuracy",
            "score": round(education_date_accuracy, 4),
        },
        {"key": "education_date_support", "score": education_date_support},
    ]
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
