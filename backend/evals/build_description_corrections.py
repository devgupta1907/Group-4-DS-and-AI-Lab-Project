"""Build the versioned description correction layer from locally OCRed PDFs.

This script never calls a model. The saved v004 descriptions are treated only
as transcription candidates and are accepted when ordered token sequences are
grounded in OCR from the source PDF. Low-identity exceptions require an explicit
manual allow-list; positional shifts are never accepted automatically.
"""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from evals.description_scoring import _identity_score

_V004_MARKER = ":v004_source_faithful_skills:"
_MINIMUM_GROUNDING = 0.75
_MINIMUM_EXPANSION = 1.20
_REVIEWED_LOW_IDENTITY = {
    ("apparel__7a80b86cefdc1314", 0),
    ("apparel__7a80b86cefdc1314", 1),
    ("database__129", 0),
    ("digital_media__70", 0),
    ("digital_media__70", 1),
    ("health_fitness__557ea37d99744e6c", 1),
}


def _tokens(value: object) -> list[str]:
    return re.findall(r"[a-z0-9+#.]+", str(value or "").casefold())


def _grounding(candidate: str, source_ocr: str) -> float:
    candidate_tokens = _tokens(candidate)
    blocks = SequenceMatcher(
        None, candidate_tokens, _tokens(source_ocr), autojunk=False
    ).get_matching_blocks()
    grounded = sum(block.size for block in blocks if block.size >= 3)
    return grounded / len(candidate_tokens) if candidate_tokens else 0.0


def build(ledger_path: Path, ocr_dir: Path) -> list[dict]:
    attempts = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    experiment_key = next(
        row["experiment_key"]
        for row in attempts
        if row.get("status") == "success"
        and _V004_MARKER in row.get("experiment_key", "")
        and ":offline_normalization=" not in row.get("experiment_key", "")
    )
    records = {
        row["resume_id"]: row
        for row in attempts
        if row.get("status") == "success"
        and row.get("experiment_key") == experiment_key
    }
    corrections = []
    for resume_id, record in sorted(records.items()):
        source_ocr = (ocr_dir / f"{resume_id}.txt").read_text(encoding="utf-8")
        predicted = (record.get("prediction") or {}).get("experience") or []
        expected = (record.get("reference") or {}).get("experience") or []
        for index, gold_entry in enumerate(expected):
            if index >= len(predicted) or not isinstance(predicted[index], dict):
                continue
            predicted_entry = predicted[index]
            candidate = predicted_entry.get("description")
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            old = gold_entry.get("description")
            old_tokens = _tokens(old)
            expansion = len(_tokens(candidate)) / max(1, len(old_tokens))
            grounding = _grounding(candidate, source_ocr)
            identity = _identity_score(predicted_entry, gold_entry)
            explicitly_reviewed = (resume_id, index) in _REVIEWED_LOW_IDENTITY
            if grounding < _MINIMUM_GROUNDING:
                continue
            if old_tokens and expansion < _MINIMUM_EXPANSION:
                continue
            if identity < 4 and not explicitly_reviewed:
                continue
            corrections.append({
                "resume_id": resume_id,
                "experience_index": index,
                "old_description": old,
                "corrected_description": candidate.strip(),
                "verification": "source_pdf_local_ocr_ordered_token_grounding",
                "grounding_score": round(grounding, 4),
                "identity_match_score": identity,
                "low_identity_manually_reviewed": explicitly_reviewed,
            })
    return corrections


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--ocr-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corrections = build(args.ledger, args.ocr_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in corrections:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Wrote {len(corrections)} corrections to {args.output}")


if __name__ == "__main__":
    main()
