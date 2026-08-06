"""LangGraph orchestration of the pipeline.

Each node checks `state["error"]` before doing real work, so a failure
in an earlier stage short-circuits the remaining stages instead of
raising. Ported from career-agent's app/pipeline/graph.py; the
`profile_ingest` node is dropped (see `internal/pipeline/state.py` —
the candidate already has an identity, `profile_id`, before this
pipeline runs, and `service.py` computes `candidate_embedding` once
before invoking the graph).
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from src.job_discovery_matching.internal.pipeline.nodes import (
    extraction_module,
    hard_filter,
    judge_module,
    matching_module,
    query_generator,
    search_module,
)
from src.job_discovery_matching.internal.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


def _guarded(name: str, fn):
    """Wrap a node so exceptions are captured into state["error"] instead of raised."""

    async def wrapped(state: PipelineState) -> PipelineState:
        if state.get("error"):
            return state
        try:
            return await fn(state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pipeline node %s failed", name)
            state["error"] = f"{name}: {exc}"
            return state

    return wrapped


def build_pipeline():
    graph = StateGraph(PipelineState)

    graph.add_node("query_generator", _guarded("query_generator", query_generator.run))
    graph.add_node("search_module", _guarded("search_module", search_module.run))
    graph.add_node("extraction_module", _guarded("extraction_module", extraction_module.run))
    graph.add_node("hard_filter", _guarded("hard_filter", hard_filter.run))
    graph.add_node("matching_module", _guarded("matching_module", matching_module.run))
    graph.add_node("judge_module", _guarded("judge_module", judge_module.run))

    graph.set_entry_point("query_generator")
    graph.add_edge("query_generator", "search_module")
    graph.add_edge("search_module", "extraction_module")
    graph.add_edge("extraction_module", "hard_filter")
    graph.add_edge("hard_filter", "matching_module")
    graph.add_edge("matching_module", "judge_module")
    graph.add_edge("judge_module", END)

    return graph.compile()


# Compiled once at import time and reused across requests.
pipeline = build_pipeline()
