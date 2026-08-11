"""promptfoo python provider for the query_generator / judge_batch prompt evals.

Deliberately dependency-light (stdlib only) so this eval doesn't need the
full backend's asyncpg/sqlalchemy/crawl4ai stack installed — it only needs
promptfoo (node) + python3 to test the two LLM prompts in isolation.

Mirrors app/services/llm_client.py's contract:
  - system/user messages, temperature, max_tokens
  - strips markdown fences before returning
  - one retry on transient HTTP failure

MOCK MODE: if OPENROUTER_API_KEY is unset, or EVAL_MOCK=1 is exported, no
network call is made — a deterministic synthetic response is returned
instead. This keeps `promptfoo eval` runnable in CI / offline / for
harness self-tests, and keeps LLM spend at zero while iterating on the
eval itself. Unset EVAL_MOCK and export a real key to grade actual model
output.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
EVAL_MOCK = os.environ.get("EVAL_MOCK", "").lower() in ("1", "true", "yes") or not OPENROUTER_API_KEY

_SYSTEM_SPLIT_RE = re.compile(r"^SYSTEM:\s*(.*?)\n\s*USER:\s*(.*)$", re.DOTALL)


def _split_prompt(rendered_prompt: str) -> tuple[str, str]:
    """The .txt prompt files use a 'SYSTEM: ... USER: ...' convention so a
    single promptfoo prompt file maps cleanly onto llm_client's two-message
    format. Falls back to treating the whole thing as a user message."""
    m = _SYSTEM_SPLIT_RE.match(rendered_prompt.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", rendered_prompt.strip()


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip().strip("`").strip()


def _call_openrouter(system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    last_exc = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError) as exc:
            last_exc = exc
            time.sleep(1)
    raise RuntimeError(f"OpenRouter call failed after retry: {last_exc}")


def _mock_response(context: dict) -> str:
    """Deterministic, schema-correct fake output so the eval pipeline
    (assertions, latency capture, aggregation) can be exercised with zero
    LLM calls and zero API key required."""
    v = context.get("vars", {})
    if "jobs_block" in v:
        num_jobs = int(v.get("num_jobs", 1))
        jobs = []
        for i in range(num_jobs):
            prob = 40 + (i * 17) % 55  # spread across low/mid/high bands
            if prob >= 70:
                rec = "Apply Immediately"
            elif prob >= 30:
                rec = "Apply"
            else:
                rec = "Skip"
            jobs.append({
                "title": f"Mock Role {i}",
                "company": "Mock Co",
                "location": "Bangalore",
                "is_remote": i % 2 == 0,
                "required_skills": ["SQL", "Python"],
                "interview_probability": prob,
                "strengths": ["Relevant skills"],
                "gaps": ["Limited domain experience"],
                "recommendation": rec,
                "one_line_reason": "Reasonable overlap with candidate profile.",
            })
        return json.dumps(jobs)
    num_queries = int(v.get("num_queries", 6))
    base = ["Data Analyst jobs", "SQL Python analyst", "fintech data analyst",
            "Business Analyst Bangalore", "Analytics Engineer remote", "junior data analyst jobs"]
    queries = (base * ((num_queries // len(base)) + 1))[:num_queries]
    return json.dumps(queries)


def call_api(prompt: str, options: dict, context: dict) -> dict:
    """promptfoo python-provider entrypoint. `prompt` is the fully-rendered
    prompt (vars already substituted by promptfoo's nunjucks templating)."""
    cfg = (options or {}).get("config", {}) or {}
    temperature = float(cfg.get("temperature", 0.0))
    max_tokens = int(cfg.get("max_tokens", 1500))

    t0 = time.perf_counter()
    try:
        if EVAL_MOCK:
            raw = _mock_response(context)
        else:
            system_prompt, user_prompt = _split_prompt(prompt)
            raw = _call_openrouter(system_prompt, user_prompt, temperature, max_tokens)
        parsed_ok = True
        try:
            json.loads(_strip_markdown_fences(raw))
        except json.JSONDecodeError:
            parsed_ok = False
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "output": _strip_markdown_fences(raw),
            "metadata": {
                "mock": EVAL_MOCK,
                "valid_json": parsed_ok,
                "provider_latency_ms": round(elapsed_ms, 1),
            },
        }
    except Exception as exc:  # noqa: BLE001 - surface as a failed eval row, not a crash
        return {"error": f"{type(exc).__name__}: {exc}"}
