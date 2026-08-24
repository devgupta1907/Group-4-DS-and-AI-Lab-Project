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


# Cities India officially renamed, where the old name is still in very
# common use in job postings (Naukri especially). Without this, searching
# "Bengaluru" silently rejects every posting that says "Bangalore" — the
# same city. Purely additive: can only create new matches, never remove
# one that already worked.
_CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "bengaluru": ("bangalore",), "bangalore": ("bengaluru",),
    "mumbai": ("bombay",), "bombay": ("mumbai",),
    "chennai": ("madras",), "madras": ("chennai",),
    "kolkata": ("calcutta",), "calcutta": ("kolkata",),
    "gurgaon": ("gurugram",), "gurugram": ("gurgaon",),
    "vadodara": ("baroda",), "baroda": ("vadodara",),
}


def _passes_location(candidate: dict, job_json: dict, job_text: str, preferences: dict) -> bool:
    is_remote = bool(job_json.get("is_remote")) or "remote" in job_text[:1500].lower()
    remote_only = (preferences or {}).get("remote_only")

    if remote_only:
        return is_remote
    if candidate.get("remote_ok") and is_remote:
        return True

    # A resume location is evidence about the candidate, not consent to reject
    # every role outside that exact string. Only an explicit search preference
    # is a hard location constraint.
    #
    # Now a LIST (see SearchPreferences.target_locations): a job passes if it
    # matches ANY one of the given locations — the user is choosing between
    # cities, not requiring all of them at once.
    target_locations = (preferences or {}).get("target_locations") or []
    if not target_locations:
        return True

    # candidate.location comes from the resume contact block and is often a
    # full street address ("6993 Jacobson Gardens, Philadelphia, PA"), which
    # never appears verbatim in a posting. Match any comma-separated
    # component longer than three characters instead — city or state is
    # enough signal for a stage that is meant to be permissive.
    # Match against the posting's OWN identifying fields, not the crawled
    # page body.
    #
    # job_text[:1500] used to be included here, and it is the reason a
    # Mumbai search returned Gorakhpur jobs: every Indian job board footer
    # carries a navigation menu listing all major cities, so "mumbai"
    # appears in the page text of a naukri.com/accountant-jobs-in-GORAKHPUR
    # listing. The city being *mentioned somewhere on the page* is not
    # evidence the job is there.
    #
    # source_url is the strongest available signal precisely because these
    # boards put the city in the slug ("accountant-jobs-in-gorakhpur",
    # "/Gorakhpur/Accountants"), and unlike the body it cannot be polluted
    # by nav menus.
    haystack = " ".join((
        str(job_json.get("location") or ""),
        str(job_json.get("source_url") or ""),
        str(job_json.get("title") or ""),
    )).lower().replace("-", " ").replace("/", " ").replace("_", " ")

    # CITY ONLY — deliberately not the state/region components.
    #
    # "Jalore, Rajasthan" used to expand to ["jalore", "rajasthan"], and a
    # job in Gorakhpur (Uttar Pradesh) would pass on "rajasthan" alone,
    # because job-board listing pages carry navigation menus listing every
    # Indian state. A state name appearing somewhere in 1500 characters of
    # crawled page text is not evidence the JOB is in that state. The first
    # comma-separated component is the city, which is the part that
    # actually has to match.
    all_parts: list[str] = []
    for location in target_locations:
        components = [p.strip().lower() for p in location.split(",") if p.strip()]
        if not components:
            continue
        city = components[0]
        if len(city) <= 3:
            continue
        all_parts.append(city)
        all_parts.extend(_CITY_ALIASES.get(city, ()))
    if not all_parts:
        return True

    # NOTE: this deliberately does NOT short-circuit on `is_remote`. It used
    # to read `return is_remote or any(...)`, which meant ANY posting tagged
    # remote bypassed the location check entirely, for every candidate —
    # that's why a Chennai-only search could return a job in New York. The
    # legitimate "remote is acceptable to this candidate" path is the
    # `candidate.get("remote_ok") and is_remote` check above, which is gated
    # on the CANDIDATE wanting remote, not on the job merely offering it.
    return any(p in haystack for p in all_parts)

# Deliberately loose, same spirit as the experience patterns above: Indian
# job postings state pay in wildly inconsistent formats, and this stage is
# meant to be permissive, not a precise parser. Two families:
#   - "X-Y LPA" / "X LPA" / "X lakhs" / "X lacs" (with or without Rs/INR)
#   - absolute rupee figures with Indian comma grouping ("Rs 8,00,000"),
#     optionally as a range
_SALARY_LPA_RANGE_RE = re.compile(
    r"(?:\u20b9|rs\.?|inr)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:-|to|\u2013)\s*(?:\u20b9|rs\.?|inr)?\s*"
    r"(\d{1,3}(?:\.\d+)?)\s*(?:lpa|lakhs?|lacs?)\b",
    re.IGNORECASE,
)
_SALARY_LPA_SINGLE_RE = re.compile(
    r"(?:\u20b9|rs\.?|inr)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:lpa|lakhs?|lacs?)\b",
    re.IGNORECASE,
)
_SALARY_RUPEE_RANGE_RE = re.compile(
    r"\u20b9\s*(\d[\d,]{4,})\s*(?:-|to|\u2013)\s*\u20b9?\s*(\d[\d,]{4,})"
)
_SALARY_RUPEE_SINGLE_RE = re.compile(
    r"(?:\u20b9|(?:rs|inr)\.?\s)\s*(\d[\d,]{4,})", re.IGNORECASE
)


def _guess_salary_lpa_max(text: str) -> float | None:
    """Highest plausible salary figure mentioned, in LPA, or None if nothing
    matched. Returns the UPPER end of a range: a posting saying "8-12 LPA"
    against a candidate wanting 10 could plausibly pay enough, so it is
    judged on its best case. A miss (None) is treated by the caller as
    "not mentioned", never as "definitely underpays"."""
    m = _SALARY_LPA_RANGE_RE.search(text)
    if m:
        return max(float(m.group(1)), float(m.group(2)))
    m = _SALARY_LPA_SINGLE_RE.search(text)
    if m:
        return float(m.group(1))
    m = _SALARY_RUPEE_RANGE_RE.search(text)
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", ""))
        return max(lo, hi) / 100_000
    m = _SALARY_RUPEE_SINGLE_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "")) / 100_000
    return None


def _passes_salary(job_json: dict, job_text: str, preferences: dict) -> bool:
    """Permissive by explicit product decision: most Indian job postings do
    not state a salary at all, so a candidate's minimum must not silently
    exclude the majority of the market. A job is rejected ONLY when a
    figure is found AND it is clearly below the minimum. No figure found,
    or one that cannot be parsed, always passes."""
    min_salary_lpa = (preferences or {}).get("min_salary_lpa")
    if not min_salary_lpa:
        return True

    # Adzuna-sourced jobs carry structured salary_min/salary_max in raw
    # rupees — prefer that over regex-guessing when present.
    salary_max = job_json.get("salary_max")
    salary_min = job_json.get("salary_min")
    if salary_max or salary_min:
        structured_max_lpa = max(v for v in (salary_max, salary_min) if v) / 100_000
        return structured_max_lpa >= min_salary_lpa

    guessed = _guess_salary_lpa_max(job_text[:3000])
    if guessed is None:
        return True
    return guessed >= min_salary_lpa


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
        if not _passes_salary(job_json, job_text, preferences):
            continue
        filtered.append(entry)

    logger.info("Hard filter: %d/%d jobs kept", len(filtered), len(raw_jobs))
    state["filtered_jobs"] = filtered
    state.setdefault("progress", []).append("hard_filter_complete")
    return state
