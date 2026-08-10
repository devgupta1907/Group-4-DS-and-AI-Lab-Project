"""Export the untouched Milestone-2 skills as a versioned evaluation overlay."""

from __future__ import annotations

import json
from pathlib import Path

SOURCE = Path.home() / "workspace/iitm/dsai/Milestone_2_Resume_Parsing/final_dataset/gold.jsonl"
OUTPUT = Path(__file__).resolve().parent / "data" / "gold_original_skills_v001.jsonl"


def main() -> None:
    rows = []
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("_annotated"):
            rows.append({"resume_id": record["id"], "skills": record.get("skills") or []})
    OUTPUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print({"records": len(rows), "skills": sum(len(row["skills"]) for row in rows), "output": str(OUTPUT)})


if __name__ == "__main__":
    main()
