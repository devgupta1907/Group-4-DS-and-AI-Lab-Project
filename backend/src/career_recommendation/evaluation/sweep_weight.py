"""
Sweep SKILL_BONUS_WEIGHT to find the value that beats retrieval baseline.
Run from backend/:
    uv run python src/career_recommendation/evaluation/sweep_weight.py
"""
import json
from pathlib import Path

from src.career_recommendation.config import CareerRecommendationModuleConfig as Cfg
from src.career_recommendation.retrieval import retrieve_candidate_occupations
from src.career_recommendation import re_ranker
from src.career_recommendation.evaluation.evaluate_gold import (
    load_gold, to_profile, reciprocal_rank, hit_rate_at_k, _mean, MAP_PATH
)

WEIGHTS = [0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.25, 0.40]

gold = load_gold(None)
cat_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))["categories"]

# Retrieve once, reuse across all weights (retrieval doesn't depend on the weight)
cache = []
for rec in gold:
    mapped = cat_map.get(rec.get("category"))
    if not mapped:
        continue
    profile = to_profile(rec)
    if not (profile["skills"] or profile["job_titles"] or profile["experience"]):
        continue
    cache.append((profile, {m["uri"] for m in mapped}, retrieve_candidate_occupations(profile)))

print(f"cached {len(cache)} profiles\n")

base_rr = [reciprocal_rank([d.metadata["occupation_uri"] for d, _ in r], rel) for _, rel, r in cache]
base_h5 = [hit_rate_at_k([d.metadata["occupation_uri"] for d, _ in r], rel, 5) for _, rel, r in cache]
print(f"RETRIEVAL BASELINE   MRR={_mean(base_rr):.4f}  HitRate@5={_mean(base_h5):.4f}\n")

print(f"{'weight':>8}  {'MRR':>8}  {'Hit@1':>8}  {'Hit@3':>8}  {'Hit@5':>8}")
for w in WEIGHTS:
    Cfg.SKILL_BONUS_WEIGHT = w
    rrs, h1, h3, h5 = [], [], [], []
    for profile, rel, retrieved in cache:
        ranked, _ = re_ranker.deterministic_rerank(profile, retrieved)
        uris = [r["occupation_uri"] for r in ranked]
        rrs.append(reciprocal_rank(uris, rel))
        h1.append(hit_rate_at_k(uris, rel, 1))
        h3.append(hit_rate_at_k(uris, rel, 3))
        h5.append(hit_rate_at_k(uris, rel, 5))
    print(f"{w:>8.2f}  {_mean(rrs):>8.4f}  {_mean(h1):>8.4f}  {_mean(h3):>8.4f}  {_mean(h5):>8.4f}")