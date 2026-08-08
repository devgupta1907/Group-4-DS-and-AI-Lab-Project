"""Create report-ready tables and plots for the paired pipeline experiment."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BACKEND = Path(__file__).resolve().parents[1]
RESULTS = BACKEND / "experiments" / "results" / "pipeline_ab.jsonl"
REPORT = BACKEND / "experiments" / "reports" / "pipeline_ab"
COLORS = {"direct_vision": "#2563eb", "docling_text": "#f97316"}
LABELS = {"direct_vision": "Direct vision", "docling_text": "Docling + text"}


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def canvas(title: str, subtitle: str, height: int = 720):
    image = Image.new("RGB", (1500, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((55, 35), title, fill="#0f172a", font=font(34, True))
    draw.text((55, 82), subtitle, fill="#475569", font=font(18))
    return image, draw


def grouped_bars(
    table: pd.DataFrame,
    metrics: list[tuple[str, str]],
    output: Path,
    title: str,
    subtitle: str,
) -> None:
    image, draw = canvas(title, subtitle, 260 + len(metrics) * 120)
    left, width = 390, 940
    for row, (metric, label) in enumerate(metrics):
        y = 150 + row * 120
        draw.text((55, y + 28), label, fill="#1e293b", font=font(19, True))
        for index, strategy in enumerate(("direct_vision", "docling_text")):
            value = float(table.loc[strategy, metric])
            bar_y = y + index * 42
            draw.rounded_rectangle(
                (left, bar_y, left + width * max(0, value), bar_y + 30),
                radius=5,
                fill=COLORS[strategy],
            )
            draw.text(
                (left + width * max(0, value) + 12, bar_y + 3),
                f"{value:.3f}",
                fill="#0f172a",
                font=font(17, True),
            )
    for index, strategy in enumerate(("direct_vision", "docling_text")):
        x = 920 + index * 245
        draw.rectangle((x, 70, x + 25, 95), fill=COLORS[strategy])
        draw.text((x + 35, 70), LABELS[strategy], fill="#334155", font=font(16))
    image.save(output, optimize=True)


def latency_plot(summary: pd.DataFrame, output: Path) -> None:
    image, draw = canvas(
        "Gemma 4: end-to-end latency by input strategy",
        "Mean time across evaluated resumes; lower is better",
        610,
    )
    maximum = summary["total_seconds"].max() * 1.12
    left, width = 300, 1050
    for index, strategy in enumerate(("direct_vision", "docling_text")):
        y = 185 + index * 155
        preprocess = float(summary.loc[strategy, "preprocess_seconds"])
        model = float(summary.loc[strategy, "model_seconds"])
        total = float(summary.loc[strategy, "total_seconds"])
        draw.text((55, y + 15), LABELS[strategy], fill="#172554", font=font(20, True))
        pre_width = width * preprocess / maximum
        model_width = width * model / maximum
        draw.rounded_rectangle(
            (left, y, left + pre_width, y + 58), radius=6, fill="#94a3b8"
        )
        draw.rectangle(
            (left + pre_width, y, left + pre_width + model_width, y + 58),
            fill=COLORS[strategy],
        )
        draw.text(
            (left + pre_width + model_width + 14, y + 16),
            f"{total:.1f}s total",
            fill="#0f172a",
            font=font(19, True),
        )
        draw.text(
            (left, y + 70),
            f"Preprocess {preprocess:.1f}s  |  Model {model:.1f}s",
            fill="#475569",
            font=font(16),
        )
    draw.rectangle((55, 500, 80, 525), fill="#94a3b8")
    draw.text((90, 500), "Preprocessing", fill="#334155", font=font(16))
    draw.rectangle((260, 500, 285, 525), fill="#2563eb")
    draw.text((295, 500), "Model inference", fill="#334155", font=font(16))
    image.save(output, optimize=True)


def paired_plot(detail: pd.DataFrame, output: Path) -> None:
    pivot = detail.pivot(index="resume_id", columns="strategy", values="profile_f1_macro")
    image, draw = canvas(
        "Gemma 4: direct vision vs Docling macro F1",
        "Each line compares the same resume under both input strategies",
        760,
    )
    left, right = 430, 1260
    draw.line((left, 145, left, 650), fill="#cbd5e1", width=3)
    draw.line((right, 145, right, 650), fill="#cbd5e1", width=3)
    draw.text((left - 65, 112), "Direct", fill="#1d4ed8", font=font(18, True))
    draw.text((right - 70, 112), "Docling", fill="#c2410c", font=font(18, True))
    for index, (resume_id, row) in enumerate(pivot.iterrows()):
        y = 180 + index * 92
        direct = float(row["direct_vision"])
        docling = float(row["docling_text"])
        direct_y = y + (1 - direct) * 58
        docling_y = y + (1 - docling) * 58
        draw.text((45, y + 15), resume_id[:34], fill="#334155", font=font(15))
        draw.line((left, direct_y, right, docling_y), fill="#94a3b8", width=4)
        draw.ellipse((left - 9, direct_y - 9, left + 9, direct_y + 9), fill="#2563eb")
        draw.ellipse((right - 9, docling_y - 9, right + 9, docling_y + 9), fill="#f97316")
        draw.text((left + 18, direct_y - 12), f"{direct:.3f}", fill="#1e40af", font=font(15))
        draw.text((right + 18, docling_y - 12), f"{docling:.3f}", fill="#9a3412", font=font(15))
    image.save(output, optimize=True)


def weighted_date_summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strategy, frame in detail.groupby("strategy"):
        row = {"strategy": strategy}
        for prefix in ("experience_date", "education_date"):
            support = frame[f"{prefix}_support"].sum()
            weighted = (
                frame[f"{prefix}_accuracy"] * frame[f"{prefix}_support"]
            ).sum()
            row[f"{prefix}_accuracy"] = weighted / support if support else 0.0
            row[f"{prefix}_support"] = int(support)
        rows.append(row)
    return pd.DataFrame(rows).set_index("strategy")


def main() -> None:
    if not RESULTS.exists():
        raise SystemExit(f"No experiment results at {RESULTS}")
    REPORT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in RESULTS.read_text().splitlines() if line.strip()]
    detail = pd.DataFrame(rows)
    detail = detail[detail["success"] == True]  # noqa: E712
    detail = detail.drop_duplicates(["resume_id", "strategy"], keep="last")
    required = {"direct_vision", "docling_text"}
    if set(detail["strategy"]) != required:
        raise SystemExit("At least one successful run for each strategy is required")

    complete_ids = (
        detail.groupby("resume_id")["strategy"]
        .agg(lambda values: set(values) == required)
    )
    paired = detail[detail["resume_id"].isin(complete_ids[complete_ids].index)]
    if paired.empty:
        raise SystemExit("At least one complete direct-vision/Docling pair is required")

    numeric = detail.select_dtypes("number").columns
    summary = detail.groupby("strategy")[numeric].mean()
    dates = weighted_date_summary(detail)
    summary = summary.drop(
        columns=[column for column in dates.columns if column in summary],
        errors="ignore",
    ).join(dates)

    detail.to_csv(REPORT / "per_resume_metrics.csv", index=False)
    summary.to_csv(REPORT / "summary.csv")

    grouped_bars(
        summary,
        [
            ("profile_f1_macro", "Profile macro F1"),
            ("schema_valid", "Schema-valid rate"),
            ("coverage", "Profile coverage"),
            ("pii_clean", "PII-clean rate"),
        ],
        REPORT / "overall_quality.png",
        "Overall extraction quality",
        "Successful human-annotated runs; higher is better",
    )
    grouped_bars(
        summary,
        [
            ("skills_f1", "Skills F1"),
            ("job_titles_f1", "Job titles F1"),
            ("education_f1", "Education F1"),
            ("experience_f1", "Experience F1"),
            ("certifications_f1", "Certifications F1"),
            ("projects_f1", "Projects F1"),
            ("technologies_f1", "Technologies F1"),
        ],
        REPORT / "field_f1.png",
        "Field-level F1",
        "Entity matching is case- and whitespace-insensitive",
    )
    grouped_bars(
        summary,
        [
            ("experience_date_accuracy", "Experience date accuracy"),
            ("education_date_accuracy", "Education date accuracy"),
        ],
        REPORT / "date_accuracy.png",
        "Date extraction after format normalization",
        "Month names, MM/YYYY and YYYY-MM are treated as equivalent",
    )
    latency_plot(summary, REPORT / "latency_breakdown.png")
    paired_plot(paired, REPORT / "paired_macro_f1.png")

    pivot = paired.pivot(index="resume_id", columns="strategy", values="profile_f1_macro")
    pivot["docling_minus_direct"] = pivot["docling_text"] - pivot["direct_vision"]
    pivot.sort_values("docling_minus_direct").to_csv(REPORT / "paired_differences.csv")

    print(summary.to_string())
    print(f"Wrote report artifacts to {REPORT}")


if __name__ == "__main__":
    main()
