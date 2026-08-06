"""Node 5 — Matching Module: filtered_jobs[] -> ranked_jobs[].

Stage 1 of the two-stage re-ranking strategy: BM25 (exact skill
matching) and cosine similarity over the candidate/job embeddings
(semantic matching) are combined into a single hybrid score, and the top
`Cfg.TOP_K_RANKED` jobs are kept for the LLM judge stage. Zero LLM calls.
"""

from __future__ import annotations

import logging

from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.services.bm25_service import score_jobs_against_query
from src.job_discovery_matching.internal.services.embedding_client import cosine_similarity

logger = logging.getLogger(__name__)


def _candidate_query_text(candidate: dict) -> str:
    return " ".join(
        [
            " ".join(candidate.get("skills", []) or []),
            " ".join(candidate.get("target_roles", []) or []),
            candidate.get("domain", "") or "",
        ]
    )


async def run(state: PipelineState) -> PipelineState:
    candidate = state["candidate_json"]
    candidate_embedding = state["candidate_embedding"]
    entries = state.get("filtered_jobs", [])

    if not entries:
        state["ranked_jobs"] = []
        state.setdefault("progress", []).append("matching_complete")
        return state

    query_text = _candidate_query_text(candidate)
    job_texts = [e["job_text"] for e in entries]
    bm25_scores = score_jobs_against_query(query_text, job_texts)

    weight_sum = Cfg.BM25_WEIGHT + Cfg.EMBEDDING_WEIGHT
    ranked = []
    for entry, bm25_score in zip(entries, bm25_scores):
        embed_score = cosine_similarity(candidate_embedding, entry["embedding"])
        embed_score_clipped = max(0.0, min(1.0, (embed_score + 1) / 2))

        hybrid_raw = Cfg.BM25_WEIGHT * bm25_score + Cfg.EMBEDDING_WEIGHT * embed_score_clipped
        hybrid_normalised = hybrid_raw / weight_sum if weight_sum else hybrid_raw

        ranked.append(
            {
                **entry,
                "bm25_score": round(bm25_score, 4),
                "embedding_score": round(embed_score_clipped, 4),
                "hybrid_score": round(hybrid_normalised, 4),
            }
        )

    ranked.sort(key=lambda r: r["hybrid_score"], reverse=True)
    top_ranked = ranked[: Cfg.TOP_K_RANKED]

    state["ranked_jobs"] = top_ranked
    state.setdefault("progress", []).append("matching_complete")
    return state
