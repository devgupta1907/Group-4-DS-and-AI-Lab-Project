"""LangGraph orchestration of the pipeline.

Each node checks `state["error"]` before doing real work, so a failure
in an earlier stage short-circuits the remaining stages instead of
raising. Ported from career-agent's app/pipeline/graph.py; the
`profile_ingest` node is dropped (see `internal/pipeline/state.py` —
the candidate already has an identity, `profile_id`, before this
pipeline runs, and `service.py` computes `candidate_embedding` once
before invoking the graph).

Search source order, cheapest/fastest first:

  1. db_cache_module  — Postgres only, no external call at all. Reuses a
     fresh (<= DB_CACHE_MAX_AGE_HOURS old), semantically similar posting
     already sitting in job_discovery_postings from ANY previous run.
  2. adzuna_module     — one structured API call per query. Only runs if
     step 1 found nothing.
  3. search_module +
     extraction_module — SearXNG (web search) + crawl4ai (actual page
     fetch). Only runs if step 2 ALSO found nothing. Most expensive path,
     kept as the last resort.

i.e. exactly: DB match -> use it; elif Adzuna has results -> use those;
else -> search + crawl.

Two human checkpoints, both via `interrupt()` (langgraph.types), both
requiring the Postgres checkpointer below to survive across separate
HTTP requests:

  1. query_selection_gate — right after query_generator, before any
     external call (Adzuna/SearXNG/crawl4ai) is spent. User picks which
     generated queries to actually search.
  2. judge_confirmation_gate — right after hybrid ranking is computed
     AND persisted (rank_persist_module), before the LLM judge call.
     User sees real ranked jobs and decides whether the judge stage
     (this pipeline's second and last LLM call) is worth running.
     proceed=True -> judge_module -> END. proceed=False ->
     hybrid_finalize_module -> END (same final_jobs[] shape, judge=None).
"""

from __future__ import annotations

import logging
import time

from langgraph.errors import GraphInterrupt
from langgraph.graph import END, StateGraph

from src.job_discovery_matching.internal.pipeline.checkpointer import get_checkpointer
from src.job_discovery_matching.internal.pipeline.nodes import (
    adzuna_search_module,
    db_cache_module,
    extraction_module,
    hard_filter,
    hybrid_finalize_module,
    judge_confirmation_gate,
    judge_module,
    matching_module,
    query_generator,
    query_selection_gate,
    rank_persist_module,
    search_module,
)
from src.job_discovery_matching.internal.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


def _guarded(name: str, fn):
    """Wrap a node so exceptions are captured into state["error"] instead of
    raised, and every node's wall-clock time is logged/recorded in
    state["node_timings"] (see previous docstring content for the shape).

    CRITICAL: `GraphInterrupt` (raised by `interrupt()` inside
    query_selection_gate.py AND judge_confirmation_gate.py) must NOT be
    caught here — it's LangGraph's own control-flow signal for "pause the
    graph and return to the caller," not a real failure. Catching it as a
    broad `except Exception` would turn every pause into a hard pipeline
    error instead."""

    async def wrapped(state: PipelineState) -> PipelineState:
        timings = state.setdefault("node_timings", [])

        if state.get("error"):
            timings.append({"node": name, "duration_ms": 0.0, "status": "skipped"})
            return state

        start = time.perf_counter()
        try:
            result = await fn(state)
            status = "error" if result.get("error") else "ok"
            return result
        except GraphInterrupt:
            status = "interrupted"
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pipeline node %s failed", name)
            state["error"] = f"{name}: {exc}"
            status = "exception"
            return state
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            timings.append({"node": name, "duration_ms": duration_ms, "status": status})
            logger.info("Node %-18s took %8.1f ms [%s]", name, duration_ms, status)

    return wrapped


def route_after_db_cache(state: PipelineState) -> str:
    """DB cache produced jobs (or errored) -> skip straight to hard_filter.
    Nothing in the DB cache cleared the similarity/freshness bar -> try
    Adzuna next."""
    if state.get("error"):
        return "hard_filter"
    if state.get("raw_jobs"):
        return "hard_filter"
    return "adzuna_module"


def route_after_adzuna(state: PipelineState) -> str:
    """Adzuna produced jobs (or the node errored) -> skip straight to
    hard_filter. Adzuna came back empty -> fall back to the SearXNG +
    crawl4ai path (search_module -> extraction_module)."""
    if state.get("error"):
        # Let the already-set error short-circuit the fallback nodes too,
        # rather than re-entering a path that will also just no-op.
        return "hard_filter"
    if state.get("raw_jobs"):
        return "hard_filter"
    return "search_module"


def route_after_judge_confirmation(state: PipelineState) -> str:
    """User (or the empty-ranked_jobs shortcut in judge_confirmation_gate
    itself) said proceed -> judge_module (spends the LLM call). Anything
    else, including an error, -> hybrid_finalize_module — cheap, no LLM
    call, just reshapes ranked_jobs into final_jobs."""
    error = state.get("error")
    proceed = state.get("proceed_to_judge")
    logger.info(
        "route_after_judge_confirmation: error=%r proceed_to_judge=%r -> %s",
        error, proceed, "hybrid_finalize_module" if (error or not proceed) else "judge_module",
    )
    if error:
        return "hybrid_finalize_module"
    if proceed:
        return "judge_module"
    return "hybrid_finalize_module"


def build_pipeline(checkpointer=None):
    """`checkpointer` is required in production (see
    `internal/pipeline/checkpointer.py`) — without one, `interrupt()` in
    query_selection_gate.py / judge_confirmation_gate.py has nowhere to
    persist state, and resuming from a later, separate HTTP request will
    fail. Left optional here only so plain unit tests can compile/exercise
    the graph without a live Postgres connection."""
    graph = StateGraph(PipelineState)

    graph.add_node("query_generator", _guarded("query_generator", query_generator.run))
    graph.add_node("query_selection_gate", _guarded("query_selection_gate", query_selection_gate.run))
    graph.add_node("db_cache_module", _guarded("db_cache_module", db_cache_module.run))
    graph.add_node("adzuna_module", _guarded("adzuna_module", adzuna_search_module.run))
    graph.add_node("search_module", _guarded("search_module", search_module.run))
    graph.add_node("extraction_module", _guarded("extraction_module", extraction_module.run))
    graph.add_node("hard_filter", _guarded("hard_filter", hard_filter.run))
    graph.add_node("matching_module", _guarded("matching_module", matching_module.run))
    graph.add_node("rank_persist_module", _guarded("rank_persist_module", rank_persist_module.run))
    graph.add_node(
        "judge_confirmation_gate", _guarded("judge_confirmation_gate", judge_confirmation_gate.run)
    )
    graph.add_node("judge_module", _guarded("judge_module", judge_module.run))
    graph.add_node("hybrid_finalize_module", _guarded("hybrid_finalize_module", hybrid_finalize_module.run))

    graph.set_entry_point("query_generator")
    graph.add_edge("query_generator", "query_selection_gate")
    graph.add_edge("query_selection_gate", "db_cache_module")
    graph.add_conditional_edges(
        "db_cache_module",
        route_after_db_cache,
        {"hard_filter": "hard_filter", "adzuna_module": "adzuna_module"},
    )
    graph.add_conditional_edges(
        "adzuna_module",
        route_after_adzuna,
        {"hard_filter": "hard_filter", "search_module": "search_module"},
    )
    graph.add_edge("search_module", "extraction_module")
    graph.add_edge("extraction_module", "hard_filter")
    graph.add_edge("hard_filter", "matching_module")
    graph.add_edge("matching_module", "rank_persist_module")
    graph.add_edge("rank_persist_module", "judge_confirmation_gate")
    graph.add_conditional_edges(
        "judge_confirmation_gate",
        route_after_judge_confirmation,
        {"judge_module": "judge_module", "hybrid_finalize_module": "hybrid_finalize_module"},
    )
    graph.add_edge("judge_module", END)
    graph.add_edge("hybrid_finalize_module", END)

    return graph.compile(checkpointer=checkpointer)


# Compiled lazily, once, on first real use — NOT at import time, because
# attaching the Postgres checkpointer requires opening an async connection
# pool (internal/pipeline/checkpointer.py), which can't happen at plain
# module-import time. `service.py` calls `await get_pipeline()` rather than
# importing a `pipeline` global directly.
_pipeline = None


async def get_pipeline():
    global _pipeline
    if _pipeline is None:
        checkpointer = await get_checkpointer()
        _pipeline = build_pipeline(checkpointer=checkpointer)
    return _pipeline
