"""Adzuna search client.

Adapted from the standalone `adzuna_job_fetcher.py` script into this
module's async service style (see `internal/services/searxng_client.py`
for the pattern being followed). Unlike SearXNG, Adzuna's `/search`
endpoint already returns structured vacancy data (title, company,
location, description, salary, ...) straight from its job index, so a
result from here needs no crawl4ai fetch before it can be scored —
see `internal/pipeline/nodes/adzuna_search_module.py`, which is the
only caller.

Credentials (`ADZUNA_APP_ID` / `ADZUNA_APP_KEY`) come from
`JobDiscoveryModuleConfig`, which loads them from the environment the
same way `SEARXNG_URL` is loaded. Missing/invalid credentials or a
network failure are treated as "no results" (empty list) rather than
raised, so the caller can fall back to the SearXNG + crawl4ai path
without a try/except of its own.
"""

from __future__ import annotations

import logging

import httpx

from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg

logger = logging.getLogger(__name__)


async def search(
    query: str,
    *,
    location: str = "",
    country: str | None = None,
    max_results: int = 10,
    page: int = 1,
) -> list[dict]:
    """Return a list of normalized job dicts for a search query.

    Mirrors `searxng_client.search`'s contract (never raises, returns
    `[]` on any failure) so both search sources are interchangeable
    from the pipeline node's point of view.
    """
    if not Cfg.ADZUNA_APP_ID or not Cfg.ADZUNA_APP_KEY:
        logger.warning(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY not configured — skipping Adzuna search for %r",
            query,
        )
        return []

    country = country or Cfg.ADZUNA_COUNTRY
    url = f"{Cfg.ADZUNA_BASE_URL}/jobs/{country}/search/{page}"

    params = {
        "app_id": Cfg.ADZUNA_APP_ID,
        "app_key": Cfg.ADZUNA_APP_KEY,
        "results_per_page": max_results,
        "what": query,
        "content-type": "application/json",
    }
    if location:
        params["where"] = location

    try:
        async with httpx.AsyncClient(timeout=Cfg.ADZUNA_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(
                    "Adzuna returned HTTP %s for %r. Body: %s",
                    resp.status_code, query, resp.text[:500],
                )
                return []
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Adzuna query failed for %r: %s", query, exc)
        return []

    jobs = [_normalize(job) for job in data.get("results", [])]
    jobs = [job for job in jobs if job["url"] and job["title"]]

    logger.info("Adzuna query %r -> %d results", query, len(jobs))
    return jobs[:max_results]


def _normalize(job: dict) -> dict:
    """Same field mapping as the original `adzuna_job_fetcher.fetch_jobs`."""
    company = job.get("company") or {}
    location_data = job.get("location") or {}
    category = job.get("category") or {}

    return {
        "id": job.get("id"),
        "title": job.get("title") or "",
        "company": company.get("display_name") or "",
        "location": location_data.get("display_name") or "",
        "description": job.get("description") or "",
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "contract_type": job.get("contract_type"),
        "contract_time": job.get("contract_time"),
        "category": category.get("label"),
        "created": job.get("created"),
        "url": job.get("redirect_url") or "",
    }
