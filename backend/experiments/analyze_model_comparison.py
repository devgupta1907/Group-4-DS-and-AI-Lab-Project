"""Build Gemini 3.5 reports and compare it with Gemma 4 on prompt v002.

Run from backend after both experiment result files exist:
    .venv/bin/python experiments/analyze_model_comparison.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RUNS = ROOT / "runs"
GEMINI_REPORT = ROOT / "reports" / "gemini35_verbatim"
COMPARISON_REPORT = ROOT / "reports" / "model_comparison"
TECH_LABELS = {
    "sap_developer__Image_100": "SAP",
    "network_security_engineer__3271dd46520c65b9": "Network Security",
    "sql_developer__0b8431fc6fb166a7": "SQL",
    "python_developer__67": "Python",
    "data_science__Image_50": "Data Science",
}


def latest_pairs(path: Path, version: str = "v002") -> pd.DataFrame:
    frame = pd.read_json(path, lines=True)
    frame = frame[(frame["success"]) & (frame["prompt_version"] == version)]
    return frame.groupby("resume_id", as_index=False, sort=False).tail(1)


def chart(
    labels: list[str],
    values: list[float],
    *,
    title: str,
    subtitle: str,
    path: Path,
    percent: bool = False,
) -> None:
    width, height = 1400, 180 + len(labels) * 65
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default(size=24)
    font = ImageFont.load_default(size=19)
    draw.text((35, 25), title, fill="#17202a", font=title_font)
    draw.text((35, 65), subtitle, fill="#475569", font=font)
    maximum = max(values) or 1
    colors = ("#64748b", "#2563eb", "#0891b2", "#7c3aed", "#059669")
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        y = 115 + index * 65
        draw.text((35, y + 8), label, fill="#334155", font=font)
        bar_width = int(920 * value / maximum)
        draw.rounded_rectangle(
            (260, y, 260 + bar_width, y + 36),
            radius=5,
            fill=colors[index % len(colors)],
        )
        rendered = f"{value * 100:.1f}%" if percent else f"{value:.1f} s"
        draw.text((275 + bar_width, y + 7), rendered, fill="#17202a", font=font)
    image.save(path, "PNG", optimize=True)


def sanitized_sample(raw_path: Path) -> dict:
    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    chosen = None
    for row in rows:
        if (
            row["status"] == "success"
            and "resume_id=sql_developer__0b8431fc6fb166a7" in row.get("notes", "")
        ):
            chosen = row
    if chosen is None:
        raise RuntimeError("No successful SQL Developer Gemini run found")
    profile = copy.deepcopy(chosen["output"])
    contact = profile.get("contact") or {}
    for key in ("name", "location"):
        if contact.get(key) is not None:
            contact[key] = "[REDACTED]"
    contact["links"] = []
    for entry in profile.get("education") or []:
        for key in ("institution", "start_year", "end_year"):
            if entry.get(key) is not None:
                entry[key] = "[REDACTED]"
    for entry in profile.get("experience") or []:
        for key in ("company", "location", "start_date", "end_date"):
            if entry.get(key) is not None:
                entry[key] = "[REDACTED]"
    for entry in profile.get("certifications") or []:
        if entry.get("issuer") is not None:
            entry["issuer"] = "[REDACTED]"
    return {
        "_experiment": {
            "model": chosen["model"],
            "prompt_version": chosen["prompt_version"],
            "resume_id": "sql_developer__0b8431fc6fb166a7",
            "privacy": "Direct identifiers and identifying dates were redacted for the report.",
        },
        "parsed_resume": profile,
    }


def main() -> None:
    GEMINI_REPORT.mkdir(parents=True, exist_ok=True)
    COMPARISON_REPORT.mkdir(parents=True, exist_ok=True)
    gemma = latest_pairs(RESULTS / "description_copy_ab.jsonl")
    gemini = latest_pairs(RESULTS / "gemini35_verbatim.jsonl")
    gemini = gemini.assign(
        resume_label=gemini["resume_id"].map(TECH_LABELS),
        latency_seconds=gemini["latency_ms"] / 1000,
    )
    gemini.to_csv(GEMINI_REPORT / "per_resume_metrics.csv", index=False)

    chart(
        gemini["resume_label"].tolist(),
        gemini["latency_seconds"].tolist(),
        title="Gemini 3.5 Flash Latency by Resume",
        subtitle="Improved verbatim prompt; lower is better.",
        path=GEMINI_REPORT / "latency_by_resume.png",
    )
    scored = gemini.dropna(subset=["verbatim_rate"])
    chart(
        scored["resume_label"].tolist(),
        scored["verbatim_rate"].tolist(),
        title="Gemini 3.5 Flash Exact Description Copy Rate",
        subtitle="Percentage of extracted descriptions found word-for-word in the resume.",
        path=GEMINI_REPORT / "exact_copy_rate_by_resume.png",
        percent=True,
    )

    models = ["Gemma 4 31B", "Gemini 3.5 Flash"]
    latency = [gemma["latency_ms"].mean() / 1000, gemini["latency_seconds"].mean()]
    copy_scores = [
        gemma["verbatim_rate"].dropna().mean(),
        gemini["verbatim_rate"].dropna().mean(),
    ]
    chart(
        models,
        latency,
        title="Average Latency - Improved Verbatim Prompt",
        subtitle="Same five technology resumes; lower is better.",
        path=COMPARISON_REPORT / "average_latency.png",
    )
    chart(
        models,
        copy_scores,
        title="Exact Description Copy Rate - Improved Verbatim Prompt",
        subtitle="Calculated when the model returned a description; higher is better.",
        path=COMPARISON_REPORT / "exact_copy_rate.png",
        percent=True,
    )

    summary = pd.DataFrame(
        {
            "model": models,
            "resumes": [len(gemma), len(gemini)],
            "successful_runs": [int(gemma["success"].sum()), int(gemini["success"].sum())],
            "average_latency_seconds": latency,
            "exact_copy_rate": copy_scores,
            "resumes_with_descriptions": [
                int(gemma["verbatim_rate"].notna().sum()),
                int(gemini["verbatim_rate"].notna().sum()),
            ],
        }
    )
    summary.to_csv(COMPARISON_REPORT / "summary.csv", index=False)
    sample = sanitized_sample(RUNS / "gemini35_verbatim_raw.jsonl")
    (GEMINI_REPORT / "sample_extracted_resume.json").write_text(
        json.dumps(sample, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"Wrote Gemini reports to {GEMINI_REPORT}")
    print(f"Wrote comparison reports to {COMPARISON_REPORT}")


if __name__ == "__main__":
    main()
