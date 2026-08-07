"""Score the description-copy A/B test and create separate SVG plots."""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from math import sqrt
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "runs" / "description_copy_ab_raw.jsonl"
SAFE = ROOT / "results" / "description_copy_ab.jsonl"
REPORTS = ROOT / "reports" / "gemma4_prompt_ab"
GOLD = (
    ROOT.parents[2]
    / "Milestone_2_Resume_Parsing"
    / "final_dataset"
    / "gold.jsonl"
)
TOKEN = re.compile(r"[a-z0-9+#.]+")


def words(text: str | None) -> list[str]:
    return TOKEN.findall((text or "").casefold())


def cosine(left: list[str], right: list[str]) -> float:
    a, b = Counter(left), Counter(right)
    denominator = sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
    return sum(value * b[token] for token, value in a.items()) / denominator if denominator else 0


def token_f1(left: list[str], right: list[str]) -> float:
    a, b = Counter(left), Counter(right)
    hits = sum((a & b).values())
    if not a or not b:
        return 0
    precision, recall = hits / sum(a.values()), hits / sum(b.values())
    return 2 * precision * recall / (precision + recall) if precision + recall else 0


def best_window(prediction: str, source: str) -> tuple[float, float]:
    """Best local source match, avoiding dilution by the whole resume."""
    target, corpus = words(prediction), words(source)
    if not target or not corpus:
        return 0, 0
    sizes = {
        max(1, round(len(target) * factor))
        for factor in (0.75, 1.0, 1.25)
    }
    best_cosine = best_f1 = 0.0
    for size in sizes:
        step = max(1, size // 8)
        for start in range(0, max(1, len(corpus) - size + 1), step):
            window = corpus[start : start + size]
            best_cosine = max(best_cosine, cosine(target, window))
            best_f1 = max(best_f1, token_f1(target, window))
    return best_cosine, best_f1


def descriptions(profile: dict) -> list[str]:
    return [
        item["description"]
        for section in ("experience", "projects")
        for item in profile.get(section) or []
        if isinstance(item, dict) and item.get("description")
    ]


def source_from_prompt(prompt: str) -> str:
    marker = "RESUME TEXT:\n---\n"
    return prompt.split(marker, 1)[1].rsplit("\n---", 1)[0]


def best_reference_score(prediction: str, references: list[str], scorer) -> float:
    return max((scorer(words(prediction), words(ref)) for ref in references), default=0)


def latest_runs() -> list[dict]:
    rows = [json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines()]
    latest = {}
    for row in rows:
        if row["status"] != "success":
            continue
        match = re.search(r"resume_id=([^;]+)", row.get("notes", ""))
        if match:
            latest[(match.group(1), row["prompt_version"])] = row
    return list(latest.values())


def gold_profiles() -> dict[str, dict]:
    return {
        row["id"]: row
        for row in (
            json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines()
        )
    }


def score_rows() -> pd.DataFrame:
    gold = gold_profiles()
    scored = []
    for run in latest_runs():
        resume_id = re.search(r"resume_id=([^;]+)", run["notes"]).group(1)
        predicted = descriptions(run["output"])
        references = descriptions(gold[resume_id])
        source = source_from_prompt(run["rendered_prompt"])
        normalized_source = " ".join(words(source))

        exact = [
            float(" ".join(words(description)) in normalized_source)
            for description in predicted
        ]
        local = [best_window(description, source) for description in predicted]
        source_cosine = sum(value[0] for value in local) / len(local) if local else 0
        source_word_f1 = sum(value[1] for value in local) / len(local) if local else 0
        exact_rate = sum(exact) / len(exact) if exact else 0
        source_fidelity = 0.5 * exact_rate + 0.25 * source_cosine + 0.25 * source_word_f1
        count_recall = min(len(predicted) / len(references), 1) if references else 1

        scored.append(
            {
                "resume_id": resume_id,
                "prompt_version": run["prompt_version"],
                "model": run["model"],
                "latency_seconds": run["latency_ms"] / 1000,
                "descriptions_returned": len(predicted),
                "gold_description_count": len(references),
                "description_count_recall": count_recall,
                "exact_source_rate": exact_rate,
                "source_window_cosine": source_cosine,
                "source_window_word_f1": source_word_f1,
                "source_fidelity_score": source_fidelity,
                # Gold text quality is known to be inconsistent, so these are
                # diagnostics rather than acceptance criteria.
                "gold_cosine_diagnostic": (
                    sum(best_reference_score(p, references, cosine) for p in predicted)
                    / len(predicted)
                    if predicted
                    else 0
                ),
                "gold_word_f1_diagnostic": (
                    sum(best_reference_score(p, references, token_f1) for p in predicted)
                    / len(predicted)
                    if predicted
                    else 0
                ),
                "description_score": 0.7 * source_fidelity + 0.3 * count_recall,
            }
        )
    return pd.DataFrame(scored)


def svg_grouped(frame: pd.DataFrame, metrics: list[str], path: Path, title: str) -> None:
    versions = ["v001", "v002"]
    labels = {"v001": "A: baseline", "v002": "B: verbatim"}
    colors = {"v001": "#64748b", "v002": "#2563eb"}
    width, height = 900, 110 + len(metrics) * 100
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<style>text{font-family:system-ui;fill:#17202a}.title{font-size:20px;font-weight:700}'
        ".label{font-size:13px}.value{font-size:12px;fill:white;font-weight:600}</style>",
        f'<text class="title" x="20" y="30">{html.escape(title)}</text>',
    ]
    maximum = max(frame[metrics].max().max(), 0.001)
    for index, metric in enumerate(metrics):
        y = 65 + index * 100
        parts.append(f'<text class="label" x="20" y="{y}">{html.escape(metric)}</text>')
        for offset, version in enumerate(versions):
            value = frame.loc[version, metric]
            bar_y = y + 10 + offset * 30
            bar_width = 650 * value / maximum
            parts += [
                f'<text class="label" x="20" y="{bar_y + 17}">{labels[version]}</text>',
                f'<rect x="120" y="{bar_y}" width="{bar_width:.1f}" height="23" '
                f'fill="{colors[version]}" rx="3"/>',
                f'<text class="value" x="{125 + max(0, bar_width - 58):.1f}" '
                f'y="{bar_y + 16}">{value:.3f}</text>',
            ]
    parts.append("</svg>")
    path.write_text("".join(parts), encoding="utf-8")


def png_grouped(
    frame: pd.DataFrame,
    metrics: list[str],
    path: Path,
    title: str,
    metric_note: str = "",
    footnotes: tuple[str, ...] = (),
) -> None:
    """Render a publication-ready grouped horizontal bar chart without matplotlib."""
    versions = ["v001", "v002"]
    labels = {"v001": "A: baseline", "v002": "B: verbatim"}
    colors = {"v001": "#64748b", "v002": "#2563eb"}
    metric_labels = {
        "latency_seconds": "Average latency (seconds)",
        "description_score": "Overall description quality",
        "source_fidelity_score": "Source fidelity",
        "exact_source_rate": "Descriptions copied exactly",
        "description_count_recall": "Description count recall",
    }
    width, height = 1400, 265 + len(metrics) * 150 + len(footnotes) * 30
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=22)
    small = ImageFont.load_default(size=18)
    draw.text((35, 25), title, fill="#17202a", font=font)
    draw.text(
        (35, 62),
        "Scenario A - Baseline: no explicit instruction to copy descriptions exactly.",
        fill="#475569",
        font=small,
    )
    draw.text(
        (35, 90),
        "Scenario B - Verbatim: copy descriptions word-for-word; do not paraphrase.",
        fill="#475569",
        font=small,
    )
    if metric_note:
        draw.text((35, 118), metric_note, fill="#0f172a", font=small)
    maximum = max(frame[metrics].max().max(), 0.001)
    for index, metric in enumerate(metrics):
        y = 185 + index * 150
        draw.text(
            (35, y),
            metric_labels.get(metric, metric.replace("_", " ")),
            fill="#17202a",
            font=small,
        )
        for offset, version in enumerate(versions):
            bar_y = y + 35 + offset * 43
            value = float(frame.loc[version, metric])
            bar_width = int(1000 * value / maximum)
            draw.text((35, bar_y + 7), labels[version], fill="#334155", font=small)
            draw.rounded_rectangle(
                (205, bar_y, 205 + bar_width, bar_y + 32),
                radius=5,
                fill=colors[version],
            )
            draw.text(
                (220 + bar_width, bar_y + 5),
                (
                    f"{value * 100:.1f}%"
                    if metric == "exact_source_rate"
                    else f"{value:.3f}"
                ),
                fill="#17202a",
                font=small,
            )
    footnote_y = 210 + len(metrics) * 150
    for index, line in enumerate(footnotes):
        draw.text(
            (35, footnote_y + index * 30),
            line,
            fill="#334155",
            font=small,
        )
    image.save(path, format="PNG", optimize=True)


def main() -> None:
    if not RAW.exists():
        raise SystemExit(f"No raw results at {RAW}")
    REPORTS.mkdir(parents=True, exist_ok=True)
    detail = score_rows()
    detail.to_csv(REPORTS / "per_resume_scores.csv", index=False)
    summary = detail.groupby("prompt_version").mean(numeric_only=True)
    summary.to_csv(REPORTS / "summary.csv")

    png_grouped(
        summary,
        ["latency_seconds"],
        REPORTS / "average_latency.png",
        "Average Latency",
    )
    png_grouped(
        summary,
        ["exact_source_rate"],
        REPORTS / "description_quality_metrics.png",
        "Exact Description Copy Rate",
        metric_note=(
            "Percentage of extracted descriptions found word-for-word in the resume."
        ),
    )
    report = f"""<!doctype html><meta charset="utf-8"><title>Description A/B</title>
<style>body{{font:14px system-ui;max-width:1050px;margin:40px auto;color:#17202a}}
table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{padding:7px;
border:1px solid #ddd}}.note{{background:#eff6ff;padding:14px}}</style>
<h1>Prompt A/B: description-copy instruction</h1>
<p class="note"><b>Primary evidence:</b> source-grounded fidelity. Exact copying and
best local word alignment are measured against OCR text from the resume itself.
Gold-description cosine is shown only as a diagnostic because the existing gold
descriptions are known to be incomplete or inconsistent.</p>
<img src="average_latency.png" alt="Latency comparison" style="max-width:100%">
<img src="description_quality_metrics.png" alt="Quality comparison" style="max-width:100%">
<h2>Aggregate scores</h2>{
    summary.reset_index().to_html(index=False, float_format=lambda x: f"{x:.3f}")
}
<h2>Per-resume scores</h2>{detail.to_html(index=False, float_format=lambda x: f"{x:.3f}")}"""
    (REPORTS / "report.html").write_text(report, encoding="utf-8")
    print(summary.to_string())
    print(f"Wrote reports to {REPORTS}")


if __name__ == "__main__":
    main()
