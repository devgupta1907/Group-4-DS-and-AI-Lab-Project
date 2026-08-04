"""
Career Recommendation — evaluation harness.

Computes Recall@K, Precision@K, MRR and Hit Rate@K against a labelled
gold set, at TWO stages of the pipeline:

    retrieval  — raw vector search output (top RETRIEVAL_TOP_K = 20)
    reranked   — after deterministic weighted re-ranking (top FINAL_TOP_K = 5)

Evaluating both stages separately is the point of this harness: it shows
whether a bad recommendation was the retriever's fault (the right
occupation was never retrieved) or the re-ranker's fault (it was
retrieved but ranked out of the top-5). Those need different fixes.

The LLM explanation step is NOT evaluated here — it does not change which
occupations are returned or their order, so it cannot affect these
metrics. It also costs an API call per profile. Explanation quality needs
separate human review.

METRIC DEFINITIONS (as implemented)
    Hit Rate@K   1 if any relevant occupation appears in the top-K, else 0.
                 Averaged over profiles.
    Recall@K     (relevant items in top-K) / (total relevant items).
                 With one relevant item per profile this equals Hit Rate@K.
    Precision@K  (relevant items in top-K) / K.
                 NOTE: with 1 relevant item, Precision@K is capped at 1/K
                 (max 0.20 at K=5, 0.05 at K=20). Low values are a
                 property of the metric, not a failure of the system.
                 Report it, but read Recall and MRR for real signal.
    MRR          Mean of 1/rank of the FIRST relevant occupation
                 (1.0 = always ranked first, 0.5 = typically second,
                 0 = never retrieved).

Run from: backend/
    uv run python src/career_recommendation/evaluation/evaluate.py
"""

import json
import time
from pathlib import Path

from core.config import GlobalConfig
from career_recommendation.config import CareerRecommendationModuleConfig as Cfg
from career_recommendation.retrieval import retrieve_candidate_occupations
from career_recommendation.re_ranker import deterministic_rerank

GOLD_SET_PATH = Path(__file__).parent / "gold_set.json"
RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"

# K values to report. Retrieval is evaluated up to RETRIEVAL_TOP_K,
# re-ranking only up to FINAL_TOP_K (it returns no more than that).
RETRIEVAL_KS = [1, 3, 5, 10, 20]
RERANK_KS = [1, 3, 5]


# ---------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------

def hit_rate_at_k(ranked_uris: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if set(ranked_uris[:k]) & relevant else 0.0


def recall_at_k(ranked_uris: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked_uris[:k]) & relevant) / len(relevant)


def precision_at_k(ranked_uris: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    return len(set(ranked_uris[:k]) & relevant) / k


def reciprocal_rank(ranked_uris: list[str], relevant: set[str]) -> float:
    for i, uri in enumerate(ranked_uris, start=1):
        if uri in relevant:
            return 1.0 / i
    return 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------

def evaluate(gold_set: list[dict]) -> dict:
    retrieval_rows = []
    rerank_rows = []
    per_profile = []
    failures = []

    total = len(gold_set)
    start_time = time.time()

    for i, entry in enumerate(gold_set, start=1):
        profile = entry["profile"]
        relevant = set(entry["relevant_uris"])

        try:
            retrieved = retrieve_candidate_occupations(profile)
        except Exception as exc:
            failures.append({"profile_id": entry["profile_id"], "error": str(exc)})
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
            "rr": reciprocal_rank(reranked_uris, relevant),
            **{f"hit@{k}": hit_rate_at_k(reranked_uris, relevant, k) for k in RERANK_KS},
            **{f"recall@{k}": recall_at_k(reranked_uris, relevant, k) for k in RERANK_KS},
            **{f"precision@{k}": precision_at_k(reranked_uris, relevant, k) for k in RERANK_KS},
        })

        retrieved_rank = next(
            (idx for idx, u in enumerate(retrieved_uris, 1) if u in relevant), None
        )
        reranked_rank = next(
            (idx for idx, u in enumerate(reranked_uris, 1) if u in relevant), None
        )

        per_profile.append({
            "profile_id": entry["profile_id"],
            "expected": entry.get("relevant_titles", []),
            "retrieved_rank": retrieved_rank,
            "reranked_rank": reranked_rank,
            "top_reranked": [r["occupation_title"] for r in ranked[:3]],
            "used_relaxed_matching": meta["used_relaxed_matching"],
        })

        if i % 10 == 0 or i == total:
            print(f"  evaluated {i}/{total}")

    elapsed = time.time() - start_time

    def summarise(rows: list[dict], ks: list[int]) -> dict:
        if not rows:
            return {}
        out = {"MRR": round(_mean([r["rr"] for r in rows]), 4)}
        for k in ks:
            out[f"HitRate@{k}"] = round(_mean([r[f"hit@{k}"] for r in rows]), 4)
            out[f"Recall@{k}"] = round(_mean([r[f"recall@{k}"] for r in rows]), 4)
            out[f"Precision@{k}"] = round(_mean([r[f"precision@{k}"] for r in rows]), 4)
        return out

    return {
        "config": {
            "embedding_provider": GlobalConfig.EMBEDDING_PROVIDER,
            "embedding_model": (
                GlobalConfig.GEMINI_EMBEDDING_MODEL
                if GlobalConfig.EMBEDDING_PROVIDER == "gemini"
                else GlobalConfig.HF_EMBEDDING_MODEL
            ),
            "chroma_dir": GlobalConfig.CHROMA_DB_DIR,
            "collection": GlobalConfig.CHROMA_COLLECTION,
            "retrieval_top_k": Cfg.RETRIEVAL_TOP_K,
            "final_top_k": Cfg.FINAL_TOP_K,
            "essential_skill_weight": Cfg.ESSENTIAL_SKILL_WEIGHT,
            "optional_skill_weight": Cfg.OPTIONAL_SKILL_WEIGHT,
        },
        "n_profiles": len(retrieval_rows),
        "n_failures": len(failures),
        "failures": failures[:10],
        "elapsed_seconds": round(elapsed, 1),
        "retrieval_stage": summarise(retrieval_rows, RETRIEVAL_KS),
        "reranked_stage": summarise(rerank_rows, RERANK_KS),
        "per_profile": per_profile,
    }


def print_report(results: dict) -> None:
    cfg = results["config"]
    print("\n" + "=" * 62)
    print("CAREER RECOMMENDATION — EVALUATION REPORT")
    print("=" * 62)
    print(f"Embedding : {cfg['embedding_provider']} / {cfg['embedding_model']}")
    print(f"Index     : {cfg['collection']} @ {cfg['chroma_dir']}")
    print(f"Weights   : essential={cfg['essential_skill_weight']}, optional={cfg['optional_skill_weight']}")
    print(f"Profiles  : {results['n_profiles']} evaluated, {results['n_failures']} failed")
    print(f"Runtime   : {results['elapsed_seconds']}s")

    for stage_key, label in [
        ("retrieval_stage", f"STAGE 1 — RETRIEVAL (vector search, top {cfg['retrieval_top_k']})"),
        ("reranked_stage", f"STAGE 2 — AFTER DETERMINISTIC RE-RANKING (top {cfg['final_top_k']})"),
    ]:
        stage = results[stage_key]
        if not stage:
            continue
        print(f"\n{label}")
        print("-" * 62)
        print(f"  MRR: {stage['MRR']:.4f}")
        print(f"  {'K':>4}  {'HitRate@K':>10}  {'Recall@K':>10}  {'Precision@K':>12}")
        ks = sorted({int(k.split("@")[1]) for k in stage if "@" in k})
        for k in ks:
            print(
                f"  {k:>4}  {stage[f'HitRate@{k}']:>10.4f}  "
                f"{stage[f'Recall@{k}']:>10.4f}  {stage[f'Precision@{k}']:>12.4f}"
            )

    # Diagnostic: where did the re-ranker help or hurt?
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
    print("-" * 62)
    print(f"  moved the correct occupation UP    : {improved}")
    print(f"  moved it DOWN                      : {degraded}")
    print(f"  dropped it out of top-{cfg['final_top_k']} entirely  : {lost}")

    print("\nNOTE: with one relevant occupation per profile, Precision@K is")
    print(f"capped at 1/K (max {1/cfg['final_top_k']:.2f} at K={cfg['final_top_k']}).")
    print("Read Recall@K and MRR for the real signal.")
    print("=" * 62)


if __name__ == "__main__":
    if not GOLD_SET_PATH.exists():
        raise SystemExit(
            f"Gold set not found at {GOLD_SET_PATH}.\n"
            "Run build_gold_set.py first:\n"
            "  uv run python src/career_recommendation/evaluation/build_gold_set.py"
        )

    gold_set = json.loads(GOLD_SET_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(gold_set)} labelled profiles from {GOLD_SET_PATH.name}\n")

    results = evaluate(gold_set)
    print_report(results)

    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFull results (incl. per-profile breakdown) written to {RESULTS_PATH}")
