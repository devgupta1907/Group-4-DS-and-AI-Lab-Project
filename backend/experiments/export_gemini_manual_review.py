"""Export the current reviewed Gemini prompt from the append-only ledger."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from evals import gold

LEDGER = BACKEND / "experiments" / "runs" / "vertex_vision_raw_baseline" / "attempts.jsonl"
OUTPUT = BACKEND / "experiments" / "runs" / "vertex_vision_raw_baseline" / "manual_review"
MODEL = "gemini-3.5-flash"
PROMPT_VERSION = "v010_strict_visual_skill_section"
REVIEWED = BACKEND / "evals" / "data" / "gold_manual_review_ids_v001.json"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-reviewed", action="store_true",
        help="Export reviewed resumes too; useful for checking that saved output is unchanged.",
    )
    parser.add_argument(
        "--resume-id", action="append", default=[],
        help="Export only this resume ID; repeat the option for multiple resumes.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=OUTPUT,
        help="Destination directory (defaults to the standard manual-review folder).",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    reviewed = set()
    if not args.include_reviewed and REVIEWED.exists():
        manifest = json.loads(REVIEWED.read_text(encoding="utf-8"))
        reviewed = set(manifest["reviewed_resume_ids"])
    examples_by_id = {example.resume_id: example for example in gold.load(None)}
    pdf_by_id = {resume_id: example.pdf_path for resume_id, example in examples_by_id.items()}
    latest = {}
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (
            row.get("status") == "success"
            and row.get("model") == MODEL
            and row.get("prompt_version") == PROMPT_VERSION
            and not row.get("evaluation_type")
            and row.get("resume_id") not in reviewed
            and (not args.resume_id or row.get("resume_id") in args.resume_id)
        ):
            latest[row["resume_id"]] = row
    output.mkdir(parents=True, exist_ok=True)
    index = []
    metadata_fields = (
        "record_id", "resume_id", "timestamp_utc", "experiment_key", "model",
        "prompt_version", "evaluation_mode", "resume_total_seconds",
        "model_wall_seconds", "page_count", "attempt", "prompt_tokens",
        "output_tokens", "thinking_tokens", "total_tokens", "cached_input_tokens",
        "estimated_cost_usd", "pricing_version", "raw_schema_valid",
        "raw_schema_errors",
    )
    for resume_id, row in sorted(latest.items()):
        folder = output / resume_id
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_by_id[resume_id], folder / "source.pdf")
        gold_review_path = folder / "gold_to_review.json"
        if not gold_review_path.exists():
            write_json(gold_review_path, examples_by_id[resume_id].profile)
        prediction = row.get("raw_prediction") or row.get("prediction") or {}
        write_json(folder / "predicted.json", prediction)
        metadata = {field: row.get(field) for field in metadata_fields}
        index.append(metadata)
    print({"resumes": len(index), "output": str(output)})


if __name__ == "__main__":
    main()
