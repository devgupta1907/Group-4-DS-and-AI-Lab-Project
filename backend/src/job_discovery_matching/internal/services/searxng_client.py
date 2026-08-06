"""SearXNG search client.

Ported from career-agent's app/services/searxng_client.py. The
Redis-backed result cache from the original is dropped — this repo's
docker-compose has no Redis service, and the job posting itself (the
expensive crawl4ai fetch) is already cached in Postgres via
`internal.repository` / `job_discovery_postings`, which is where the
real savings are. Caching search-engine result pages is a smaller win
and can be reintroduced here later without touching any other module.
"""

from __future__ import annotations

import logging

import httpx

from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg

logger = logging.getLogger(__name__)


async def search(query: str, max_results: int = 8) -> list[dict]:
    """Return a list of {title, url, content} dicts for a search query."""
    try:
        async with httpx.AsyncClient(timeout=Cfg.SEARXNG_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{Cfg.SEARXNG_URL}/search",
                params={"q": query, "format": "json"},
            )
            if resp.status_code != 200:
                logger.warning(
                    "SearXNG returned HTTP %s for %r. Body: %s",
                    resp.status_code, query, resp.text[:500],
                )
                return []
            print(resp.text)
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("SearXNG query failed for %r: %s", query, exc)
        return []

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        }
        for r in data.get("results", [])
        if r.get("url")
    ]

    # Single most useful line for diagnosing "0 jobs" — if this logs 0 for
    # every query, the problem is SearXNG/upstream engines, not this module.
    logger.info(
        "SearXNG query %r -> %d results (engines: %s)",
        query, len(results), data.get("engines", data.get("number_of_results", "?")),
    )
    return results[:max_results]
