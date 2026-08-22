"""Node 1.6 — Query Selection Gate: search_queries[] -> (human checkpoint) -> search_queries[]

The only node in the graph that calls `interrupt()`. Everything before
it (query_generator) is cheap — one LLM call, no external network
calls yet. Everything after it (db_cache_module, adzuna_module,
search_module+extraction_module) spends real time/money: Adzuna calls,
SearXNG calls, crawl4ai page fetches. This is deliberately the
cheapest possible point to pause and ask "which of these do you
actually want searched" before any of that runs.

`interrupt()` (langgraph.types) suspends graph execution and returns
control to the caller of `pipeline.ainvoke()`/`.astream()` — the
GraphInterrupt it raises propagates up to `service.py`, which reports
status="awaiting_query_selection" back to the API layer. The graph
state at this point is persisted by the checkpointer (see
`internal/pipeline/graph.py`'s `build_pipeline(checkpointer=...)`), so
resuming later — potentially in a different process, after the
original HTTP request has long since returned — picks up exactly
here, not from the start.

Resuming happens via `pipeline.ainvoke(Command(resume=selected_queries), config)`
using the SAME `thread_id` (== run_id) the initial call used. See
`service.py::resume_query_selection()`.
"""

from __future__ import annotations

import logging

from langgraph.types import interrupt

from src.job_discovery_matching.internal.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


async def run(state: PipelineState) -> PipelineState:
    generated = state["search_queries"]

    # On first entry this returns control to the caller (GraphInterrupt).
    # On resume (after Command(resume=...)), it returns the value the
    # caller sent — the queries they actually picked/edited.
    selected: list[str] = interrupt(
        {
            "kind": "select_search_queries",
            "generated_queries": generated,
        }
    )

    # Guard against a resume payload that's empty/malformed — fall back to
    # everything the LLM generated rather than searching on nothing.
    state["search_queries"] = selected if selected else generated
    state.setdefault("progress", []).append("query_selection_confirmed")
    return state
