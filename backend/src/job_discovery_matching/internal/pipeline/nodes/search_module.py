

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.nodes.hard_filter import (
    _passes_location,
    _passes_salary,
)
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.services import searxng_client
from src.core.db import get_session_factory
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
logger = logging.getLogger(__name__)

_NON_VACANCY_TERMS = (
    "salary",
    "resume example",
    "resume tips",
    "tutorial",
    "roadmap",
    "job description template",
    "job description",
    "what is",
    "how to become",
    "skills a senior",
    "course",
)
_VACANCY_PATH_TERMS = ("/jobs/", "/job/", "/careers/", "/career/", "/candidate/")
_VACANCY_TEXT_TERMS = ("apply", "hiring", "vacancy", "opening", "position")


def _looks_like_vacancy(result: dict) -> bool:
    title = (result.get("title") or "").lower()
    content = (result.get("content") or "").lower()
    path = urlparse(result.get("url") or "").path.lower()
    if any(term in title or term in path for term in _NON_VACANCY_TERMS):
        return False
    return any(term in path for term in _VACANCY_PATH_TERMS) or any(
        term in f"{title} {content}" for term in _VACANCY_TEXT_TERMS
    )


def _job_query(query: str) -> str:
    lowered = query.lower()
    return query if "job" in lowered or "hiring" in lowered else f"{query} jobs hiring"


def _is_direct_vacancy(result: dict) -> bool:
    parsed = urlparse(result.get("url") or "")
    path = parsed.path.lower()
    title = (result.get("title") or "").lower()
    # Broadened after a real miss: only matched "N+ ... jobs" (count
    # BEFORE the word). "Information Technology Jobs in Chennai (1,000+
    # Open Roles)" puts the count in a trailing parenthetical instead —
    # same listing page, missed by the narrower pattern. Same regex now
    # reused in judge_module.py's deterministic is_real_vacancy backstop.
    if (
        re.search(r"\b\d[\d,]*\+?\s+.*\bjobs?\b", title)
        or re.search(r"\(\s*\d[\d,]*\+?\s*(?:open\s+)?(?:roles?|jobs?|positions?|openings?)\s*\)", title)
        or "job vacancies" in title
    ):
        return False
    # Was `[^/]*\d[^/]*` — only matched a numeric ID in the path segment
    # immediately after /jobs//careers/ (e.g. "/jobs/12345"). Real postings
    # that put the ID at the END of a slug instead (e.g. Shine.com:
    # "/jobs/full-stack-developer-java/.../19195704") never matched, so
    # they got bucketed as "listing" filler instead of "direct" — lower
    # priority than a real generic search-results page, which is backwards.
    has_identifier = bool(re.search(r"/(?:jobs?|careers?)/.*\d", path))
    is_application = "/candidate/" in path and bool(parsed.query)
    is_job_view = "/jobs/view/" in path or "/job/" in path
    return has_identifier or is_application or is_job_view


async def run(state: PipelineState) -> PipelineState:
    queries = state["search_queries"]

    seen_urls: set[str] = set()
    direct_urls: list[str] = []
    listing_urls: list[str] = []

    for query in queries:
        results = await searxng_client.search(_job_query(query), max_results=10)
        for r in filter(_looks_like_vacancy, results):
            url = r["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            target = direct_urls if _is_direct_vacancy(r) else listing_urls
            target.append(url)

    # Was capped at Cfg.TOP_N_JUDGED (5 total) — that's how many get
    # JUDGED, not how many are worth CRAWLING. With only 5 candidates to
    # begin with, a couple of listing pages (is_real_vacancy=False, see
    # hard_filter.py) could wipe out most of a run's real yield. Crawling
    # up to the full MAX_JOB_URLS instead gives hard_filter and the judge
    # a much wider pool to actually find real postings in — costs more
    # crawl time per run, which is the right tradeoff for a pre-warm run
    # feeding the cache, not something a live-in-front-of-people run
    # should ever be doing cold anyway.
    if len(direct_urls) >= Cfg.MAX_JOB_URLS:
        job_urls = direct_urls[: Cfg.MAX_JOB_URLS]
    else:
        fallback_count = Cfg.MAX_JOB_URLS - len(direct_urls)
        job_urls = direct_urls + listing_urls[:fallback_count]
    state["job_urls"] = job_urls
    logger.info(
        "Search complete: %d queries -> %d direct vacancies, %d listing fallbacks, %d selected",
        len(queries),
        len(direct_urls),
        len(listing_urls),
        len(job_urls),
    )
    if not job_urls:
        logger.warning(
            "Zero job URLs found across all %d queries: %s. Falling back to "
            "the stored posting corpus.",
            len(queries), queries,
        )
        candidate = state["candidate_json"]
        preferences = state.get("preferences") or {}

        async with get_session_factory()() as session:
            repo = JobDiscoveryRepository(session)
            # Pull a wider pool than MAX_JOB_URLS since most of it is about
            # to be discarded by the same location/salary check hard_filter
            # itself would apply — recent-but-irrelevant is not a
            # replacement for irrelevant, no matter how recent. Same
            # DB_CACHE_POOL_SIZE knob db_cache_module pulls from, since
            # this is functionally the same kind of query (shared, cross-
            # user table, no embedding similarity available here since
            # SearXNG never ran and this is a last resort, not a ranked
            # candidate pool).
            cached = await repo.find_recent_postings(limit=Cfg.DB_CACHE_POOL_SIZE)

        matched = [
            posting for posting in cached
            if _passes_location(candidate, posting.job_json, posting.job_text, preferences)
            and _passes_salary(posting.job_json, posting.job_text, preferences)
        ]

        job_urls = [posting.source_url for posting in matched[: Cfg.MAX_JOB_URLS]]
        state["job_urls"] = job_urls
        state["used_cached_postings"] = bool(job_urls)
        logger.info(
            "Recovered %d/%d stored postings matching location/salary preferences "
            "(of %d checked) from the stored corpus",
            len(job_urls), len(matched), len(cached),
        )

    state.setdefault("progress", []).append("search_complete")
    return state