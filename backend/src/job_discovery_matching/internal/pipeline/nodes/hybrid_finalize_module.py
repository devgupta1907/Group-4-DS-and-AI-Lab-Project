"""Node 6b — Hybrid Finalize: ranked_jobs[] -> final_jobs[] (judge=None).

Reached only when the user declined the LLM judge at
`judge_confirmation_gate.py`. Produces the SAME final_jobs[] shape
judge_module.py does — same keys, `judge` set to None and `final_score`
falling back to `hybrid_score` — so `store._result_from_state()` and the
frontend don't need a separate code path for "hybrid-only" results.

Zero LLM calls, zero new persistence — rank_persist_module.py already
saved these rankings; there's just no judge_result row for them.
"""

from __future__ import annotations

import logging

from src.job_discovery_matching.internal.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


async def run(state: PipelineState) -> PipelineState:
    ranked_jobs = state.get("ranked_jobs", [])

    final_jobs = [
        {
            **entry,
            "judge": None,
            "final_score": entry["hybrid_score"],
        }
        for entry in ranked_jobs
    ]

    state["final_jobs"] = final_jobs
    state.setdefault("progress", []).append("hybrid_finalize_complete")
    return state
