"""promptfoo provider for the search + crawl parameter sweep eval.

No LLM calls happen anywhere in this file — search_module.py and
crawler_service.py never touch an LLM in production either, so this eval
costs zero tokens by construction. Each promptfoo "provider" entry in
search_crawl.promptfooconfig.yaml is one (max_results, crawl_concurrency,
crawl_timeout_ms, crawl_urls_limit) parameter combination; each "test" is
one search query. The Cartesian product lets promptfoo's table compare
parameter sets directly.

Two modes:
  - REAL: imports the actual app.services.searxng_client /
    crawler_service from ../../../backend and exercises the real
    SearXNG + Crawl4AI/Playwright stack. Requires running this from an
    environment with backend/requirements.txt installed and SearXNG
    reachable (e.g. inside `docker compose exec backend ...`, or a venv
    with SEARXNG_URL pointed at a running instance).
  - MOCK: used automatically if the real services can't be imported or
    SearXNG isn't reachable, or if EVAL_MOCK=1 is exported. Generates
    deterministic synthetic search/crawl results (seeded by query text)
    with simulated latency, so the eval harness itself, the assertions,
    and the aggregation script can all be validated with zero infra.
"""
import asyncio
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

EVAL_MOCK_FORCED = os.environ.get("EVAL_MOCK", "").lower() in ("1", "true", "yes")

# On the host, this repo looks like <root>/backend/app/... — 4 parents up
# from this file is <root>, so <root>/backend is the dir to add to
# sys.path. Inside the backend Docker container, the layout is flattened
# to /app/app/... (see backend/Dockerfile: WORKDIR /app, COPY app ./app),
# so /app itself is the equivalent of "backend/" on the host.
# CAREER_AGENT_BACKEND_DIR overrides both if neither guess is right.
_CANDIDATE_BACKEND_DIRS = [
    os.environ.get("CAREER_AGENT_BACKEND_DIR"),
    str(Path(__file__).resolve().parents[4] / "backend"),  # host layout
    "/app",  # in-container layout
]

_REAL_AVAILABLE = False
_searxng = None
_crawler = None
_import_errors = []

if not EVAL_MOCK_FORCED:
    for _candidate in _CANDIDATE_BACKEND_DIRS:
        if not _candidate or not Path(_candidate).is_dir():
            continue
        if _candidate not in sys.path:
            sys.path.insert(0, _candidate)
        try:
            from app.services import searxng_client as _searxng  # type: ignore
            from app.services import crawler_service as _crawler  # type: ignore
            _REAL_AVAILABLE = True
            break
        except Exception as exc:  # noqa: BLE001
            _import_errors.append(f"{_candidate}: {type(exc).__name__}: {exc}")
            sys.path.remove(_candidate)

    if not _REAL_AVAILABLE and os.environ.get("EVAL_DEBUG"):
        print("[search_crawl_provider] real import failed, falling back to mock:", file=sys.stderr)
        for line in _import_errors:
            print(f"  tried {line}", file=sys.stderr)


# --------------------------------------------------------------- mock mode --

def _seeded_rng(query: str) -> random.Random:
    seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


async def _mock_search(query: str, max_results: int) -> list[dict]:
    rng = _seeded_rng(query)
    await asyncio.sleep(0.05 + rng.random() * 0.15)  # simulate network latency
    n = rng.randint(max(2, max_results - 3), max_results)
    return [
        {"title": f"{query} result {i}", "url": f"https://mock-jobs.example/{abs(hash((query, i)))}", "content": ""}
        for i in range(n)
    ]


async def _mock_crawl(url: str, timeout_ms: int) -> dict | None:
    rng = _seeded_rng(url)
    latency = 0.2 + rng.random() * 0.8
    await asyncio.sleep(min(latency, timeout_ms / 1000))
    if rng.random() < 0.12:  # ~12% of pages "fail" to crawl, like real dead links
        return None
    return {"job_text": "x" * rng.randint(200, 2000), "job_json": {"title": "Mock Role"}}


# --------------------------------------------------------------- real mode --

async def _real_search(query: str, max_results: int) -> list[dict]:
    return await _searxng.search(query, max_results=max_results)


async def _real_crawl(url: str, timeout_ms: int) -> dict | None:
    # crawler_service's run config timeout is fixed at import time from
    # settings; per-call override isn't supported without editing the
    # service, so timeout_ms here is informational/enforced via wait_for.
    try:
        result = await asyncio.wait_for(_crawler.crawl_and_extract(url), timeout=timeout_ms / 1000)
    except asyncio.TimeoutError:
        return None
    return {"job_text": result.job_text, "job_json": result.job_json} if result else None


# ------------------------------------------------------------------- core --

async def _run(query: str, cfg: dict) -> dict:
    max_results = int(cfg.get("max_results", 8))
    crawl_urls_limit = int(cfg.get("crawl_urls_limit", 5))
    crawl_concurrency = int(cfg.get("crawl_concurrency", 3))
    crawl_timeout_ms = int(cfg.get("crawl_timeout_ms", 15000))

    use_real = _REAL_AVAILABLE and not EVAL_MOCK_FORCED
    search_fn = _real_search if use_real else _mock_search
    crawl_fn = _real_crawl if use_real else _mock_crawl

    t0 = time.perf_counter()
    results = await search_fn(query, max_results)
    search_latency_ms = (time.perf_counter() - t0) * 1000

    seen, urls = set(), []
    for r in results:
        u = r.get("url")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    urls_to_crawl = urls[:crawl_urls_limit]

    sem = asyncio.Semaphore(max(1, crawl_concurrency))

    async def _bounded_crawl(u):
        async with sem:
            return await crawl_fn(u, crawl_timeout_ms)

    t1 = time.perf_counter()
    crawl_results = await asyncio.gather(*[_bounded_crawl(u) for u in urls_to_crawl])
    crawl_latency_ms = (time.perf_counter() - t1) * 1000

    crawled_success = sum(1 for c in crawl_results if c)

    return {
        "query": query,
        "mode": "real" if use_real else "mock",
        "unique_urls_found": len(urls),
        "urls_attempted_crawl": len(urls_to_crawl),
        "crawled_success": crawled_success,
        "crawl_success_rate": round(crawled_success / len(urls_to_crawl), 3) if urls_to_crawl else 0.0,
        "search_latency_ms": round(search_latency_ms, 1),
        "crawl_latency_ms": round(crawl_latency_ms, 1),
        "total_latency_ms": round(search_latency_ms + crawl_latency_ms, 1),
        "params": {
            "max_results": max_results,
            "crawl_urls_limit": crawl_urls_limit,
            "crawl_concurrency": crawl_concurrency,
            "crawl_timeout_ms": crawl_timeout_ms,
        },
    }


def call_api(prompt: str, options: dict, context: dict) -> dict:
    cfg = (options or {}).get("config", {}) or {}
    query = (context.get("vars") or {}).get("query") or prompt.strip()
    try:
        result = asyncio.run(_run(query, cfg))
        return {"output": json.dumps(result), "metadata": result}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
