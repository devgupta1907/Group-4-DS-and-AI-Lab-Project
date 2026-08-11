"""Deterministic promptfoo assertions for the query_generator / judge_batch
prompt variants.

All grading here is rule-based JSON/schema validation — no `llm-rubric` or
model-graded assertions are used anywhere in this eval, on purpose: model
grading would double the number of LLM calls per test case (one to
generate, one to grade). Recall/precision/quality signal instead comes
from checking the response against the exact schema judge_module.py and
query_generator.py already depend on in production.
"""
import json
import re

_VALID_RECS = {"Apply Immediately", "Apply", "Skip"}


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip().strip("`").strip()


def _load_json(output):
    if isinstance(output, (list, dict)):
        return output
    return json.loads(_strip_fences(output))


# ---------------------------------------------------------------- queries --

def check_query_array(output, context):
    """query_generator: exactly N non-empty, unique-ish string queries."""
    expected_n = int(context["vars"].get("num_queries", 6))
    try:
        data = _load_json(output)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"pass": False, "score": 0.0, "reason": f"not valid JSON: {exc}"}

    if not isinstance(data, list):
        return {"pass": False, "score": 0.0, "reason": "top-level JSON is not an array"}

    strings = [q for q in data if isinstance(q, str) and q.strip()]
    length_ok = len(data) == expected_n
    all_strings = len(strings) == len(data)
    unique_ratio = len(set(s.lower().strip() for s in strings)) / max(len(strings), 1)

    score = 0.5 * (1.0 if length_ok else len(data) / expected_n) \
        + 0.3 * (1.0 if all_strings else 0.0) \
        + 0.2 * unique_ratio

    return {
        "pass": length_ok and all_strings and unique_ratio > 0.7,
        "score": round(min(score, 1.0), 3),
        "reason": f"len={len(data)}/{expected_n}, all_strings={all_strings}, unique_ratio={unique_ratio:.2f}",
    }


def check_query_diversity(output, context):
    """Reward queries that don't just repeat the same 2-3 tokens (a cheap,
    zero-LLM proxy for 'these queries will actually surface different
    jobs' instead of near-duplicate SearXNG hits)."""
    try:
        data = _load_json(output)
    except (json.JSONDecodeError, TypeError):
        return {"pass": False, "score": 0.0, "reason": "not valid JSON"}
    if not isinstance(data, list) or not data:
        return {"pass": False, "score": 0.0, "reason": "empty/invalid array"}

    token_sets = [set(re.findall(r"[a-z0-9+#]+", str(q).lower())) for q in data]
    pairs, overlaps = 0, 0.0
    for i in range(len(token_sets)):
        for j in range(i + 1, len(token_sets)):
            a, b = token_sets[i], token_sets[j]
            if not a or not b:
                continue
            overlaps += len(a & b) / len(a | b)
            pairs += 1
    avg_overlap = overlaps / pairs if pairs else 0.0
    diversity = 1.0 - avg_overlap
    return {"pass": diversity > 0.4, "score": round(diversity, 3), "reason": f"avg_pair_overlap={avg_overlap:.2f}"}


# ------------------------------------------------------------------ judge --

def check_judge_array(output, context):
    """judge_batch: exactly N objects, matching schema, scores in range."""
    expected_n = int(context["vars"].get("num_jobs", 1))
    try:
        data = _load_json(output)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"pass": False, "score": 0.0, "reason": f"not valid JSON: {exc}"}

    if not isinstance(data, list):
        return {"pass": False, "score": 0.0, "reason": "top-level JSON is not an array"}
    if len(data) != expected_n:
        return {"pass": False, "score": 0.2, "reason": f"len={len(data)} != expected {expected_n}"}

    ok_count = 0
    problems = []
    for i, job in enumerate(data):
        if not isinstance(job, dict):
            problems.append(f"job {i} not an object")
            continue
        prob = job.get("interview_probability")
        prob_ok = isinstance(prob, (int, float)) and 0 <= prob <= 100
        rec_ok = job.get("recommendation") in _VALID_RECS
        has_reason = bool(job.get("one_line_reason"))
        has_skills = isinstance(job.get("required_skills"), list)
        if prob_ok and rec_ok and has_reason and has_skills:
            ok_count += 1
        else:
            problems.append(
                f"job {i}: prob_ok={prob_ok} rec_ok={rec_ok} "
                f"has_reason={has_reason} has_skills={has_skills}"
            )

    score = ok_count / expected_n
    return {
        "pass": score == 1.0,
        "score": round(score, 3),
        "reason": "; ".join(problems) if problems else "all jobs well-formed",
    }


def check_judge_calibration(output, context):
    """Sanity check: 'Apply Immediately' should correlate with a high
    interview_probability, and 'Skip' with a low one, per job. Catches
    prompts that produce internally-inconsistent judgments."""
    try:
        data = _load_json(output)
    except (json.JSONDecodeError, TypeError):
        return {"pass": False, "score": 0.0, "reason": "not valid JSON"}
    if not isinstance(data, list) or not data:
        return {"pass": False, "score": 0.0, "reason": "empty/invalid array"}

    consistent = 0
    for job in data:
        if not isinstance(job, dict):
            continue
        prob = job.get("interview_probability")
        rec = job.get("recommendation")
        if not isinstance(prob, (int, float)):
            continue
        if rec == "Apply Immediately" and prob >= 70:
            consistent += 1
        elif rec == "Apply" and 30 <= prob < 90:
            consistent += 1
        elif rec == "Skip" and prob < 60:
            consistent += 1

    score = consistent / len(data)
    return {"pass": score >= 0.8, "score": round(score, 3), "reason": f"{consistent}/{len(data)} internally consistent"}
