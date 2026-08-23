"""Node 3 — Extraction Module: job_urls[] -> raw_jobs[].

Zero LLM calls. For each URL: reuse a fresh `job_discovery_postings` row
if one exists (see `internal.repository.get_fresh_posting`), otherwise
crawl it (crawl4ai + JSON-LD, see `internal.services.crawler_service`),
embed the extracted text, and upsert the cache row. The cache is shared
across ALL users/runs — the same job posting is never re-crawled or
re-embedded twice within `Cfg.POSTING_CACHE_TTL_HOURS`.

Last resort in the source cascade (db_cache -> adzuna -> this), so
unlike those two there's no further fallback to route to afterward —
whatever comes out of here is final, `graph.py` sends it straight to
`hard_filter` unconditionally. Still MERGES with whatever db_cache_module
/ adzuna_search_module already contributed rather than overwriting it,
for the same reason those two merge with each other.
"""

from __future__ import annotations

import asyncio
import logging

from src.core.db import get_session_factory
from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
from src.job_discovery_matching.internal.services import crawler_service
from src.job_discovery_matching.internal.services.embedding_client import embed_documents

logger = logging.getLogger(__name__)


def _job_text_for_embedding(job_json: dict, job_text: str) -> str:
    return " ".join(
        [
            job_json.get("title", "") or "",
            " ".join(job_json.get("required_skills", []) or []),
            job_json.get("description", "") or job_text[:1000],
        ]
    ).strip()


async def _fetch_one(url: str, semaphore: asyncio.Semaphore) -> dict | None:

    async with semaphore:
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

        extracted = await crawler_service.crawl_and_extract(url)

    if extracted is None:
        return None

    embedding_text = _job_text_for_embedding(extracted.job_json, extracted.job_text)
    [embedding] = embed_documents([embedding_text[:4000] or extracted.job_json.get("title", "") or url])

    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        posting = await repo.upsert_posting(
            url=url,
            job_json=extracted.job_json,
            job_text=extracted.job_text,
            embedding=embedding,
        )

    return {
        "posting_id": posting.id,
        "job_json": extracted.job_json,
        "job_text": extracted.job_text,
        "embedding": embedding,
        "source_url": url,
    }


async def run(state: PipelineState) -> PipelineState:
    existing_jobs: list[dict] = list(state.get("raw_jobs") or [])
    existing_urls = {job["source_url"] for job in existing_jobs if job.get("source_url")}

    urls = [u for u in state["job_urls"] if u not in existing_urls]
    semaphore = asyncio.Semaphore(Cfg.CRAWL_CONCURRENCY)

    results = await asyncio.gather(*(_fetch_one(url, semaphore) for url in urls))
    new_jobs = [r for r in results if r is not None]

    raw_jobs = (existing_jobs + new_jobs)[: Cfg.MAX_JOB_URLS]
    state["raw_jobs"] = raw_jobs
    logger.info(
        "Extraction complete: %d URLs crawled -> %d new jobs (%d carried over from "
        "DB cache/Adzuna, %d total)",
        len(urls), len(new_jobs), len(existing_jobs), len(raw_jobs),
    )
    state.setdefault("progress", []).append("extraction_complete")
    return state
