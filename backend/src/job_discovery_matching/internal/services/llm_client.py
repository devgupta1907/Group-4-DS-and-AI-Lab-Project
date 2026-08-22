"""Two LLM calls, total, per pipeline run: query generation and the
batched judge. Both go through `src.services.llm_client.llm` — the same
`ChatGoogleGenerativeAI` instance career_recommendation's re_ranker.py
already uses — via LangChain's `.with_structured_output()`, rather than
career-agent's original approach of a raw OpenRouter HTTP call plus
manual JSON-fence stripping. This means:

  * no second LLM provider / no second required API key
    (GOOGLE_AI_STUDIO / GOOGLE_API_KEY already configures both), and
  * no hand-rolled JSON parsing — the structured-output schema below
    IS the response contract, and LangChain handles the retry/repair
    that career-agent's `_JSON_RETRY_SUFFIX` did by hand.

`llm.invoke()` is synchronous; both callers run it via `asyncio.to_thread`
so a slow LLM call doesn't block the event loop the rest of the pipeline
(crawling, SearXNG) shares.
"""

from __future__ import annotations

import asyncio
import logging

from pydantic import BaseModel, Field

from src.job_discovery_matching.internal.pipeline.prompts import (
    JUDGE_BATCH_SYSTEM,
    JUDGE_BATCH_USER,
    QUERY_GENERATOR_SYSTEM,
    QUERY_GENERATOR_USER,
)
from src.services.llm_client import llm

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class _SearchQueries(BaseModel):
    queries: list[str] = Field(description="Diverse job-search queries for this candidate.")


class JudgedJob(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    is_remote: bool = False
    required_skills: list[str] = Field(default_factory=list)
    interview_probability: int = 0
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendation: str = "Skip"
    one_line_reason: str = ""


class _JudgeBatch(BaseModel):
    jobs: list[JudgedJob] = Field(description="One entry per job, in the same order given.")


async def generate_search_queries(
    candidate_json: dict, num_queries: int, preferences: dict | None = None
) -> list[str]:
    """candidate_json -> up to `num_queries` search query strings. Raises
    LLMError on failure; the caller (query_generator node) decides the
    heuristic fallback, not this function.

    `target_roles` and `skills` are pulled out and passed as their own
    template variables, not left for the model to notice inside the raw
    candidate_json dump — otherwise it anchors on whichever field is
    loudest (usually candidate_json["current_role"]) and every "diverse"
    query ends up being a rephrase of just that one role.

    `preferences` (SearchPreferences.model_dump()) is optional so existing
    callers that don't pass it still work; `target_location`/`remote_only`
    get baked into the generated query text itself — not just applied as
    a post-hoc filter in hard_filter.py — so the search engine is actually
    asked for jobs in the right place instead of everywhere."""
    target_roles = candidate_json.get("target_roles") or []
    skills = candidate_json.get("skills") or []
    prefs = preferences or {}
    target_location = prefs.get("target_location") or "(none given)"
    remote_only = bool(prefs.get("remote_only"))
    min_salary_lpa = prefs.get("min_salary_lpa")
    min_salary_text = f"{min_salary_lpa} LPA" if min_salary_lpa else "(none given)"
    prompt = (
        f"{QUERY_GENERATOR_SYSTEM}\n\n"
        + QUERY_GENERATOR_USER.format(
            num_queries=num_queries,
            candidate_target_roles=target_roles or ["(none listed — infer from candidate profile below)"],
            candidate_skills=skills[:15] or ["(none listed — infer from candidate profile below)"],
            target_location=target_location,
            remote_only=remote_only,
            min_salary_lpa=min_salary_text,
            candidate_json=candidate_json,
        )
    )
    try:
        structured = llm.with_structured_output(_SearchQueries)
        result = await asyncio.to_thread(structured.invoke, prompt)
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"Query generation failed: {exc}") from exc

    queries = [str(q) for q in (result.queries or [])][:num_queries]
    if not queries:
        raise LLMError("Query generation returned no queries.")
    return queries


async def judge_batch(candidate_json: dict, jobs_block: str, num_jobs: int) -> list[JudgedJob]:
    """candidate_json + rendered job texts -> one JudgedJob per job, in
    the same order. Raises LLMError on failure; the caller (judge_module
    node) falls back to hybrid-score-only ranking, not this function."""
    prompt = (
        f"{JUDGE_BATCH_SYSTEM}\n\n"
        + JUDGE_BATCH_USER.format(
            candidate_json=candidate_json,
            num_jobs=num_jobs,
            last_index=num_jobs - 1,
            jobs_block=jobs_block,
        )
    )
    try:
        structured = llm.with_structured_output(_JudgeBatch)
        result = await asyncio.to_thread(structured.invoke, prompt)
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"Batched judge call failed: {exc}") from exc

    if not result.jobs:
        raise LLMError("Judge call returned an empty jobs array.")
    return result.jobs
