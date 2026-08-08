"""
Career Recommendation — evaluation against the REAL resume gold set.
Run from: backend/
    uv run python src/career_recommendation/evaluation/evaluate_gold.py
    uv run python src/career_recommendation/evaluation/evaluate_gold.py --split test
"""

import argparse
import json
import time
from pathlib import Path

from src.core.config import GlobalConfig
from src.career_recommendation.config import CareerRecommendationModuleConfig as Cfg
from src.career_recommendation.retrieval import retrieve_candidate_occupations
from src.career_recommendation.re_ranker import deterministic_rerank

HERE = Path(__file__).parent
GOLD_PATH = HERE / "gold.jsonl"
MAP_PATH = HERE / "category_to_esco.json"
RESULTS_PATH = HERE / "evaluation_results_gold.json"

RETRIEVAL_KS = [1, 3, 5, 10, 20]
RERANK_KS = [1, 3, 5]

# Recall@K and Precision@K are always computed and stored; this only controls
# whether the console report prints them. See the METRICS note above.
SHOW_ALL_METRICS = False


# ---------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------

def hit_rate_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if set(ranked[:k]) & relevant else 0.0


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    return len(set(ranked[:k]) & relevant) / k


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, uri in enumerate(ranked, start=1):
        if uri in relevant:
            return 1.0 / i
    return 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------

def load_gold(split: str | None) -> list[dict]:
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    if split:
        rows = [r for r in rows if r.get("eval_split") == split]
    return rows


def to_profile(record: dict) -> dict:
    """
    Converts a gold.jsonl record into the candidate_profile shape the
    pipeline expects. Contact details are deliberately excluded — they
    carry no career signal and the project does not process PII here.
    """
    return {
        "job_titles": record.get("job_titles") or [],
        "skills": record.get("skills") or [],
        "experience": record.get("experience") or [],
        "projects": record.get("projects") or [],
        "education": record.get("education") or [],
    }


# ---------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------

def evaluate(gold: list[dict], cat_map: dict) -> dict:
    retrieval_rows, rerank_rows, per_profile, failures, skipped = [], [], [], [], []
    start = time.time()
    total = len(gold)

    for i, record in enumerate(gold, start=1):
        category = record.get("category")
        mapped = cat_map.get(category)
        if not mapped:
            skipped.append({"id": record.get("id"), "category": category, "reason": "category not in mapping"})
            continue

        relevant = {m["uri"] for m in mapped}
        profile = to_profile(record)

        if not profile["skills"] and not profile["job_titles"] and not profile["experience"]:
            skipped.append({"id": record.get("id"), "category": category, "reason": "empty profile"})
            continue

        try:
            retrieved = retrieve_candidate_occupations(profile)
        except Exception as exc:
            failures.append({"id": record.get("id"), "error": str(exc)})
            continue

        retrieved_uris = [doc.metadata.get("occupation_uri") for doc, _ in retrieved]
        ranked, meta = deterministic_rerank(profile, retrieved)
        reranked_uris = [r["occupation_uri"] for r in ranked]

        retrieval_rows.append({
            "rr": reciprocal_rank(retrieved_uris, relevant),
            **{f"hit@{k}": hit_rate_at_k(retrieved_uris, relevant, k) for k in RETRIEVAL_KS},
            **{f"recall@{k}": recall_at_k(retrieved_uris, relevant, k) for k in RETRIEVAL_KS},
            **{f"precision@{k}": precision_at_k(retrieved_uris, relevant, k) for k in RETRIEVAL_KS},
        })
        rerank_rows.append({
            "category": category,
            "rr": reciprocal_rank(reranked_uris, relevant),
            **{f"hit@{k}": hit_rate_at_k(reranked_uris, relevant, k) for k in RERANK_KS},
            **{f"recall@{k}": recall_at_k(reranked_uris, relevant, k) for k in RERANK_KS},
            **{f"precision@{k}": precision_at_k(reranked_uris, relevant, k) for k in RERANK_KS},
        })

        per_profile.append({
            "id": record.get("id"),
            "category": category,
            "acceptable": [m["title"] for m in mapped],
            "retrieved_rank": next((idx for idx, u in enumerate(retrieved_uris, 1) if u in relevant), None),
            "reranked_rank": next((idx for idx, u in enumerate(reranked_uris, 1) if u in relevant), None),
            "top_reranked": [r["occupation_title"] for r in ranked[:5]],
            "used_relaxed_matching": meta["used_relaxed_matching"],
            "n_skills": len(profile["skills"]),
        })

        if i % 10 == 0 or i == total:
            print(f"  evaluated {i}/{total}")

    def summarise(rows, ks):
        if not rows:
            return {}
        out = {"MRR": round(_mean([r["rr"] for r in rows]), 4)}
        for k in ks:
            out[f"HitRate@{k}"] = round(_mean([r[f"hit@{k}"] for r in rows]), 4)
            out[f"Recall@{k}"] = round(_mean([r[f"recall@{k}"] for r in rows]), 4)
            out[f"Precision@{k}"] = round(_mean([r[f"precision@{k}"] for r in rows]), 4)
        return out

    # Per-category Hit Rate@5, to expose where the system actually fails.
    by_cat = {}
    for r in rerank_rows:
        by_cat.setdefault(r["category"], []).append(r["hit@5"])
    per_category = {c: round(_mean(v), 3) for c, v in sorted(by_cat.items())}

    return {
        "config": {
            "embedding_provider": GlobalConfig.EMBEDDING_PROVIDER,
            "embedding_model": (
                GlobalConfig.GEMINI_EMBEDDING_MODEL
                if GlobalConfig.EMBEDDING_PROVIDER == "gemini"
                else GlobalConfig.HF_EMBEDDING_MODEL
            ),
            "vector_store": f"supabase:{GlobalConfig.SUPABASE_TABLE}",
            "retrieval_top_k": Cfg.RETRIEVAL_TOP_K,
            "final_top_k": Cfg.FINAL_TOP_K,
            "essential_skill_weight": Cfg.ESSENTIAL_SKILL_WEIGHT,
            "optional_skill_weight": Cfg.OPTIONAL_SKILL_WEIGHT,
        },
        "n_evaluated": len(retrieval_rows),
        "n_skipped": len(skipped),
        "n_failures": len(failures),
        "skipped": skipped,
        "failures": failures[:10],
        "elapsed_seconds": round(time.time() - start, 1),
        "retrieval_stage": summarise(retrieval_rows, RETRIEVAL_KS),
        "reranked_stage": summarise(rerank_rows, RERANK_KS),
        "per_category_hitrate_at_5": per_category,
        "per_profile": per_profile,
    }


def print_report(results: dict, split: str | None) -> None:
    cfg = results["config"]
    print("\n" + "=" * 66)
    print("CAREER RECOMMENDATION — EVALUATION (REAL RESUME GOLD SET)")
    print("=" * 66)
    print(f"Split     : {split or 'all'}")
    print(f"Embedding : {cfg['embedding_provider']} / {cfg['embedding_model']}")
    print(f"Index     : {cfg['vector_store']}")
    print(f"Weights   : essential={cfg['essential_skill_weight']}, optional={cfg['optional_skill_weight']}")
    print(f"Profiles  : {results['n_evaluated']} evaluated, {results['n_skipped']} skipped, {results['n_failures']} failed")
    print(f"Runtime   : {results['elapsed_seconds']}s")

    for key, label in [
        ("retrieval_stage", f"STAGE 1 — RETRIEVAL (top {cfg['retrieval_top_k']})"),
        ("reranked_stage", f"STAGE 2 — AFTER RE-RANKING (top {cfg['final_top_k']})"),
    ]:
        stage = results[key]
        if not stage:
            continue
        print(f"\n{label}")
        print("-" * 66)
        print(f"  MRR: {stage['MRR']:.4f}")
        ks = sorted({int(x.split('@')[1]) for x in stage if '@' in x})

        if SHOW_ALL_METRICS:
            print(f"  {'K':>4}  {'HitRate@K':>10}  {'Recall@K':>10}  {'Precision@K':>12}")
            for k in ks:
                print(
                    f"  {k:>4}  {stage[f'HitRate@{k}']:>10.4f}  "
                    f"{stage[f'Recall@{k}']:>10.4f}  {stage[f'Precision@{k}']:>12.4f}"
                )
        else:
            print(f"  {'K':>4}  {'HitRate@K':>10}")
            for k in ks:
                print(f"  {k:>4}  {stage[f'HitRate@{k}']:>10.4f}")

    improved = degraded = lost = 0
    for p in results["per_profile"]:
        rt, rr = p["retrieved_rank"], p["reranked_rank"]
        if rt is not None and rr is None:
            lost += 1
        elif rt is not None and rr is not None:
            if rr < rt:
                improved += 1
            elif rr > rt:
                degraded += 1

    print("\nRE-RANKER DIAGNOSTIC")
    print("-" * 66)
    print(f"  moved an acceptable occupation UP  : {improved}")
    print(f"  moved it DOWN                      : {degraded}")
    print(f"  dropped it out of top-{cfg['final_top_k']} entirely : {lost}")

    print("\nWEAKEST CATEGORIES (HitRate@5)")
    print("-" * 66)
    worst = sorted(results["per_category_hitrate_at_5"].items(), key=lambda x: x[1])[:10]
    for cat, score in worst:
        print(f"  {score:.2f}  {cat}")

    print("to 'software developer'), which caps achievable scores by construction.")
    if not SHOW_ALL_METRICS:
        print("Recall@K and Precision@K are in the JSON output, not printed here.")
    print("=" * 66)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default=None,
                    help="Evaluate only one split. Default: all 86 records.")
    args = ap.parse_args()

    if not GOLD_PATH.exists():
        raise SystemExit(f"Missing {GOLD_PATH}")
    if not MAP_PATH.exists():
        raise SystemExit(f"Missing {MAP_PATH}")

    gold = load_gold(args.split)
    cat_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))["categories"]
    print(f"Loaded {len(gold)} resumes, {len(cat_map)} category mappings\n")

    results = evaluate(gold, cat_map)
    print_report(results, args.split)

    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFull results written to {RESULTS_PATH}")