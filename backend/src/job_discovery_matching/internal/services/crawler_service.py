"""Crawl4AI-backed page fetching + zero-LLM job metadata extraction.

Ported near-verbatim from career-agent's app/services/crawler_service.py.
This is the ONLY thing in the module that touches job board URLs, and it
never calls an LLM. Two zero-cost signal sources are tried, in order:

  1. schema.org JobPosting JSON-LD — most large job boards embed this
     directly in <head>. When present it gives clean
     title/company/location for free.
  2. Page metadata fallback — <title>, og:site_name, and a "remote"
     keyword check — used when JSON-LD isn't present.

Either way, Crawl4AI's *pruned* markdown (nav/ads/footer already
stripped) is also returned as `job_text`, which is what BM25 + embeddings
rank against, and what the judge module later reads for the jobs that
make the final shortlist. Whether a given (url -> result) pair needs to
be crawled at all — vs. served from the `job_discovery_postings` cache —
is decided by the caller (extraction_module.py), not here.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import json
import logging
import re
import sys
import threading
from dataclasses import dataclass

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg

logger = logging.getLogger(__name__)

# Standard Docker-safe Chromium flags. Without these, headless Chromium
# frequently crashes inside containers (sandbox restrictions + small
# /dev/shm) — that crash surfaces as Playwright's "Target page, context
# or browser has been closed", which kills every other in-flight crawl
# sharing the browser.
_DOCKER_CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]

_browser_config = BrowserConfig(
    browser_type="chromium",
    headless=True,
    verbose=False,
    extra_args=_DOCKER_CHROMIUM_ARGS,
)

_run_config = CrawlerRunConfig(
    cache_mode=CacheMode.ENABLED,
    markdown_generator=DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.45, threshold_type="dynamic")
    ),
    page_timeout=Cfg.CRAWL_TIMEOUT_MS,
)

_loop: asyncio.AbstractEventLoop | None = None
_loop_init_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _loop_init_lock:
        if _loop is not None and _loop.is_running():
            return _loop
        _loop = (
            asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        )
        threading.Thread(target=_loop.run_forever, name="crawler-loop", daemon=True).start()
        return _loop


async def _on_crawler_loop(coro):
    """Run a coroutine on the private crawler loop, awaited from any loop."""
    return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, _ensure_loop()))

_crawler: AsyncWebCrawler | None = None
_crawler_lock = asyncio.Lock()


async def _get_crawler() -> AsyncWebCrawler:
    """Lazily start one shared headless-browser instance for the process.

    Lock-protected so two concurrent extraction tasks can't both see
    `_crawler is None` and launch two separate browsers at once.
    """
    global _crawler
    async with _crawler_lock:
        # print("Inside get_crawler")
        if _crawler is None:
            # print("Creating crawler")
            _crawler = AsyncWebCrawler(config=_browser_config)
            # print("Crawler created")
            await _crawler.__aenter__()
        
    return _crawler


async def _close_crawler()-> None:
    """Call on app shutdown to cleanly tear down the browser."""
    global _crawler
    async with _crawler_lock:
        if _crawler is not None:
            try:
                await _crawler.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001 - already dead, nothing to clean up
                pass
            _crawler = None


async def _reset_crawler_inner() -> None:
    """Force-recreate the shared browser after a crash, so remaining URLs
    in the batch don't all fail behind a dead browser process."""
    global _crawler
    async with _crawler_lock:
        if _crawler is not None:
            try:
                await _crawler.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            _crawler = None
            
async def close_crawler() -> None:
    """Call on app shutdown to cleanly tear down the browser."""
    await _on_crawler_loop(_close_crawler())

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)
_OG_SITE_NAME_RE = re.compile(
    r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']*)["\']', re.IGNORECASE
)


_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^<]+?>")
_BLANK_LINES_RE = re.compile(r"\n\s*\n+")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")


def _clean_text(text: str) -> str:
    """Shared cleaner for anything that ends up as `job_text` or
    `job_json["description"]` — both the judge LLM prompt (judge_module.py)
    and BM25 scoring (matching_module.py) read this field directly, so any
    HTML/entity noise left in here is wasted tokens for the judge AND
    diluted keyword signal for BM25. Handles three failure modes seen in
    practice: script/style block bodies surviving Crawl4AI's pruning filter
    (the old regex only removed tags, not their content), literal HTML
    entities (&amp;, &nbsp;, ...) left un-decoded, and the run of blank
    lines/repeated whitespace that both raw HTML-to-text and markdown
    conversion tend to leave behind."""
    if not text:
        return ""
    cleaned = _SCRIPT_STYLE_RE.sub(" ", text)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = html_lib.unescape(cleaned)
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


# Old name kept as an alias — _extract_jsonld_job/_map_jsonld below only
# ever needed tag-stripping for JSON-LD's already-plain-ish description
# field, but route it through the same stronger cleaner now.
_strip_html = _clean_text


def _extract_jsonld_job(html: str) -> dict | None:
    """Best-effort zero-LLM extraction from schema.org JobPosting JSON-LD."""
    for match in _JSONLD_RE.finditer(html):
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue

        for candidate in data if isinstance(data, list) else [data]:
            if not isinstance(candidate, dict):
                continue
            types = candidate.get("@type", "")
            types = types if isinstance(types, list) else [types]
            if "JobPosting" not in types:
                continue
            return _map_jsonld(candidate)
    return None


def _map_jsonld(ld: dict) -> dict:
    org = ld.get("hiringOrganization") or {}
    location = ld.get("jobLocation") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    address = (location or {}).get("address") or {}

    employment_type = ld.get("employmentType") or ""
    if isinstance(employment_type, list):
        employment_type = employment_type[0] if employment_type else ""

    return {
        "title": ld.get("title") or "",
        "company": org.get("name") if isinstance(org, dict) else "",
        "location": ", ".join(
            filter(None, [address.get("addressLocality"), address.get("addressRegion")])
        )
        if isinstance(address, dict)
        else "",
        "is_remote": bool(ld.get("jobLocationType") == "TELECOMMUTE"),
        "employment_type": employment_type,
        "description": _strip_html(ld.get("description") or "")[:4000],
        "required_skills": [],
        "extraction_method": "jsonld",
    }


def _extract_page_metadata(html: str, fit_markdown: str) -> dict:
    """Crude, zero-LLM fallback when no JSON-LD is present."""
    title_match = _TITLE_TAG_RE.search(html)
    site_match = _OG_SITE_NAME_RE.search(html)
    text_lower = (fit_markdown or "").lower()

    return {
        "title": _strip_html(title_match.group(1)) if title_match else "",
        "company": site_match.group(1).strip() if site_match else "",
        "location": "",
        "is_remote": "remote" in text_lower[:2000],
        "employment_type": "",
        "description": _clean_text(fit_markdown)[:4000],
        "required_skills": [],
        "extraction_method": "metadata_fallback",
    }


@dataclass
class ExtractedJob:
    job_json: dict
    job_text: str


_CRASH_SIGNATURE = "has been closed"


async def crawl_and_extract(url: str) -> ExtractedJob | None:
    """Fetch a URL and return (crude/JSON-LD job_json, pruned job_text).

    Returns None if the page couldn't be fetched or had negligible
    content. No LLM call happens in this function. If the shared browser
    has crashed, it's relaunched once and the fetch is retried.
    """
    async def _fetch():
        # Runs entirely on the crawler loop: the browser must be created
        # and used on the same loop, so the retry lives in here too.
        for attempt in range(2):
            crawler = await _get_crawler()
            try:
                return await crawler.arun(url=url, config=_run_config)
            except Exception as exc:  # noqa: BLE001
                if _CRASH_SIGNATURE in str(exc) and attempt == 0:
                    logger.warning("Crawl4AI browser crashed, relaunching and retrying %s", url)
                    await _reset_crawler_inner()
                    continue
                logger.warning("Crawl4AI failed for %s: %s", url, exc)
                return None
        return None

    result = await _on_crawler_loop(_fetch())

    if not result or not result.success:
        return None

    fit_markdown = ""
    if result.markdown:
        fit_markdown = getattr(result.markdown, "fit_markdown", None) or str(result.markdown)

    if not fit_markdown or len(fit_markdown) < 100:
        return None

    html = result.html or ""
    job_json = _extract_jsonld_job(html) if html else None
    if not job_json or not job_json.get("title"):
        job_json = _extract_page_metadata(html, fit_markdown)

    job_json["source_url"] = url
    # `job_text` is what BM25 (matching_module.py) scores against AND what
    # the judge LLM prompt (judge_module.py) reads verbatim — clean it here
    # too, not just job_json["description"], since Crawl4AI's pruning
    # filter doesn't guarantee tag-free markdown on every page (tables,
    # embedded widgets, and script/style remnants have all been observed
    # leaking through on real job board pages).
    clean_job_text = _clean_text(fit_markdown)
    return ExtractedJob(job_json=job_json, job_text=clean_job_text or fit_markdown)
