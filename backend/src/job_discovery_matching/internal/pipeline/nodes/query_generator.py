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


def _heuristic_query(candidate: dict) -> str:
    role = candidate.get("current_role") or (candidate.get("target_roles") or [None])[0]
    if role:
        return f"{role} jobs"
    skills = candidate.get("skills") or []
    if skills:
        return " ".join(skills[:3]) + " jobs"
    return "jobs"


async def run(state: PipelineState) -> PipelineState:
    candidate_json = state["candidate_json"]

    try:
        queries = await generate_search_queries(candidate_json, Cfg.NUM_SEARCH_QUERIES)
    except LLMError as exc:
        logger.warning("Query generator LLM call failed, falling back to a heuristic query: %s", exc)
        queries = [_heuristic_query(candidate_json)]

    state["search_queries"] = queries
    state.setdefault("progress", []).append("queries_generated")
    return state
