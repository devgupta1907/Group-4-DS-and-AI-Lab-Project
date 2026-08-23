"""Node 1 — Query Generator: candidate_json -> search_queries[].

1 LLM call (structured output via src/services/llm_client.py). On
failure, falls back to a single heuristic query built from the
candidate's current role / top skills, so the pipeline still produces
*something* rather than dead-ending here.
"""

from __future__ import annotations

import logging

from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.services.llm_client import LLMError, generate_search_queries

logger = logging.getLogger(__name__)


def _heuristic_query(candidate: dict, preferences: dict | None = None) -> str:
    role = candidate.get("current_role") or (candidate.get("target_roles") or [None])[0]
    base = f"{role} jobs" if role else None
    if base is None:
        skills = candidate.get("skills") or []
        base = " ".join(skills[:3]) + " jobs" if skills else "jobs"

    prefs = preferences or {}
    if prefs.get("remote_only"):
        return f"{base} remote"
    target_location = prefs.get("target_location")
    if target_location:
        return f"{base} in {target_location}"
    return base


async def run(state: PipelineState) -> PipelineState:
    candidate_json = state["candidate_json"]
    preferences = state.get("preferences") or {}

    try:
        queries = await generate_search_queries(
            candidate_json, Cfg.NUM_SEARCH_QUERIES, preferences=preferences
        )
    except LLMError as exc:
        logger.warning("Query generator LLM call failed, falling back to a heuristic query: %s", exc)
        queries = [_heuristic_query(candidate_json, preferences)]

    state["search_queries"] = queries
    state.setdefault("progress", []).append("queries_generated")
    return state
