"""Node 5.6 — Judge Confirmation Gate: ranked_jobs[] -> (human checkpoint) -> proceed?

Second (and last) `interrupt()` in this graph — see
`query_selection_gate.py` for the first. Hybrid ranking (BM25 + embedding
similarity, zero LLM calls, via matching_module.py) has already run and
been persisted (rank_persist_module.py) by the time this node is
reached, so pausing here costs nothing extra to back out of: the user
sees real, already-ranked jobs and decides whether the single batched
LLM judge call (judge_module.py — the pipeline's second and last LLM
call, after query_generator's) is worth spending.

Resuming with `Command(resume={"proceed": True})` continues to
judge_module. `{"proceed": False}` (or any other value) skips straight
to hybrid_finalize_module, which turns the SAME ranked_jobs into the
final result shape without ever calling the judge LLM.
"""

from __future__ import annotations

import logging

from langgraph.types import interrupt

from src.job_discovery_matching.internal.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


async def run(state: PipelineState) -> PipelineState:
    ranked_jobs = state.get("ranked_jobs", [])

    # Nothing to judge either way — skip the pause entirely rather than
    # asking the user to confirm judging zero jobs.
    if not ranked_jobs:
        state["proceed_to_judge"] = False
        state.setdefault("progress", []).append("judge_confirmation_skipped_empty")
        return state

    preview = [
        {
            "title": entry["job_json"].get("title", ""),
            "company": entry["job_json"].get("company", ""),
            "location": entry["job_json"].get("location", ""),
            "hybrid_score": entry["hybrid_score"],
            "source_url": entry["source_url"],
        }
        for entry in ranked_jobs
    ]

    answer = interrupt(
        {
            "kind": "confirm_judge",
            "ranked_jobs_preview": preview,
        }
    )

    proceed = bool(answer.get("proceed")) if isinstance(answer, dict) else bool(answer)
    selected_job_urls = answer.get("selected_job_urls") if isinstance(answer, dict) else None
    logger.info(
        "judge_confirmation_gate resumed: raw_answer=%r proceed=%s selected_job_urls=%s",
        answer, proceed, selected_job_urls,
    )
    state["proceed_to_judge"] = proceed
    # Empty list and None both mean "no restriction, judge everything" —
    # only a non-empty list narrows judge_module's input.
    state["selected_job_urls"] = selected_job_urls or None
    state.setdefault("progress", []).append("judge_confirmation_answered")
    return state
