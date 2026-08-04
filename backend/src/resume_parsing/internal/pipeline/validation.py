"""Stage 5 — the hard gate before anything is persisted.

Two independent checks:

**Schema validation** is a pass/fail contract. Because the schema sets
`additionalProperties: false`, a model that transcribes an email address or a
phone number produces an *invalid* profile and is rejected here — the privacy
rule is enforced by the validator, not by hoping the prompt held.

**Completeness** is a heuristic, not a contract. A fresher legitimately has no
experience and most resumes have no projects, so absence is a valid state. Low
coverage only decides whether the repair path is worth running.
"""

from __future__ import annotations

from jsonschema import Draft7Validator

from src.resume_parsing.internal.domain import ValidationReport
from src.resume_parsing.internal.prompts import load_schema

# Weighted because a profile without skills is far more suspect than one
# without certifications. Weights sum to 1.0.
_COVERAGE_WEIGHTS: dict[str, float] = {
    "contact.name": 0.20,
    "skills": 0.30,
    "education": 0.20,
    "experience": 0.20,
    "job_titles": 0.10,
}

# Populated-if-present sections that are flagged for the user to check rather
# than treated as failures.
_REVIEWABLE = ("contact.name", "contact.location", "skills", "education", "experience")


def validate(payload: dict) -> ValidationReport:
    report = ValidationReport()
    validator = Draft7Validator(load_schema())

    for error in sorted(validator.iter_errors(payload), key=str):
        location = ".".join(str(p) for p in error.absolute_path) or "<root>"
        report.schema_errors.append(f"{location}: {error.message}")

    report.coverage = _coverage(payload)
    report.needs_review = [field for field in _REVIEWABLE if not _present(payload, field)]
    return report


def _coverage(payload: dict) -> float:
    return round(
        sum(weight for field, weight in _COVERAGE_WEIGHTS.items() if _present(payload, field)),
        4,
    )


def _present(payload: dict, path: str) -> bool:
    node: object = payload
    for part in path.split("."):
        if not isinstance(node, dict):
            return False
        node = node.get(part)
    if node is None:
        return False
    if isinstance(node, str):
        return bool(node.strip())
    if isinstance(node, list):
        return len(node) > 0
    return True
