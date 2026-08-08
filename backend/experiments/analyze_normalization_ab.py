"""Compare strict saved scores with normalized rescoring and an optional rerun."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.metrics import field_metrics  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
STRICT_RESULTS = BACKEND / "experiments/results/pipeline_ab_gemini35.jsonl"
RAW_RESULTS = BACKEND / "experiments/runs/pipeline_ab_gemini35_raw.jsonl"
REPORT = BACKEND / "experiments/reports/normalization_ab"


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(name, size)


def chart(frame: pd.DataFrame, metric: str, title: str, output: Path) -> None:
    values = frame.set_index("experiment")[metric]
    canvas = Image.new("RGB", (1100, 620), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((55, 35), title, fill="#0f172a", font=font(34, True))
    colors = ["#64748b", "#2563eb"]
    for index, (label, value) in enumerate(values.items()):
        left = 90 + index * 330
        top = 500 - float(value) * 360
        draw.rounded_rectangle((left, top, left + 210, 500), 10, fill=colors[index])
        draw.text((left + 45, top - 45), f"{value:.3f}", fill="#0f172a", font=font(28, True))
        draw.multiline_text(
            (left, 525),
            label.replace(" ", "\n"),
            fill="#334155",
            font=font(19),
            align="center",
        )
    draw.line((70, 500, 1030, 500), fill="#94a3b8", width=3)
    canvas.save(output)


def field_chart(frame: pd.DataFrame, output: Path) -> None:
    metrics = [
        ("profile_f1_macro", "Macro"),
        ("education_f1", "Education"),
        ("skills_f1", "Skills"),
        ("job_titles_f1", "Job titles"),
        ("experience_f1", "Experience"),
        ("projects_f1", "Projects"),
    ]
    colors = ["#64748b", "#2563eb"]
    canvas = Image.new("RGB", (1500, 760), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (55, 35),
        "Field-level comparison: strict vs normalized scoring",
        fill="#0f172a",
        font=font(34, True),
    )
    baseline_y = 620
    group_width = 220
    bar_width = 48
    for metric_index, (metric, label) in enumerate(metrics):
        group_left = 80 + metric_index * group_width
        for experiment_index, row in frame.iterrows():
            value = float(row[metric])
            left = group_left + experiment_index * (bar_width + 8)
            top = baseline_y - value * 430
            draw.rectangle(
                (left, top, left + bar_width, baseline_y),
                fill=colors[experiment_index],
            )
        draw.text(
            (group_left, baseline_y + 18),
            label,
            fill="#334155",
            font=font(18),
        )
    draw.line((60, baseline_y, 1450, baseline_y), fill="#94a3b8", width=3)
    for index, row in frame.iterrows():
        left = 920 + index * 185
        draw.rectangle((left, 90, left + 25, 115), fill=colors[index])
        draw.text(
            (left + 35, 88),
            str(row["experiment"]),
            fill="#334155",
            font=font(16),
        )
    canvas.save(output)


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    strict = pd.DataFrame(
        row
        for row in rows(STRICT_RESULTS)
        if row.get("success") and row.get("strategy") == "direct_vision"
    ).drop_duplicates("resume_id", keep="last")

    normalized_rows = []
    for row in rows(RAW_RESULTS):
        if row.get("strategy") != "direct_vision":
            continue
        scores = {
            score["key"]: score["score"]
            for score in field_metrics(row["profile"], row["reference"])
        }
        normalized_rows.append({"resume_id": row["resume_id"], **scores})
    normalized = pd.DataFrame(normalized_rows).drop_duplicates("resume_id", keep="last")

    metrics = [
        "profile_f1_macro",
        "education_f1",
        "skills_f1",
        "job_titles_f1",
        "experience_f1",
        "projects_f1",
    ]
    summary_rows = [
        {
            "experiment": "Strict original",
            "successful_resumes": len(strict),
            **{metric: strict[metric].mean() for metric in metrics},
        },
        {
            "experiment": "Normalized rescore",
            "successful_resumes": len(normalized),
            **{metric: normalized[metric].mean() for metric in metrics},
        },
    ]
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(REPORT / "summary.csv", index=False)

    paired = strict[["resume_id", "profile_f1_macro", "education_f1"]].merge(
        normalized[["resume_id", "profile_f1_macro", "education_f1"]],
        on="resume_id",
        suffixes=("_strict", "_normalized"),
    )
    paired.to_csv(REPORT / "per_resume_comparison.csv", index=False)
    chart(
        summary,
        "profile_f1_macro",
        "Macro profile F1: scoring normalization",
        REPORT / "macro_f1.png",
    )
    chart(
        summary,
        "education_f1",
        "Education F1: scoring normalization",
        REPORT / "education_f1.png",
    )
    field_chart(summary, REPORT / "field_comparison.png")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
