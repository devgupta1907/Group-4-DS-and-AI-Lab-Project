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
import re

from src.core.db import get_session_factory
from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.pipeline.state import PipelineState
from src.job_discovery_matching.internal.repository import JobDiscoveryRepository
from src.job_discovery_matching.internal.services.llm_client import JudgedJob, LLMError, judge_batch

# Defensive net, not the primary fix: crawler_service.py's _clean_text is
# where job_text should already be cleaned before it ever reaches this
# node. This second pass exists so that a future extraction path (a new
# source module, a cache row written before the crawler_service fix, a
# manually-inserted posting, ...) can never smuggle raw HTML into the
# judge LLM prompt just because it skipped that upstream cleaning step.
_TAG_RE = re.compile(r"<[^<]+?>")

# Same intent as search_module.py's _is_direct_vacancy title check, but
# broadened after finding a real miss: the original only matched "N+ ...
# jobs" (count BEFORE the word). "Information Technology Jobs in Chennai
# (1,000+ Open Roles)" puts the count in a trailing parenthetical instead
# — same listing page, missed by the narrower pattern. Reused here as a
# SECOND, code-level check on top of judged.is_real_vacancy — the prompt
# explicitly asks the model to set that field false for exactly this
# case, but in practice it doesn't always: a listing page can still get a
# real fit score in the 0-39 "Skip" band without is_real_vacancy ever
# being set false, which fools the deterministic backstop below into
# thinking it's a genuine posting that just scored low. A title match
# here is unambiguous regardless of what the model reported.
_LISTING_TITLE_RE = re.compile(
    r"\b\d[\d,]*\+?\s+.*\bjobs?\b"
    r"|\(\s*\d[\d,]*\+?\s*(?:open\s+)?(?:roles?|jobs?|positions?|openings?)\s*\)",
    re.IGNORECASE,
)


def _title_looks_like_listing(title: str) -> bool:
    title = title or ""
    return bool(_LISTING_TITLE_RE.search(title)) or "job vacancies" in title.lower()


def _strip_residual_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()

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
        # Strip BEFORE truncating to Cfg.JUDGE_TEXT_CHAR_LIMIT, not after —
        # truncating first then stripping can cut mid-tag and leave a
        # dangling '<' or an unterminated tag in the prompt, and it also
        # wastes budget on markup that would've been removed anyway.
        text = _strip_residual_html(entry["job_text"])[: Cfg.JUDGE_TEXT_CHAR_LIMIT]
        parts.append(f"--- JOB {i} ---\n{text}")
    return "\n\n".join(parts)


def _merge_entry(entry: dict, judged: JudgedJob, *, used_llm_judge: bool) -> dict:
    fallback_probability = int(round(entry["hybrid_score"] * 100))
    prob = judged.interview_probability
    if not isinstance(prob, int) or not (0 <= prob <= 100):
        prob = fallback_probability

    # Deterministic backstop, not trusting the model to reliably self-report
    # 0 here (it doesn't always — see JudgedJob.is_real_vacancy's docstring,
    # and _title_looks_like_listing above for the case where it also
    # doesn't reliably set is_real_vacancy itself). Only forces 0 for "not
    # a real posting at all"; a real posting that's simply a poor fit
    # keeps whatever score the rubric actually gave it. Checks the
    # ORIGINAL crawled title (entry["job_json"]), not judged.title — the
    # LLM's "cleaned" title could plausibly strip the "6,000+" prefix that
    # makes the pattern match in the first place.
    is_real_vacancy = judged.is_real_vacancy and not _title_looks_like_listing(
        entry["job_json"].get("title")
    )
    recommendation = judged.recommendation or "Apply"
    if not is_real_vacancy:
        prob = 0
        recommendation = "Skip"

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
            "recommendation": recommendation,
            "one_line_reason": judged.one_line_reason or "",
            "used_llm_judge": used_llm_judge,
        },
        "final_score": round(final_score, 4),
    }


async def _persist_judge_results(
    to_judge: list[dict], judged_by_index: dict[int, JudgedJob], used_llm_judge: bool
) -> None:
    """Rankings are already persisted by rank_persist_module.py (this node
    runs after it) — each entry in `to_judge` already carries a
    `ranking_id`. This only adds the judge_result row for the top
    `Cfg.TOP_N_JUDGED` entries, not a second copy of the ranking itself."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = JobDiscoveryRepository(session)
        for index, entry in enumerate(to_judge):
            judged = judged_by_index.get(index)
            if judged is None:
                continue
            fallback_probability = int(round(entry["hybrid_score"] * 100))
            prob = (
                judged.interview_probability
                if isinstance(judged.interview_probability, int)
                else fallback_probability
            )
            # Same deterministic backstop as _merge_entry — the persisted
            # row must match what the user is actually shown, not
            # whatever raw number the model returned before the backstop.
            is_real_vacancy = judged.is_real_vacancy and not _title_looks_like_listing(
                entry["job_json"].get("title")
            )
            recommendation = judged.recommendation or "Apply"
            if not is_real_vacancy:
                prob = 0
                recommendation = "Skip"
            final_score = Cfg.HYBRID_WEIGHT * entry["hybrid_score"] + Cfg.JUDGE_WEIGHT * (prob / 100.0)
            await repo.save_judge_result(
                entry["ranking_id"],
                interview_probability=prob,
                strengths=judged.strengths or [],
                gaps=judged.gaps or [],
                recommendation=recommendation,
                one_line_reason=judged.one_line_reason or "",
                final_score=round(final_score, 4),
                used_llm_judge=used_llm_judge,
            )


async def run(state: PipelineState) -> PipelineState:
    ranked_jobs = state.get("ranked_jobs", [])

    # If the user picked specific jobs at judge_confirmation_gate, judge
    # only those (matched on source_url) instead of the default top-N —
    # this is what makes "judge only what I selected" actually true.
    # Falls back to the original top-N-by-hybrid-score behaviour when no
    # selection was made, so a client that never sends selected_job_urls
    # sees no change.
    selected_urls = state.get("selected_job_urls")
    if selected_urls:
        selected_set = set(selected_urls)
        candidates = [entry for entry in ranked_jobs if entry.get("source_url") in selected_set]
        if not candidates:
            logger.warning(
                "selected_job_urls matched none of %d ranked jobs; falling back to top-N",
                len(ranked_jobs),
            )
            to_judge = ranked_jobs[: Cfg.TOP_N_JUDGED]
        else:
            # An explicit selection is honoured in full, not truncated to
            # TOP_N_JUDGED — that cap exists to bound the automatic "judge
            # the top N by hybrid score" case, not a user's deliberate pick.
            to_judge = candidates
    else:
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
            preferences=state.get("preferences"),
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

    await _persist_judge_results(to_judge, judged_by_index, used_llm_judge)

    # Never leave the report thinner than it needs to be when a wider
    # ranked pool exists to draw from. Two tiers, both deliberately NOT
    # touching a real, correctly-scored result — this only ever ADDS
    # ranked-but-unjudged (judge=None) entries, never removes or re-scores
    # a real one:
    #
    #  - every judged candidate was fake (is_real_vacancy=False, i.e. a
    #    listing/category page, not an individual posting) -> show the
    #    full ranked pool instead of an empty report.
    #  - SOME real postings survived, but fewer than MINIMUM_DISPLAY_TARGET
    #    -> pad up to that target from whatever's left in ranked_jobs
    #    beyond what got judged (search_module now crawls up to
    #    MAX_JOB_URLS, TOP_N_JUDGED only judges the top 8 of those, so
    #    there is usually more available to draw from).
    #
    # This can't manufacture real postings that don't exist — if
    # ranked_jobs itself is thin, the backfill is thin too. It only
    # guarantees nothing gets left on the table that was already found.
    MINIMUM_DISPLAY_TARGET = 3
    real_count = sum(
        1 for job in final_jobs
        if job.get("judge") and job["judge"]["interview_probability"] > 0
    )

    if to_judge and real_count == 0:
        logger.warning(
            "All %d judged candidates were listing/category pages, not real "
            "postings — showing the full ranked pool (%d jobs) instead of "
            "an empty report.",
            len(to_judge), len(ranked_jobs),
        )
        # Distinguishes this from hybrid_finalize_module's judge=None,
        # which means "user declined the judge stage" — service.py's
        # status/message logic checks final_jobs[0]["judge"] is None to
        # detect that case, and without this flag can't tell it apart
        # from "the judge ran and correctly found nothing real," which
        # produces the identical judge=None shape for a completely
        # different reason.
        state["all_candidates_fake"] = True
        final_jobs = [
            {**entry, "judge": None, "final_score": entry["hybrid_score"]}
            for entry in ranked_jobs
        ]
    elif 0 < real_count < MINIMUM_DISPLAY_TARGET:
        judged_urls = {entry.get("source_url") for entry in to_judge}
        backfill = [
            {**entry, "judge": None, "final_score": entry["hybrid_score"]}
            for entry in ranked_jobs
            if entry.get("source_url") not in judged_urls
        ]
        needed = MINIMUM_DISPLAY_TARGET - real_count
        if backfill:
            logger.info(
                "Only %d real posting(s) among %d judged — backfilling %d "
                "unscored candidate(s) from the wider ranked pool.",
                real_count, len(to_judge), min(needed, len(backfill)),
            )
        final_jobs = final_jobs + backfill[:needed]

    final_jobs.sort(key=lambda r: r["final_score"], reverse=True)

    state["final_jobs"] = final_jobs
    state.setdefault("progress", []).append("judging_complete")
    return state
