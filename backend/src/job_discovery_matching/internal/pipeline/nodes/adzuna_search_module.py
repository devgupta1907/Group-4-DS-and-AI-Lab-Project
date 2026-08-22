"""Node 2a — Adzuna Module: search_queries[] -> raw_jobs[] (primary source).

Structured like `search_module.py` (same `_job_query` query-shaping,
same dedup-by-URL loop over `state["search_queries"]`), but Adzuna's
`/search` response already IS a structured vacancy record — title,
company, location, description, salary — so there is nothing for
crawl4ai to do here. This node therefore folds what `search_module`
+ `extraction_module` do into one step and writes `raw_jobs[]`
directly, using the same `job_discovery_postings` cache (keyed by
URL) so a listing already seen by the SearXNG path is reused, not
re-embedded.

`graph.py` routes on this node's output: if it produced at least one
job, `search_module` + `extraction_module` (SearXNG + crawl4ai) are
skipped entirely; if Adzuna returned nothing (no credentials, no
matches, API error), the graph falls back to that path instead. See
the `route_after_adzuna` function in `graph.py`.
"""

from __future__ import annotations

import logging

from src.core.db import get_session_factory
from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
from src.job_discovery_matching.internal.services import adzuna_client
from src.job_discovery_matching.internal.services.embedding_client import embed_documents

logger = logging.getLogger(__name__)


def _job_query(query: str) -> str:
    """Same shaping as `search_module._job_query` — keeps queries consistent
    whichever source ends up serving them."""
    lowered = query.lower()
    return query if "job" in lowered or "hiring" in lowered else f"{query} jobs hiring"


def _is_adzuna_compatible(query: str) -> bool:
    """`QUERY_GENERATOR_USER` deliberately asks for one query using a
    Google-style `site:` operator (e.g. "site:linkedin.com/jobs data
    analyst") — that only means something to a real web search engine
    (SearXNG). Adzuna's `what` param is a keyword match against its own
    vacancy index; it has no concept of `site:`, so sending that query
    here either matches nothing or matches on the literal word "site".
    Skip it here — it's still in `state["search_queries"]` for the
    SearXNG fallback to use if Adzuna comes up empty overall."""
    return "site:" not in query.lower()


def _search_location(state: PipelineState) -> str:
    preferences = state.get("preferences") or {}
    return preferences.get("target_location") or state["candidate_json"].get("location") or ""


def _job_json_from_adzuna(job: dict) -> dict:
    """Map Adzuna's normalized fields onto this module's job_json shape
    (same shape `crawler_service._map_jsonld` / `_extract_page_metadata`
    produce, so hard_filter/matching/judge don't need to know which
    source a posting came from)."""
    location = job.get("location") or ""
    description = job.get("description") or ""
    return {
        "title": job.get("title") or "",
        "company": job.get("company") or "",
        "location": location,
        "is_remote": "remote" in location.lower() or "remote" in description.lower()[:500],
        "employment_type": job.get("contract_type") or job.get("contract_time") or "",
        "description": description[:4000],
        "required_skills": [],
        "extraction_method": "adzuna",
        "source_url": job.get("url"),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "category": job.get("category"),
        "created": job.get("created"),
    }


def _job_text_for_embedding(job_json: dict) -> str:
    return " ".join(
        [
            job_json.get("title", "") or "",
            job_json.get("company", "") or "",
            job_json.get("description", "") or "",
        ]
    ).strip()


async def _upsert_job(job: dict) -> dict | None:
    url = job.get("url")
    if not url:
        return None

    job_json = _job_json_from_adzuna(job)
    job_text = job_json["description"] or job_json["title"]
    if not job_text:
        return None

    session_factory = get_session_factory()

    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        cached = await repo.get_fresh_posting(url)
        if cached is not None:
            return {
                "posting_id": cached.id,
                "job_json": cached.job_json,
                "job_text": cached.job_text,
                "embedding": cached.embedding,
                "source_url": url,
            }

    embedding_text = _job_text_for_embedding(job_json)
    [embedding] = embed_documents([embedding_text[:4000] or job_json["title"] or url])

    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        posting = await repo.upsert_posting(
            url=url,
            job_json=job_json,
            job_text=job_text,
            embedding=embedding,
        )

    return {
        "posting_id": posting.id,
        "job_json": job_json,
        "job_text": job_text,
        "embedding": embedding,
        "source_url": url,
    }


async def run(state: PipelineState) -> PipelineState:
    queries = state["search_queries"]
    location = _search_location(state)

    seen_urls: set[str] = set()
    raw_jobs: list[dict] = []

    for query in queries:
        if len(raw_jobs) >= Cfg.MAX_JOB_URLS:
            break
        if not _is_adzuna_compatible(query):
            logger.info("Skipping site-restricted query on Adzuna (SearXNG-fallback-only): %r", query)
            continue
        results = await adzuna_client.search(
            _job_query(query),
            location=location,
            max_results=Cfg.ADZUNA_RESULTS_PER_QUERY,
        )
        for job in results:
            url = job.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            entry = await _upsert_job(job)
            if entry is not None:
                raw_jobs.append(entry)
            if len(raw_jobs) >= Cfg.MAX_JOB_URLS:
                break

    state["raw_jobs"] = raw_jobs
    state["job_urls"] = list(seen_urls)
    state["used_adzuna"] = bool(raw_jobs)

    logger.info(
        "Adzuna search complete: %d queries -> %d jobs",
        len(queries), len(raw_jobs),
    )
    if not raw_jobs:
        logger.warning(
            "Adzuna returned 0 jobs across %d queries: %s. Falling back to "
            "SearXNG + crawl4ai search_module/extraction_module.",
            len(queries), queries,
        )

    state.setdefault("progress", []).append("adzuna_search_complete")
    return state
