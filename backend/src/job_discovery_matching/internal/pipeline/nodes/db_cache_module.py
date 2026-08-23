"""Node 1.5 — DB Cache Module: candidate_embedding -> raw_jobs[] (checked
FIRST, before Adzuna and before SearXNG+crawl4ai).

Every posting this pipeline has ever crawled or pulled from Adzuna is
already sitting in `job_discovery_postings` with its embedding. If a
posting in there is both (a) fresh — last confirmed within
`Cfg.DB_CACHE_MAX_AGE_HOURS` (default 24h, i.e. "created less than a
day ago") — and (b) semantically close to THIS candidate — cosine
similarity >= `Cfg.DB_CACHE_SIMILARITY_THRESHOLD` — there is no reason
to spend an Adzuna call or a crawl4ai fetch re-discovering it. This
node answers that question up front, in Python, using the same
`cosine_similarity` helper `matching_module.py` uses for its embedding
score, so "similar" means the same thing here as it does in the final
ranking.

A posting also has to pass `hard_filter`'s location/salary checks (same
functions hard_filter itself uses, imported from there rather than
reimplemented) before it counts toward "the cache found something".
Without this, a candidate searching for a specific city/salary could get
a cache hit purely on embedding similarity — a real posting, just not
one that survives the very next node — which used to make
`route_after_db_cache` decide to skip Adzuna/SearXNG entirely on the
strength of results that were about to be thrown away anyway. hard_filter
still re-checks everything downstream regardless (harmless, cheap,
consistent with every other source feeding it); this is about the
ROUTING decision being honest about what the cache actually has, not
about removing hard_filter's own check.

This is the same shared, cross-user cache `extraction_module.py` and
`adzuna_search_module.py` write into via `repo.upsert_posting` — this
node only reads it; it never crawls or calls Adzuna itself.

`graph.py` routes on this node's output: MIN_JOBS_BEFORE_ACCEPTING or
more matching jobs found -> straight to `hard_filter`. Fewer than that
-> `adzuna_module`, which now MERGES with whatever this node did find
rather than discarding it (see adzuna_search_module.py) — a thin cache
hit still contributes, it just gets topped up instead of accepted as-is
or thrown away. See `route_after_db_cache` in `graph.py`.
"""

from __future__ import annotations

import logging

from src.core.db import get_session_factory
from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.nodes.hard_filter import (
    _passes_location,
    _passes_salary,
)
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
from src.job_discovery_matching.internal.services.embedding_client import cosine_similarity

logger = logging.getLogger(__name__)


def _similarity(candidate_embedding: list[float], posting_embedding: list[float] | None) -> float:
    if not posting_embedding:
        return 0.0
    raw = cosine_similarity(candidate_embedding, posting_embedding)
    return max(0.0, min(1.0, (raw + 1) / 2))  # same [-1,1] -> [0,1] clip matching_module uses


async def run(state: PipelineState) -> PipelineState:
    candidate = state["candidate_json"]
    candidate_embedding = state["candidate_embedding"]
    preferences = state.get("preferences") or {}

    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        pool = await repo.find_fresh_postings(
            max_age_hours=Cfg.DB_CACHE_MAX_AGE_HOURS,
            limit=Cfg.DB_CACHE_POOL_SIZE,
        )

    scored = []
    similarity_hits = 0
    for posting in pool:
        score = _similarity(candidate_embedding, posting.embedding)
        if score < Cfg.DB_CACHE_SIMILARITY_THRESHOLD:
            continue
        similarity_hits += 1
        if not _passes_location(candidate, posting.job_json, posting.job_text, preferences):
            continue
        if not _passes_salary(posting.job_json, posting.job_text, preferences):
            continue
        scored.append((score, posting))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[: Cfg.MAX_JOB_URLS]

    raw_jobs = [
        {
            "posting_id": posting.id,
            "job_json": posting.job_json,
            "job_text": posting.job_text,
            "embedding": posting.embedding,
            "source_url": posting.source_url,
        }
        for _score, posting in top
    ]

    state["raw_jobs"] = raw_jobs
    state["used_db_cache"] = bool(raw_jobs)

    logger.info(
        "DB cache check: %d fresh postings in pool (<= %dh old), %d cleared "
        "similarity >= %.2f, %d of those also matched location/salary "
        "preferences -> %d used",
        len(pool), Cfg.DB_CACHE_MAX_AGE_HOURS, similarity_hits,
        Cfg.DB_CACHE_SIMILARITY_THRESHOLD, len(scored), len(raw_jobs),
    )
    if len(raw_jobs) < Cfg.MIN_JOBS_BEFORE_ACCEPTING:
        logger.info(
            "Only %d/%d minimum from DB cache — falling through to adzuna_module to top up.",
            len(raw_jobs), Cfg.MIN_JOBS_BEFORE_ACCEPTING,
        )

    state.setdefault("progress", []).append("db_cache_check_complete")
    return state
