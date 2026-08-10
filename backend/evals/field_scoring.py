"""Per-field TP/FP/FN evidence shared by evaluation notebooks and scripts."""

from __future__ import annotations

import json
from typing import Any, Literal

from evals.normalization import (
    date_matches,
    normalize_company,
    normalize_field_value,
    normalize_field_values,
    normalize_text,
)

ScoringMode = Literal["exact", "normalized"]

FIELD_SPECS: dict[str, tuple[str, ...]] = {
    "contact.name": ("scalar", "contact", "name"),
    "contact.location": ("scalar", "contact", "location"),
    "skills": ("list", "skills"),
    "education.degree": ("nested", "education", "degree"),
    "education.field": ("nested", "education", "field"),
    "education.institution": ("nested", "education", "institution"),
    "education.start_year": ("nested", "education", "start_year"),
    "education.end_year": ("nested", "education", "end_year"),
    "experience.job_title": ("nested", "experience", "job_title"),
    "experience.company": ("nested", "experience", "company"),
    "experience.location": ("nested", "experience", "location"),
    "experience.start_date": ("nested", "experience", "start_date"),
    "experience.end_date": ("nested", "experience", "end_date"),
    "experience.current_role": ("nested", "experience", "current_role"),
    "projects.name": ("nested", "projects", "name"),
    "projects.technologies": ("nested", "projects", "technologies"),
    "certifications.name": ("nested", "certifications", "name"),
    "certifications.issuer": ("nested", "certifications", "issuer"),
    "certifications.year": ("nested", "certifications", "year"),
}


def comparison_value(field: str, value: Any, *, mode: ScoringMode) -> str:
    if value is None or value == "":
        return ""
    if mode == "normalized":
        return normalize_field_value(field, value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def comparison_values(field: str, value: Any, *, mode: ScoringMode) -> set[str]:
    if mode == "normalized" and field == "skills":
        # Keep each approved source line intact in the auditable TP/FP/FN table.
        # Tolerant phrase/alias matching is reported separately by the hybrid
        # skills scorer; atomizing here would hide the actual reviewed gold.
        comparable = normalize_text(value)
        return {comparable} if comparable else set()
    if mode == "normalized":
        return normalize_field_values(field, value)
    comparable = comparison_value(field, value, mode=mode)
    return {comparable} if comparable else set()


def values_for(
    profile: dict, field: str, spec: tuple[str, ...], *, mode: ScoringMode
) -> set[str]:
    kind, *path = spec
    if kind == "scalar":
        value = (profile.get(path[0]) or {}).get(path[1])
        return comparison_values(field, value, mode=mode)
    if kind == "list":
        node: Any = profile
        for key in path:
            node = (node or {}).get(key) if isinstance(node, dict) else []
        values: set[str] = set()
        for value in node or []:
            values |= comparison_values(field, value, mode=mode)
        return values
    section, key = path
    values: set[str] = set()
    for entry in profile.get(section) or []:
        if not isinstance(entry, dict):
            continue
        value = entry.get(key)
        raw_values = value if isinstance(value, list) else [value]
        for raw in raw_values:
            if mode == "normalized" and field == "experience.company":
                comparable = normalize_company(raw, location=entry.get("location"))
                if comparable:
                    values.add(comparable)
            else:
                values |= comparison_values(field, raw, mode=mode)
    return values


def confusion_rows(
    prediction: dict, reference: dict, *, mode: ScoringMode = "exact"
) -> list[dict]:
    """Return auditable item and presence confusion counts for every field."""
    rows = []
    for field, spec in FIELD_SPECS.items():
        predicted = values_for(prediction, field, spec, mode=mode)
        expected = values_for(reference, field, spec, mode=mode)
        exact_matches = predicted & expected
        matched_pairs = [(value, value) for value in sorted(exact_matches)]
        unmatched_predicted = predicted - exact_matches
        unmatched_expected = expected - exact_matches
        leaf_field = field.rsplit(".", 1)[-1]
        if mode == "normalized" and leaf_field.endswith(("date", "year")):
            # Gold annotations sometimes intentionally contain only a year.  A model
            # output with the same year plus a month is correct at gold precision.
            for predicted_value in sorted(unmatched_predicted):
                match = next(
                    (
                        expected_value
                        for expected_value in sorted(unmatched_expected)
                        if date_matches(predicted_value, expected_value)
                    ),
                    None,
                )
                if match is not None:
                    matched_pairs.append((predicted_value, match))
                    unmatched_expected.remove(match)
            matched_predicted = {pair[0] for pair in matched_pairs}
        else:
            matched_predicted = exact_matches
        tp_values = sorted(matched_predicted)
        fp_values = sorted(predicted - matched_predicted)
        fn_values = sorted(unmatched_expected)
        rows.append({
            "field": field,
            "tp": len(tp_values), "fp": len(fp_values), "fn": len(fn_values),
            "predicted_values": sorted(predicted), "gold_values": sorted(expected),
            "tp_values": tp_values, "fp_values": fp_values, "fn_values": fn_values,
            "matched_value_pairs": [
                {"predicted": predicted_value, "gold": gold_value}
                for predicted_value, gold_value in matched_pairs
            ],
            "presence_tp": int(bool(predicted) and bool(expected)),
            "presence_fp": int(bool(predicted) and not expected),
            "presence_fn": int(not predicted and bool(expected)),
            "presence_tn": int(not predicted and not expected),
            "predicted_count": len(predicted), "gold_count": len(expected),
        })
    return rows
