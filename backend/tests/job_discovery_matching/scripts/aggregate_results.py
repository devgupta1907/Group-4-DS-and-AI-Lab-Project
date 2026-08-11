"""Parse promptfoo `-o results.json` outputs from the 4 evals, build a
leaderboard per eval, pick a winner by a weighted composite score, and
save everything under evals/results/.

Usage:
    python3 aggregate_results.py [--results-dir evals/results]

Expects these files to exist (produced by scripts/run_all.sh or manual
`promptfoo eval -o ...` runs):
    ranking.json
    search_crawl.json
    prompts_query_generator.json
    prompts_judge.json
"""
import argparse
import json
from pathlib import Path

# --------------------------------------------------------------- weights --
# Tune these to match what you actually care about. They only need to be
# internally consistent per eval (they're just used to rank configs
# within one eval, not compared across evals).
RANKING_WEIGHTS = {"precision_at_5": 0.35, "ndcg_at_10": 0.30, "spearman_correlation": 0.35}
RANKING_LATENCY_WEIGHT = 0.15  # lower latency is better; penalty subtracted

SEARCH_CRAWL_WEIGHTS = {"coverage_score": 0.45, "crawl_success_score": 0.35}
SEARCH_CRAWL_LATENCY_WEIGHT = 0.20

PROMPT_WEIGHTS = {  # used for both query_generator and judge; missing keys ignored
    "query_schema_score": 0.35,
    "query_diversity_score": 0.20,
    "judge_schema_score": 0.35,
    "judge_calibration_score": 0.20,
}
PROMPT_LATENCY_WEIGHT = 0.15


def _load(results_dir: Path, filename: str) -> dict | None:
    path = results_dir / filename
    if not path.exists():
        print(f"  (skipping {filename} — not found, run this eval first)")
        return None
    return json.loads(path.read_text())


def _mean_named_scores(prompt_entry: dict) -> dict:
    metrics = prompt_entry.get("metrics", {}) or {}
    sums = metrics.get("namedScores", {}) or {}
    counts = metrics.get("namedScoresCount", {}) or {}
    return {k: (sums[k] / counts[k] if counts.get(k) else 0.0) for k in sums}


def _mean_latency_ms(prompt_entry: dict, n_tests: int) -> float:
    total = prompt_entry.get("metrics", {}).get("totalLatencyMs", 0)
    return total / n_tests if n_tests else 0.0


def _label_for(prompt_entry: dict, eval_kind: str) -> str:
    if eval_kind == "param_sweep":
        provider = prompt_entry.get("provider")
        if isinstance(provider, dict):
            return provider.get("label") or provider.get("id", "?")
        return provider or prompt_entry.get("id", "?")
    # prompt-variant evals: derive a short label from the source file path
    raw_label = prompt_entry.get("label") or ""
    return raw_label.split(":")[0].split("/")[-1] or prompt_entry.get("id", "?")[:12]


def _normalize(values: dict, key: str) -> float:
    """Min-max normalise `key` across the leaderboard rows in `values`
    (dict of label -> row dict) so latency can be combined with 0-1
    quality scores on a comparable scale."""
    xs = [row[key] for row in values.values()]
    lo, hi = min(xs), max(xs)
    if hi == lo:
        return {label: 0.0 for label in values}
    return {label: (row[key] - lo) / (hi - lo) for label, row in values.items()}


def _build_leaderboard(data: dict, weights: dict, latency_weight: float, eval_kind: str) -> list[dict]:
    prompts = data["results"]["prompts"]
    n_tests = data["results"]["stats"].get("successes", 0) + data["results"]["stats"].get("failures", 0)
    if not n_tests:
        # fall back: infer from any row's namedScoresCount
        n_tests = max((v for e in prompts for v in (e.get("metrics", {}).get("namedScoresCount") or {}).values()), default=1)

    rows = {}
    for entry in prompts:
        label = _label_for(entry, eval_kind)
        scores = _mean_named_scores(entry)
        latency = _mean_latency_ms(entry, n_tests)
        row = {k: scores.get(k, 0.0) for k in weights}
        row["latency_ms"] = latency
        row["pass_rate"] = entry["metrics"]["testPassCount"] / max(
            entry["metrics"]["testPassCount"] + entry["metrics"]["testFailCount"], 1
        )
        rows[label] = row

    latency_norm = _normalize(rows, "latency_ms")  # 0 = fastest, 1 = slowest

    leaderboard = []
    for label, row in rows.items():
        quality = sum(weights[k] * row.get(k, 0.0) for k in weights)
        latency_penalty = latency_weight * latency_norm[label]
        composite = round(quality - latency_penalty, 4)
        leaderboard.append({"label": label, "composite_score": composite, **row})

    leaderboard.sort(key=lambda r: r["composite_score"], reverse=True)
    return leaderboard


def _print_and_save_md(title: str, leaderboard: list[dict], out_path: Path) -> None:
    if not leaderboard:
        return
    cols = [c for c in leaderboard[0].keys() if c != "label"]
    lines = [f"## {title}", "", "| # | config | " + " | ".join(cols) + " |",
             "|---|---|" + "---|" * len(cols)]
    for i, row in enumerate(leaderboard, 1):
        vals = " | ".join(f"{row[c]:.4f}" if isinstance(row[c], float) else str(row[c]) for c in cols)
        marker = " **← best**" if i == 1 else ""
        lines.append(f"| {i} | {row['label']}{marker} | {vals} |")
    lines.append("")
    text = "\n".join(lines)
    print(text)
    out_path.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=str(Path(__file__).resolve().parents[1] / "results"))
    args = parser.parse_args()
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    best_config = {}
    summary_sections = []

    print("=" * 70)
    print("RANKING EVAL (BM25 + embedding weight sweep)")
    print("=" * 70)
    ranking_data = _load(results_dir, "ranking.json")
    if ranking_data:
        lb = _build_leaderboard(ranking_data, {**RANKING_WEIGHTS}, RANKING_LATENCY_WEIGHT, "param_sweep")
        _print_and_save_md("Ranking weight sweep", lb, results_dir / "leaderboard_ranking.md")
        best_config["ranking"] = lb[0]
        summary_sections.append(("Ranking", lb))

    print("=" * 70)
    print("SEARCH + CRAWL EVAL (parameter sweep)")
    print("=" * 70)
    sc_data = _load(results_dir, "search_crawl.json")
    if sc_data:
        lb = _build_leaderboard(sc_data, {**SEARCH_CRAWL_WEIGHTS}, SEARCH_CRAWL_LATENCY_WEIGHT, "param_sweep")
        _print_and_save_md("Search + crawl parameter sweep", lb, results_dir / "leaderboard_search_crawl.md")
        best_config["search_crawl"] = lb[0]
        summary_sections.append(("Search + Crawl", lb))

    print("=" * 70)
    print("QUERY_GENERATOR PROMPT VARIANTS")
    print("=" * 70)
    qg_data = _load(results_dir, "prompts_query_generator.json")
    if qg_data:
        lb = _build_leaderboard(qg_data, {k: v for k, v in PROMPT_WEIGHTS.items() if k.startswith("query_")},
                                 PROMPT_LATENCY_WEIGHT, "prompt_variant")
        _print_and_save_md("query_generator prompt variants", lb, results_dir / "leaderboard_query_generator.md")
        best_config["query_generator_prompt"] = lb[0]
        summary_sections.append(("query_generator prompt", lb))

    print("=" * 70)
    print("JUDGE_BATCH PROMPT VARIANTS")
    print("=" * 70)
    j_data = _load(results_dir, "prompts_judge.json")
    if j_data:
        lb = _build_leaderboard(j_data, {k: v for k, v in PROMPT_WEIGHTS.items() if k.startswith("judge_")},
                                 PROMPT_LATENCY_WEIGHT, "prompt_variant")
        _print_and_save_md("judge_batch prompt variants", lb, results_dir / "leaderboard_judge.md")
        best_config["judge_prompt"] = lb[0]
        summary_sections.append(("judge_batch prompt", lb))

    (results_dir / "best_config.json").write_text(json.dumps(best_config, indent=2))
    print("=" * 70)
    print(f"Saved winners to {results_dir / 'best_config.json'}")

    # Human-readable rollup
    summary_lines = ["# career-agent eval summary", ""]
    for name, lb in summary_sections:
        if lb:
            summary_lines.append(f"- **{name}** best: `{lb[0]['label']}` (composite {lb[0]['composite_score']})")
    summary_lines.append("")
    summary_lines.append("See leaderboard_*.md in this directory for full per-config breakdowns.")
    (results_dir / "summary.md").write_text("\n".join(summary_lines))
    print(f"Saved summary to {results_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
