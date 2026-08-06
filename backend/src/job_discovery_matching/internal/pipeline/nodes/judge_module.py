"""Node 6 — Judge Module: ranked_jobs[:TOP_N_JUDGED] -> final_jobs[].

The only other LLM call in the pipeline besides query_generator, and
it's a SINGLE batched request for all `Cfg.TOP_N_JUDGED` finalists — not
one call per job. Since extraction never runs an LLM over these jobs,
this call also does double duty: it cleans up title/company/location/
skills for display AND scores candidate fit, in one structured response.

This node also does ALL of this run's persistence in one place: every
surviving `ranked_jobs` entry gets a `job_discovery_rankings` row (this
is the "ranking" record), and the top `TOP_N_JUDGED` additionally get a
`job_discovery_judge_results` row (this is the "judge response" record).
"""

from __future__ import annotations

import logging

from src.core.db import get_session_factory
from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
from src.job_discovery_matching.internal.services.llm_client import JudgedJob, LLMError, judge_batch

logger = logging.getLogger(__name__)


def _fallback_judged(entry: dict) -> JudgedJob:
    """Used only if the single batched LLM call fails outright — falls
    back to the crude/JSON-LD metadata and the hybrid score, so the user
    still gets a ranked list even with zero LLM availability."""
    job_json = entry["job_json"]
    fallback_probability = int(round(entry["hybrid_score"] * 100))
    return JudgedJob(
        title=job_json.get("title") or "Untitled role",
        company=job_json.get("company", "") or "",
        location=job_json.get("location", "") or "",
        is_remote=bool(job_json.get("is_remote", False)),
        required_skills=job_json.get("required_skills", []) or [],
        interview_probability=fallback_probability,
        strengths=[],
        gaps=[],
        recommendation="Apply" if fallback_probability >= 50 else "Skip",
        one_line_reason="LLM judge unavailable; ranked by hybrid score only.",
    )


def _build_jobs_block(entries: list[dict]) -> str:
    parts = []
    for i, entry in enumerate(entries):
        text = entry["job_text"][: Cfg.JUDGE_TEXT_CHAR_LIMIT]
        parts.append(f"--- JOB {i} ---\n{text}")
    return "\n\n".join(parts)


def _merge_entry(entry: dict, judged: JudgedJob, *, used_llm_judge: bool) -> dict:
    fallback_probability = int(round(entry["hybrid_score"] * 100))
    prob = judged.interview_probability
    if not isinstance(prob, int) or not (0 <= prob <= 100):
        prob = fallback_probability

    merged_job_json = {
        **entry["job_json"],
        "title": judged.title or entry["job_json"].get("title") or "Untitled role",
        "company": judged.company or entry["job_json"].get("company", ""),
        "location": judged.location or entry["job_json"].get("location", ""),
        "is_remote": (
            judged.is_remote if judged.is_remote is not None else entry["job_json"].get("is_remote", False)
        ),
        "required_skills": judged.required_skills or entry["job_json"].get("required_skills", []),
    }

    final_score = Cfg.HYBRID_WEIGHT * entry["hybrid_score"] + Cfg.JUDGE_WEIGHT * (prob / 100.0)

    return {
        **entry,
        "job_json": merged_job_json,
        "judge": {
            "interview_probability": int(prob),
            "strengths": judged.strengths or [],
            "gaps": judged.gaps or [],
            "recommendation": judged.recommendation or "Apply",
            "one_line_reason": judged.one_line_reason or "",
            "used_llm_judge": used_llm_judge,
        },
        "final_score": round(final_score, 4),
    }


async def _persist(
    run_id, ranked_jobs: list[dict], judged_by_index: dict[int, JudgedJob], used_llm_judge: bool
) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        rankings = await repo.save_rankings(
            run_id,
            [
                {
                    "posting_id": entry["posting_id"],
                    "bm25_score": entry["bm25_score"],
                    "embedding_score": entry["embedding_score"],
                    "hybrid_score": entry["hybrid_score"],
                }
                for entry in ranked_jobs
            ],
        )
        for index, ranking in enumerate(rankings):
            judged = judged_by_index.get(index)
            if judged is None:
                continue
            entry = ranked_jobs[index]
            fallback_probability = int(round(entry["hybrid_score"] * 100))
            prob = (
                judged.interview_probability
                if isinstance(judged.interview_probability, int)
                else fallback_probability
            )
            final_score = Cfg.HYBRID_WEIGHT * entry["hybrid_score"] + Cfg.JUDGE_WEIGHT * (prob / 100.0)
            await repo.save_judge_result(
                ranking.id,
                interview_probability=prob,
                strengths=judged.strengths or [],
                gaps=judged.gaps or [],
                recommendation=judged.recommendation or "Apply",
                one_line_reason=judged.one_line_reason or "",
                final_score=round(final_score, 4),
                used_llm_judge=used_llm_judge,
            )


async def run(state: PipelineState) -> PipelineState:
    ranked_jobs = state.get("ranked_jobs", [])
    to_judge = ranked_jobs[: Cfg.TOP_N_JUDGED]

    if not ranked_jobs:
        state["final_jobs"] = []
        state.setdefault("progress", []).append("judging_complete")
        return state

    used_llm_judge = True
    try:
        judged_list = await judge_batch(
            state["candidate_json"],
            jobs_block=_build_jobs_block(to_judge),
            num_jobs=len(to_judge),
        )
    except LLMError as exc:
        logger.warning("Batched LLM judge failed for %d jobs: %s", len(to_judge), exc)
        used_llm_judge = False
        judged_list = [_fallback_judged(entry) for entry in to_judge]

    judged_by_index = {i: judged_list[i] for i in range(min(len(judged_list), len(to_judge)))}

    final_jobs = [
        _merge_entry(entry, judged_by_index.get(i) or _fallback_judged(entry), used_llm_judge=used_llm_judge)
        for i, entry in enumerate(to_judge)
    ]
    final_jobs.sort(key=lambda r: r["final_score"], reverse=True)

    await _persist(state["run_id"], ranked_jobs, judged_by_index, used_llm_judge)

    state["final_jobs"] = final_jobs
    state.setdefault("progress", []).append("judging_complete")
    return state
