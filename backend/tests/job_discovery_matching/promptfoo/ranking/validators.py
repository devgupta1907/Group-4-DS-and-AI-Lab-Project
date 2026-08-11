"""promptfoo assertions for ranking.promptfooconfig.yaml. Each function
just reads a field the provider already computed and turns it into a
named, thresholded promptfoo metric — no recomputation, no LLM calls."""
import json


def _load(output):
    return output if isinstance(output, dict) else json.loads(output)


def precision_at_5(output, context):
    data = _load(output)
    v = data.get("precision_at_5", 0.0)
    return {"pass": v >= 0.4, "score": v, "reason": f"precision@5={v}"}


def ndcg_at_10(output, context):
    data = _load(output)
    v = data.get("ndcg_at_10", 0.0)
    return {"pass": v >= 0.7, "score": v, "reason": f"ndcg@10={v}"}


def spearman_correlation(output, context):
    data = _load(output)
    v = data.get("spearman_correlation", 0.0)
    # normalise -1..+1 to a 0..1 score so it combines cleanly with the
    # other 0..1 metrics in aggregate_results.py's composite score
    normalized = (v + 1) / 2
    return {"pass": v >= 0.3, "score": round(normalized, 4), "reason": f"spearman={v}"}
