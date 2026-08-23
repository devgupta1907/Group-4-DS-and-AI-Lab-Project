"""Node 3 — Extraction Module: job_urls[] -> raw_jobs[].

Zero LLM calls. For each URL: reuse a fresh `job_discovery_postings` row
if one exists (see `internal.repository.get_fresh_posting`), otherwise
crawl it (crawl4ai + JSON-LD, see `internal.services.crawler_service`),
embed the extracted text, and upsert the cache row. The cache is shared
across ALL users/runs — the same job posting is never re-crawled or
re-embedded twice within `Cfg.POSTING_CACHE_TTL_HOURS`.
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
    urls = state["job_urls"]
    semaphore = asyncio.Semaphore(Cfg.CRAWL_CONCURRENCY)

    results = await asyncio.gather(*(_fetch_one(url, semaphore) for url in urls))

    state["raw_jobs"] = [r for r in results if r is not None]
    state.setdefault("progress", []).append("extraction_complete")
    return state
