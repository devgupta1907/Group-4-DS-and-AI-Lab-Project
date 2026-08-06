"""Node 4 — Hard Filter: raw_jobs[] -> filtered_jobs[].

Zero LLM calls. Cheap regex heuristics over the crawled job_text.
Intentionally permissive — false negatives here would silently drop good
jobs before ranking ever sees them, so ambiguous cases pass through and
let BM25/embeddings/the judge sort it out instead.

Ported from career-agent's app/pipeline/nodes/hard_filter.py.
`experience_years` from `profile_mapper.from_parsed_resume()` is always
0.0 (resume_parsing does not publish it) — `_passes_experience` therefore
treats "0 years" as real signal only when the job text gives no range at
all to compare against; see the docstring in profile_mapper.py for why.
"""

from __future__ import annotations

import logging
import re

from src.job_discovery_matching.internal.pipeline.state import PipelineState
import json
logger = logging.getLogger(__name__)

_EXPERIENCE_RANGE_RE = re.compile(r"(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*\+?\s*years?", re.IGNORECASE)
_EXPERIENCE_MIN_RE = re.compile(r"(\d{1,2})\s*\+\s*years?", re.IGNORECASE)
_EXPERIENCE_SLACK = 2.0


def _guess_experience_range(text: str) -> tuple[float, float] | None:
    range_match = _EXPERIENCE_RANGE_RE.search(text)
    if range_match:
        lo, hi = float(range_match.group(1)), float(range_match.group(2))
        return (lo, hi) if lo <= hi else (hi, lo)

    min_match = _EXPERIENCE_MIN_RE.search(text)
    if min_match:
        lo = float(min_match.group(1))
        return (lo, lo + 5)

    return None


def _passes_experience(candidate: dict, job_text: str) -> bool:
    years = candidate.get("experience_years") or 0
    guessed = _guess_experience_range(job_text[:3000])
    if guessed is None:
        return True

    min_exp, max_exp = guessed
    if years < max(0.0, min_exp - _EXPERIENCE_SLACK):
        return False
    if years > max_exp + _EXPERIENCE_SLACK:
        return False
    return True


def _passes_location(candidate: dict, job_json: dict, job_text: str, preferences: dict) -> bool:
    is_remote = bool(job_json.get("is_remote")) or "remote" in job_text[:1500].lower()
    remote_only = (preferences or {}).get("remote_only")

    if remote_only:
        return is_remote
    if candidate.get("remote_ok") and is_remote:
        return True

    target_location = (preferences or {}).get("target_location") or candidate.get("location") or ""
    if not target_location:
        return True

    haystack = f"{job_json.get('location', '')} {job_text[:1500]}".lower()
    return target_location.strip().lower() in haystack or is_remote


async def run(state: PipelineState) -> PipelineState:
    candidate = state["candidate_json"]
    preferences = state.get("preferences") or {}
    raw_jobs = state.get("raw_jobs", [])
    # print(json.dumps(raw_jobs[0].job_json, indent=2))
    filtered = []
    for entry in raw_jobs:
        job_json = entry["job_json"]
        job_text = entry["job_text"]
        if not job_json.get("title") and len(job_text) < 200:
            continue
        if not _passes_experience(candidate, job_text):
            continue
        if not _passes_location(candidate, job_json, job_text, preferences):
            continue
        filtered.append(entry)

    logger.info("Hard filter: %d/%d jobs kept", len(filtered), len(raw_jobs))
    state["filtered_jobs"] = filtered
    state.setdefault("progress", []).append("hard_filter_complete")
    return state
