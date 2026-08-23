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

`graph.py` routes on this node's output: once db_cache_module +
adzuna_module together have MIN_JOBS_BEFORE_ACCEPTING matching jobs,
`search_module` + `extraction_module` (SearXNG + crawl4ai) are skipped;
below that, the graph falls through to that path too. See
`route_after_adzuna` in `graph.py`.

This node MERGES with whatever db_cache_module already put in
`state["raw_jobs"]` rather than overwriting it — a thin cache hit still
counts, Adzuna just tops it up to (at most) Cfg.MAX_JOB_URLS total,
deduped by URL against what's already there.
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
    """Adzuna's `where` param takes exactly one location, unlike SearXNG's
    query text or hard_filter's match-any-of-N. `target_locations` is
    already resolved to at least the candidate's own location by
    career_report.service before the pipeline runs (see that module), so
    the `state["candidate_json"].get("location")` fallback below is a
    second safety net for callers that build state directly rather than
    through that path — not the primary fallback anymore.

    Only the FIRST of up to 3 preferred locations is used here; the other
    two (if given) still apply downstream in hard_filter's location match
    and in the SearXNG query-generation prompt, which do consider all of
    them. A candidate who lists 3 cities gets Adzuna results biased to the
    first, and full multi-city coverage from whichever of Adzuna/SearXNG
    actually produces results after that."""
    preferences = state.get("preferences") or {}
    target_locations = preferences.get("target_locations") or []
    if target_locations:
        return target_locations[0]
    return state["candidate_json"].get("location") or ""


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

    # Merge with db_cache_module's contribution rather than starting from
    # scratch — a thin cache hit still counts, this just tops it up.
    existing_jobs: list[dict] = list(state.get("raw_jobs") or [])
    seen_urls: set[str] = {
        job["source_url"] for job in existing_jobs if job.get("source_url")
    }
    new_jobs: list[dict] = []

    def _total() -> int:
        return len(existing_jobs) + len(new_jobs)

    for query in queries:
        if _total() >= Cfg.MAX_JOB_URLS:
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
                new_jobs.append(entry)
            if _total() >= Cfg.MAX_JOB_URLS:
                break

    raw_jobs = existing_jobs + new_jobs
    state["raw_jobs"] = raw_jobs
    state["job_urls"] = list(seen_urls)
    state["used_adzuna"] = bool(new_jobs)

    logger.info(
        "Adzuna search complete: %d queries -> %d new jobs (%d carried over from DB "
        "cache, %d total)",
        len(queries), len(new_jobs), len(existing_jobs), len(raw_jobs),
    )
    if len(raw_jobs) < Cfg.MIN_JOBS_BEFORE_ACCEPTING:
        logger.info(
            "Still only %d/%d minimum after Adzuna — falling back to SearXNG + "
            "crawl4ai search_module/extraction_module to top up further.",
            len(raw_jobs), Cfg.MIN_JOBS_BEFORE_ACCEPTING,
        )

    state.setdefault("progress", []).append("adzuna_search_complete")
    return state
