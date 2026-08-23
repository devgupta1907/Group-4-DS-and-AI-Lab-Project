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
    # resume_parsing does not publish experience_years, so 0/None means
    # "no signal", not "zero years". Treating it as literal zero rejects
    # every posting that states any requirement at all.
    years = candidate.get("experience_years")
    if not years:
        return True
    guessed = _guess_experience_range(job_text[:3000])
    if guessed is None:
        return True

    min_exp, max_exp = guessed
    if years < max(0.0, min_exp - _EXPERIENCE_SLACK):
        return False
    if years > max_exp + _EXPERIENCE_SLACK:
        return False
    return True


# Cities India officially renamed, where the old name is still in
# extremely common use in job postings (especially Naukri) despite the
# rename — a candidate who types the current official name would
# otherwise get silently rejected from postings using the old one, and
# vice versa. Purely additive to the match set below; can only create
# new matches, never remove one that already worked.
_CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "bengaluru": ("bangalore",),
    "bangalore": ("bengaluru",),
    "mumbai": ("bombay",),
    "bombay": ("mumbai",),
    "chennai": ("madras",),
    "madras": ("chennai",),
    "kolkata": ("calcutta",),
    "calcutta": ("kolkata",),
    "gurgaon": ("gurugram",),
    "gurugram": ("gurgaon",),
    "vadodara": ("baroda",),
    "baroda": ("vadodara",),
}


def _passes_location(candidate: dict, job_json: dict, job_text: str, preferences: dict) -> bool:
    """`target_locations` is a list (career_report.service resolves it to
    at least the candidate's own resume location before the pipeline ever
    runs, so an empty list here genuinely means no location signal exists
    anywhere — not "user left it blank"). A job passes if it matches ANY
    one of the given locations; the user is choosing between cities, not
    requiring all of them simultaneously."""
    is_remote = bool(job_json.get("is_remote")) or "remote" in job_text[:1500].lower()
    remote_only = (preferences or {}).get("remote_only")

    if remote_only:
        return is_remote
    if candidate.get("remote_ok") and is_remote:
        return True

    target_locations = (preferences or {}).get("target_locations") or []
    if not target_locations:
        return True

    # candidate.location comes from the resume contact block and is often a
    # full street address, which never appears verbatim in a posting. Match
    # any comma-separated component longer than three characters instead —
    # city or state is enough signal for a stage that is meant to be
    # permissive. Same per-string splitting as before, just applied across
    # every given location instead of just one.
    haystack = f"{job_json.get('location', '')} {job_text[:1500]}".lower()
    all_parts: list[str] = []
    for location in target_locations:
        for p in (p.strip().lower() for p in location.split(",")):
            if len(p) <= 3:
                continue
            all_parts.append(p)
            all_parts.extend(_CITY_ALIASES.get(p, ()))
    if not all_parts:
        return True
    # NOTE: earlier versions of this line read
    # `return is_remote or any(p in haystack for p in all_parts)` — that
    # "is_remote or" was a bug, present since before this function was
    # rewritten for multi-location support, not something introduced here.
    # It meant ANY posting tagged remote bypassed the location check
    # entirely, for every candidate, regardless of candidate.get("remote_ok")
    # — which is exactly why a Chennai-only search returned a job in NY: the
    # posting was titled "Remote Helpdesk", is_remote=True, and that alone
    # was enough to skip the location match altogether. The correct "remote
    # is acceptable to this candidate" path already exists above
    # (candidate.get("remote_ok") and is_remote) — this line should only be
    # a location match, nothing else.
    return any(p in haystack for p in all_parts)


# Deliberately loose, same spirit as _EXPERIENCE_RANGE_RE above: Indian job
# postings state salary in wildly inconsistent formats, and this stage is
# meant to be permissive, not a precise parser. Two families:
#   - "X-Y LPA" / "X LPA" / "X lakhs" / "X lacs" (with or without ₹/Rs/INR)
#   - absolute rupee figures with Indian comma grouping, e.g. "₹8,00,000",
#     optionally as a range ("₹8,00,000 - ₹12,00,000")
_SALARY_LPA_RANGE_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:-|to|–)\s*(?:₹|rs\.?|inr)?\s*"
    r"(\d{1,3}(?:\.\d+)?)\s*(?:lpa|lakhs?|lacs?)\b",
    re.IGNORECASE,
)
_SALARY_LPA_SINGLE_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:lpa|lakhs?|lacs?)\b",
    re.IGNORECASE,
)
_SALARY_RUPEE_RANGE_RE = re.compile(r"₹\s*(\d[\d,]{4,})\s*(?:-|to|–)\s*₹?\s*(\d[\d,]{4,})")
_SALARY_RUPEE_SINGLE_RE = re.compile(r"(?:₹|(?:rs|inr)\.?\s)\s*(\d[\d,]{4,})", re.IGNORECASE)


def _guess_salary_lpa_max(text: str) -> float | None:
    """Highest plausible salary figure mentioned, in LPA (lakhs per annum),
    or None if nothing matched. Returns the upper end of a range (or the
    single figure given) — a job posting "8-12 LPA" against a candidate
    wanting 10 could plausibly pay enough, so it's evaluated on its best
    case, not its worst. This is a heuristic over free text, the same as
    _guess_experience_range above; a false miss (returns None) is treated
    as "not mentioned" by the caller, not as "definitely underpays"."""
    range_match = _SALARY_LPA_RANGE_RE.search(text)
    if range_match:
        lo, hi = float(range_match.group(1)), float(range_match.group(2))
        return max(lo, hi)

    single_match = _SALARY_LPA_SINGLE_RE.search(text)
    if single_match:
        return float(single_match.group(1))

    rupee_range = _SALARY_RUPEE_RANGE_RE.search(text)
    if rupee_range:
        lo = float(rupee_range.group(1).replace(",", ""))
        hi = float(rupee_range.group(2).replace(",", ""))
        return max(lo, hi) / 100_000

    rupee_single = _SALARY_RUPEE_SINGLE_RE.search(text)
    if rupee_single:
        return float(rupee_single.group(1).replace(",", "")) / 100_000

    return None


def _passes_salary(job_json: dict, job_text: str, preferences: dict) -> bool:
    """Permissive by explicit product decision: most Indian job postings
    don't state a salary at all, and a candidate's minimum shouldn't
    silently exclude the majority of the market. A job is only rejected
    when a salary figure IS found and it's clearly below the candidate's
    minimum — no figure found (structured or in free text) always passes,
    same as an unparseable figure."""
    min_salary_lpa = (preferences or {}).get("min_salary_lpa")
    if not min_salary_lpa:
        return True

    # Adzuna-sourced jobs carry structured salary_min/salary_max (raw
    # rupees, not LPA) — prefer that over regex-guessing when present.
    salary_max = job_json.get("salary_max")
    salary_min = job_json.get("salary_min")
    if salary_max or salary_min:
        structured_max_lpa = max(v for v in (salary_max, salary_min) if v) / 100_000
        return structured_max_lpa >= min_salary_lpa

    guessed_max_lpa = _guess_salary_lpa_max(job_text[:3000])
    if guessed_max_lpa is None:
        return True

    return guessed_max_lpa >= min_salary_lpa


async def run(state: PipelineState) -> PipelineState:
    candidate = state["candidate_json"]
    preferences = state.get("preferences") or {}
    raw_jobs = state.get("raw_jobs", [])
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
        if not _passes_salary(job_json, job_text, preferences):
            continue
        filtered.append(entry)

    logger.info("Hard filter: %d/%d jobs kept", len(filtered), len(raw_jobs))
    state["filtered_jobs"] = filtered
    state.setdefault("progress", []).append("hard_filter_complete")
    return state
