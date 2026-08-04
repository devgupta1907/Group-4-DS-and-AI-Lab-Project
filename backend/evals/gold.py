"""Load the Milestone-2 gold set and reshape it into the production contract.

The gold records were annotated before `parsed_resume_schema.json` settled, so
three field names differ. Reconciling them here — rather than loosening the
schema — keeps the production contract untouched and makes the mismatch a
single, reviewable function.

    gold                    schema
    ----------------------  ----------------------
    experience[].title      experience[].job_title
    experience[].is_current experience[].current_role
    projects[].tech         projects[].technologies

Annotation bookkeeping (`id`, `category`, `eval_split`, `pdf`, `_annotated`) is
metadata about the example, not part of the profile, so it travels as dataset
inputs and never as reference output.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

GOLD_DIR = Path(
    os.getenv(
        "RESUME_GOLD_DIR",
        Path.home() / "workspace/iitm/dsai/Milestone_2_Resume_Parsing/final_dataset",
    )
)
GOLD_JSONL = GOLD_DIR / "gold.jsonl"


@dataclass(frozen=True, slots=True)
class GoldExample:
    resume_id: str
    category: str
    split: str
    pdf_path: Path
    profile: dict

    @property
    def inputs(self) -> dict:
        return {
            "resume_id": self.resume_id,
            "category": self.category,
            "pdf": str(self.pdf_path.relative_to(GOLD_DIR)),
        }


def load(split: str | None = "dev") -> list[GoldExample]:
    """Annotated gold records for one split, or all splits when `split` is None."""
    if not GOLD_JSONL.exists():
        raise FileNotFoundError(
            f"Gold set not found at {GOLD_JSONL}. Set RESUME_GOLD_DIR to the "
            "directory holding gold.jsonl and gold/."
        )

    examples = []
    for line in GOLD_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if not record.get("_annotated"):
            continue
        if split is not None and record.get("eval_split") != split:
            continue
        examples.append(
            GoldExample(
                resume_id=record["id"],
                category=record["category"],
                split=record["eval_split"],
                pdf_path=GOLD_DIR / record["pdf"],
                profile=to_profile(record),
            )
        )
    return sorted(examples, key=lambda e: e.resume_id)


def to_profile(record: dict) -> dict:
    """One gold record, reshaped into a `parsed_resume_schema.json` object."""
    contact = record.get("contact") or {}
    return {
        "contact": {
            "name": contact.get("name"),
            "location": contact.get("location"),
            "links": list(contact.get("links") or []),
        },
        "skills": list(record.get("skills") or []),
        "education": [
            {
                key: entry.get(key)
                for key in ("degree", "field", "institution", "start_year", "end_year")
            }
            for entry in record.get("education") or []
        ],
        "experience": [
            {
                "job_title": entry.get("title"),
                "company": entry.get("company"),
                "location": entry.get("location"),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "current_role": entry.get("is_current"),
                "description": entry.get("description"),
            }
            for entry in record.get("experience") or []
        ],
        "projects": [
            {
                "name": entry.get("name"),
                "description": entry.get("description"),
                "technologies": list(entry.get("tech") or []),
            }
            for entry in record.get("projects") or []
        ],
        "certifications": [
            {key: entry.get(key) for key in ("name", "issuer", "year")}
            for entry in record.get("certifications") or []
        ],
        "job_titles": list(record.get("job_titles") or []),
    }


EMPTY_PROFILE: dict = {
    "contact": {"name": None, "location": None, "links": []},
    "skills": [],
    "education": [],
    "experience": [],
    "projects": [],
    "certifications": [],
    "job_titles": [],
}
