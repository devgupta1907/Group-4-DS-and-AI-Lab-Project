"""promptfoo assertions for search_crawl.promptfooconfig.yaml. Pure math
over the provider's JSON output — zero LLM calls."""
import json


def _load(output):
    return output if isinstance(output, dict) else json.loads(output)


def check_coverage(output, context):
    """Did this parameter combo find at least expected_min_urls unique URLs?"""
    data = _load(output)
    expected = int(context["vars"].get("expected_min_urls", 3))
    found = data.get("unique_urls_found", 0)
    score = min(found / expected, 1.0) if expected else 1.0
    return {"pass": found >= expected, "score": round(score, 3), "reason": f"found={found}, expected>={expected}"}


def check_crawl_success_rate(output, context):
    data = _load(output)
    rate = data.get("crawl_success_rate", 0.0)
    return {"pass": rate >= 0.6, "score": round(rate, 3), "reason": f"crawl_success_rate={rate}"}
