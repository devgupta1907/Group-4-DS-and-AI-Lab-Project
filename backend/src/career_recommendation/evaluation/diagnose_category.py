"""
Career Recommendation — single-category retrieval diagnostic.

Purpose: Civil Engineer has an unambiguous, clean mapping (civil
engineer / civil engineering technician) and both gold resumes are
textbook matches — yet the category scores 0.50, not 1.0. That's not
a label problem (bucket 2), so this script shows exactly what the
pipeline does with those two resumes, to tell whether it's:
  - retrieving the wrong occupations entirely (embedding/query problem), or
  - retrieving the right occupation but ranking it below the top 5
    (re-ranking/truncation problem, per the "MRR gap is truncation"
    caveat already noted in the M4 handoff).

Run from: backend/
    uv run python src/career_recommendation/evaluation/diagnose_category.py "Civil Engineer"
    uv run python src/career_recommendation/evaluation/diagnose_category.py "Blockchain" --top-k 10
"""

import argparse
import json
from pathlib import Path

from career_recommendation.retrieval import retrieve_candidate_occupations
from career_recommendation.re_ranker import deterministic_rerank
from career_recommendation.config import CareerRecommendationModuleConfig as Cfg

HERE = Path(__file__).parent
GOLD_PATH = HERE / "gold.jsonl"
MAP_PATH = HERE / "category_to_esco.json"


def load_gold_records(category: str) -> list[dict]:
    records = []
    with open(GOLD_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("category") == category:
                records.append(rec)
    return records


def load_acceptable_uris(category: str) -> set[str]:
    with open(MAP_PATH, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("categories", data).get(category, [])
    return {e["uri"] for e in entries if isinstance(e, dict) and "uri" in e}


def diagnose(category: str, top_k: int) -> None:
    records = load_gold_records(category)
    acceptable = load_acceptable_uris(category)

    if not records:
        print(f'No gold records found for category "{category}" — check spelling against gold.jsonl.')
        return
    if not acceptable:
        print(f'No mapped ESCO occupations for "{category}" — this is a bucket-1/2 problem, not bucket 3.')
        return

    print(f"Category: {category}")
    print(f"Acceptable URIs ({len(acceptable)}): {sorted(acceptable)}\n")

    for i, rec in enumerate(records, 1):
        print(f"{'=' * 70}\nRecord {i}: {rec.get('job_titles')}\n{'=' * 70}")

        retrieved = retrieve_candidate_occupations(rec)
        print(f"\nSTAGE 1 — raw retrieval (top {Cfg.RETRIEVAL_TOP_K}):")
        hit_rank_retrieval = None
        for rank, (doc, score) in enumerate(retrieved, 1):
            uri = doc.metadata.get("occupation_uri")
            hit = uri in acceptable
            if hit and hit_rank_retrieval is None:
                hit_rank_retrieval = rank
            marker = "  <-- ACCEPTABLE" if hit else ""
            if rank <= top_k or hit:
                print(f"  {rank:>2}. sim={score:.4f}  {doc.metadata.get('occupation_title')}{marker}")

        if hit_rank_retrieval is None:
            print(f"\n  RESULT: acceptable occupation NOT in top {Cfg.RETRIEVAL_TOP_K} retrieval at all.")
            print("  -> This is an embedding/query problem, not a ranking problem.")
        else:
            print(f"\n  Acceptable occupation found at retrieval rank {hit_rank_retrieval}.")

        ranked, meta = deterministic_rerank(rec, retrieved)
        print(f"\nSTAGE 2 — after re-rank (top {Cfg.FINAL_TOP_K}), meta={meta}:")
        hit_rank_final = None
        for rank, r in enumerate(ranked, 1):
            hit = r["occupation_uri"] in acceptable
            if hit and hit_rank_final is None:
                hit_rank_final = rank
            marker = "  <-- ACCEPTABLE" if hit else ""
            print(
                f"  {rank}. final={r['final_score']:.4f}  sim={r['similarity_score']:.4f}  "
                f"skill={r['weighted_skill_score']:.1f}  {r['occupation_title']}{marker}"
            )

        if hit_rank_final is not None:
            print(f"\n  RESULT: HIT at final rank {hit_rank_final}.")
        elif hit_rank_retrieval is not None:
            print(
                f"\n  RESULT: MISS — was at retrieval rank {hit_rank_retrieval} but got pushed "
                f"out of top {Cfg.FINAL_TOP_K} by re-ranking or truncation."
            )
        else:
            print(f"\n  RESULT: MISS — never retrieved in the first {Cfg.RETRIEVAL_TOP_K}.")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("category", help='e.g. "Civil Engineer"')
    parser.add_argument("--top-k", type=int, default=5, help="How many non-hit retrieval rows to also print")
    args = parser.parse_args()
    diagnose(args.category, args.top_k)
