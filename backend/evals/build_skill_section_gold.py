"""Build source-grounded skill gold restricted to explicit skill-style sections.

This migration deliberately uses the historical annotations only as candidate
labels. A candidate is retained only when its meaningful tokens are visibly
grounded inside a detected skill-style section in local source-PDF OCR. Model
predictions are never read. The output is versioned and leaves gold.jsonl intact.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from evals.gold import GOLD_JSONL

OCR_DIR = Path("/tmp/resume_gold_ocr_v001")
OUTPUT = Path(__file__).resolve().parent / "data" / "gold_skill_sections_v001.jsonl"
AUDIT = Path(__file__).resolve().parent / "data" / "gold_skill_sections_v001_audit.jsonl"

SKILL_HEADING = re.compile(
    r"^(?:technical\s+|professional\s+|key\s+|core\s+|computer\s+)?"
    r"(?:skills?|competenc(?:y|ies)|expertise|qualifications?|proficiencies|"
    r"tools?(?:\s*(?:&|and)\s*technologies)?|technologies|environment|"
    r"professional\s+forte)\s*:?$",
    re.I,
)
STOP_HEADING = re.compile(
    r"^(?:professional\s+summary|summary|profile|objective|work\s+history|"
    r"professional\s+experience|work\s+experience|experience|employment|"
    r"education|projects?|certifications?|licenses?|awards?|languages?|"
    r"references?|interests?|publications?)\s*:?$",
    re.I,
)
STOPWORDS = {
    "a", "an", "and", "or", "of", "the", "to", "in", "with", "for", "on",
    "skills", "skill", "knowledge", "proficient", "proficiency", "experienced",
    "experience", "excellent", "strong", "advanced", "understanding", "using",
}

# The first visually reviewed replacement. It is kept here rather than inferred
# by the grounding heuristic because the source uses multi-column and duplicate
# skill layouts.
MANUAL = {
    "accountant__44": [
        "Advanced Bookkeeping", "Accounting and Bookkeeping",
        "Financial Statement Analysis", "Tax Return Filing", "GAAP",
        "Bank Reconciliations", "Flexible Team Player", "Microsoft Word",
        "Microsoft Excel", "Microsoft Access", "Microsoft PowerPoint",
        "Microsoft Outlook", "Banner Finance", "Xtender", "Asset Keeper Pro",
        "QuickBooks", "Fixed Asset Solutions", "Creative Solutions Bookkeeping",
        "HOST", "Document Manager", "ProSystem", "UltraTax", "Lacerte",
    ],
}


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9+#.]+", value))


def tokens(value: str) -> set[str]:
    return {token for token in clean(value).split() if token not in STOPWORDS}


def skill_sections(text: str) -> tuple[str, list[str]]:
    lines = [" ".join(line.split()).strip(" •«¢e*\t") for line in text.splitlines()]
    captured: list[str] = []
    headings: list[str] = []
    active = False
    for line in lines:
        if not line:
            continue
        if SKILL_HEADING.fullmatch(line):
            active = True
            headings.append(line)
            continue
        if active and STOP_HEADING.fullmatch(line):
            active = False
            continue
        if active:
            captured.append(line)
    return "\n".join(captured), headings


def grounded(candidate: str, section: str) -> bool:
    candidate_clean = clean(candidate)
    section_clean = clean(section)
    if candidate_clean and candidate_clean in section_clean:
        return True
    wanted = tokens(candidate)
    if not wanted:
        return False
    visible = tokens(section)
    # Require all meaningful tokens for short names and at least 80% for longer
    # canonical labels that may differ slightly from the printed phrase.
    overlap = len(wanted & visible) / len(wanted)
    return overlap == 1.0 if len(wanted) <= 3 else overlap >= 0.8


def main() -> None:
    rows: list[dict] = []
    audit: list[dict] = []
    for line in GOLD_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if not record.get("_annotated"):
            continue
        resume_id = record["id"]
        old = record.get("skills") or []
        ocr_path = OCR_DIR / f"{resume_id}.txt"
        text = ocr_path.read_text(encoding="utf-8") if ocr_path.exists() else ""
        section, headings = skill_sections(text)
        retained = MANUAL.get(
            resume_id,
            [value for value in old if isinstance(value, str) and grounded(value, section)],
        )
        retained = list(dict.fromkeys(retained))
        rows.append({"resume_id": resume_id, "skills": retained})
        audit.append({
            "resume_id": resume_id,
            "old_count": len(old),
            "new_count": len(retained),
            "removed": [value for value in old if value not in retained],
            "detected_headings": headings,
            "source": "manual_source_review" if resume_id in MANUAL else "ocr_section_grounding",
            "needs_manual_review": not headings and resume_id not in MANUAL,
        })
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    AUDIT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in audit), encoding="utf-8")
    print({
        "records": len(rows),
        "old_skills": sum(row["old_count"] for row in audit),
        "new_skills": sum(row["new_count"] for row in audit),
        "without_detected_heading": sum(row["needs_manual_review"] for row in audit),
        "output": str(OUTPUT),
    })


if __name__ == "__main__":
    main()
