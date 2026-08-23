"""Node 5.5 — Rank Persist: ranked_jobs[] -> job_discovery_rankings rows.

Split out of what used to be judge_module's `_persist()` for one reason:
judge_module now only runs if the user opts into the LLM judge stage at
`judge_confirmation_gate` (see that node's docstring). Rankings —
`job_discovery_rankings` rows — need to exist regardless of that choice,
so a later `GET /api/jobs/status/{run_id}` still shows the hybrid-ranked
jobs even for a run where the user declined judging.

Every entry gets `ranking_id` and `rank_position` written back onto it
in `state["ranked_jobs"]`, so:
  - judge_module can call `repo.save_judge_result(entry["ranking_id"], ...)`
    directly instead of re-inserting rankings itself.
  - hybrid_finalize_module (the "user declined judge" path) can report a
    real rank_position instead of recomputing one.
"""

from __future__ import annotations

import logging

from src.core.db import get_session_factory
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository

logger = logging.getLogger(__name__)


async def run(state: PipelineState) -> PipelineState:
    ranked_jobs = state.get("ranked_jobs", [])
    if not ranked_jobs:
        state.setdefault("progress", []).append("rank_persist_complete")
        return state

    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        rankings = await repo.save_rankings(state["run_id"], ranked_jobs)

    # save_rankings() assigns rank_position in the SAME order it received
    # ranked_jobs (already hybrid-score-sorted going in) — zip is safe.
    for entry, ranking in zip(ranked_jobs, rankings, strict=True):
        entry["ranking_id"] = ranking.id
        entry["rank_position"] = ranking.rank_position

    state["ranked_jobs"] = ranked_jobs
    state.setdefault("progress", []).append("rank_persist_complete")
    logger.info("Persisted %d rankings for run %s", len(ranked_jobs), state["run_id"])
    return state
