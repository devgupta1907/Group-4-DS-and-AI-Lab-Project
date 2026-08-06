"""Job Discovery & Matching — module configuration.

Reuses the same embedding model/provider and the same Gemini LLM config
as career_recommendation (src.core.config.GlobalConfig) rather than
introducing a second embedding model or a second required LLM API key.
Only SearXNG is genuinely new infrastructure for this module.
"""

from __future__ import annotations

import os

from src.core.config import GlobalConfig


class JobDiscoveryModuleConfig:
    """Constants and env-backed settings specific to this module."""

    # --- search (SearXNG) ---
    SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")
    SEARXNG_TIMEOUT_SECONDS = 100000

    # --- crawling (crawl4ai) — zero LLM calls, see internal/services/crawler_service.py ---
    CRAWL_CONCURRENCY = int(os.getenv("JOB_DISCOVERY_CRAWL_CONCURRENCY", "3"))
    CRAWL_TIMEOUT_MS = int(os.getenv("JOB_DISCOVERY_CRAWL_TIMEOUT_MS", "15000"))

    # A cached posting (job_discovery_postings row) is reused rather than
    # re-crawled within this window, shared across ALL users/runs.
    POSTING_CACHE_TTL_HOURS = int(os.getenv("JOB_DISCOVERY_CACHE_TTL_HOURS", "24"))

    # --- pipeline limits ---
    NUM_SEARCH_QUERIES = 6      # candidate profile -> N queries, 1 LLM call
    MAX_JOB_URLS = 20           # fewer URLs = fewer crawl4ai fetches per run
    TOP_K_RANKED = 15           # kept after BM25 + embedding hybrid ranking
    TOP_N_JUDGED = 5            # judged in a SINGLE batched LLM call

    # --- hybrid ranking weights ---
    BM25_WEIGHT = 0.4
    EMBEDDING_WEIGHT = 0.3
    HYBRID_WEIGHT = 0.8          # how much the pre-judge hybrid score counts...
    JUDGE_WEIGHT = 0.2           # ...vs the judge's interview_probability, in final_score

    # --- embeddings — same local bi-encoder career_recommendation uses ---
    EMBEDDING_PROVIDER = GlobalConfig.EMBEDDING_PROVIDER
    EMBEDDING_MODEL = GlobalConfig.HF_EMBEDDING_MODEL  # BAAI/bge-base-en-v1.5
    EMBEDDING_DIM = GlobalConfig.EMBEDDING_DIM

    # --- LLM (query generation + judge) ---
    # Reuses the Gemini key career_recommendation/resume_parsing already
    # require (GlobalConfig.GOOGLE_API_KEY), so no new API key is needed.
    LLM_MODEL = os.getenv("JOB_DISCOVERY_LLM_MODEL", GlobalConfig.LLM_MODEL)
    JUDGE_TEXT_CHAR_LIMIT = 3000  # how much pruned JD text feeds the judge call, per job
