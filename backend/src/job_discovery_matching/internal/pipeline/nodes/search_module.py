"""Node 2 — Search Module: search_queries[] -> job_urls[].

Zero LLM calls. Fans out each query to SearXNG and de-duplicates URLs
across all queries, capped at `Cfg.MAX_JOB_URLS`.
"""

from __future__ import annotations

import logging

from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.services import searxng_client

logger = logging.getLogger(__name__)


async def run(state: PipelineState) -> PipelineState:
    queries = state["search_queries"]

    seen_urls: set[str] = set()
    job_urls: list[str] = []

    for query in queries:
        results = await searxng_client.search(query, max_results=8)
        for r in results:
            url = r["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                job_urls.append(url)
            if len(job_urls) >= Cfg.MAX_JOB_URLS:
                break
        if len(job_urls) >= Cfg.MAX_JOB_URLS:
            break

    state["job_urls"] = job_urls
    logger.info("Search complete: %d queries -> %d unique job URLs", len(queries), len(job_urls))
    if not job_urls:
        logger.warning(
            "Zero job URLs found across all %d queries: %s. Check SearXNG directly — "
            "this is almost always a SearXNG/upstream-engine problem, not this module.",
            len(queries), queries,
        )
    state.setdefault("progress", []).append("search_complete")
    return state
