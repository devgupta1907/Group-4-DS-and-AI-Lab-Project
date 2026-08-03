"""promptfoo provider for the ranking (BM25 + embedding hybrid) parameter
sweep. This is the matching_module.py logic from the pipeline, run against
the Job_Matching_Golden_Dataset (86 candidates x 10 jobs, real ground
truth — see evals/scripts/build_ranking_dataset_from_xlsx.py) instead of
live crawled jobs, so precision@5 / ndcg@10 / Spearman rank correlation
can be measured against known-good answers. No LLM is involved at this
pipeline stage in production, and none is used here either — every
test x provider-config cell is pure math.

Metrics (see metrics.py for definitions):
  - precision_at_5: overlap between our top-5 and ground_truth_top5
    (always a set of exactly 5 jobs per candidate by dataset construction,
    so precision@5 == recall@5 here — only one is reported).
  - ndcg_at_10: computed against the continuous ground_truth_rule_score
    (0-100), over the full 10-job ranking.
  - spearman_correlation: rank-order agreement over all 10 jobs, -1..+1.
    This is the metric to watch most closely when there are only 10 items
    per candidate — precision@5 is coarse (6 possible values) and ndcg@10
    saturates quickly, but Spearman is sensitive to the full ordering.
These three are exactly what the dataset's own README recommends
(Precision@5, NDCG@10, Spearman rank correlation).

EMBEDDINGS: tries the real app.services.embedding_client (bge-base-en-v1.5
via sentence-transformers) first. Falls back to a deterministic hashed
bag-of-words embedding if sentence-transformers/model download isn't
available (e.g. no internet, or running this eval outside the backend
env) or EVAL_MOCK=1 is set. Mock embeddings still respond to *lexical*
overlap so the harness is testable end-to-end, but only the real model
gives a trustworthy semantic-similarity signal — treat mock-mode numbers
as harness smoke-tests, not real ranking-quality results.

BM25: uses rank_bm25 directly (same library + normalisation as
app/services/bm25_service.py) — this has no heavy ML deps so it's always
"real", mock or not.
"""
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # for metrics.py
from metrics import precision_at_k, ndcg_at_k, spearman_rank_correlation  # noqa: E402

EVAL_MOCK_FORCED = os.environ.get("EVAL_MOCK", "").lower() in ("1", "true", "yes")

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "eval_dataset.json"
_DATASET = json.loads(_DATA_PATH.read_text())

# Host layout: <root>/backend/app/... . In-container layout (see
# backend/Dockerfile: WORKDIR /app, COPY app ./app): /app/app/... , so
# /app itself is the equivalent of "backend/" on the host.
# CAREER_AGENT_BACKEND_DIR overrides both if neither guess is right.
_CANDIDATE_BACKEND_DIRS = [
    os.environ.get("CAREER_AGENT_BACKEND_DIR"),
    str(Path(__file__).resolve().parents[4] / "backend"),  # host layout
    "/app",  # in-container layout
]

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False

_REAL_EMBEDDINGS = False
_real_embed_text = None
_import_errors = []

if not EVAL_MOCK_FORCED:
    for _candidate in _CANDIDATE_BACKEND_DIRS:
        if not _candidate or not Path(_candidate).is_dir():
            continue
        if _candidate not in sys.path:
            sys.path.insert(0, _candidate)
        try:
            from app.services.embedding_client import embed_text as _real_embed_text  # type: ignore
            _REAL_EMBEDDINGS = True
            break
        except Exception as exc:  # noqa: BLE001
            _import_errors.append(f"{_candidate}: {type(exc).__name__}: {exc}")
            sys.path.remove(_candidate)

    if not _REAL_EMBEDDINGS and os.environ.get("EVAL_DEBUG"):
        print("[ranking_provider] real embedding import failed, falling back to mock:", file=sys.stderr)
        for line in _import_errors:
            print(f"  tried {line}", file=sys.stderr)

import re
_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _bm25_scores(query_text: str, job_texts: list[str]) -> list[float]:
    if not job_texts:
        return []
    if not _BM25_AVAILABLE:
        # crude fallback: normalized token-overlap ratio
        q = set(_tokenize(query_text))
        out = []
        for t in job_texts:
            toks = set(_tokenize(t))
            out.append(len(q & toks) / len(q) if q else 0.0)
        m = max(out) if out else 0.0
        return [s / m for s in out] if m > 0 else [0.0] * len(out)

    corpus = [_tokenize(t) for t in job_texts]
    bm25 = BM25Okapi(corpus)
    raw = bm25.get_scores(_tokenize(query_text))
    m = max(raw) if len(raw) else 0.0
    return [float(s) / float(m) for s in raw] if m > 0 else [0.0] * len(raw)


_MOCK_DIM = 128


def _mock_embed(text: str) -> list[float]:
    """Deterministic hashed bag-of-words vector — captures lexical overlap
    only, NOT real semantics. Harness smoke-test use only."""
    vec = [0.0] * _MOCK_DIM
    for tok in _tokenize(text):
        idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % _MOCK_DIM
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _embed(text: str) -> list[float]:
    if _REAL_EMBEDDINGS:
        return _real_embed_text(text)
    return _mock_embed(text)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(x * x for x in b)) or 1e-9
    return dot / (na * nb)


def _candidate_query_text(candidate: dict) -> str:
    return " ".join([
        " ".join(candidate.get("skills", []) or []),
        " ".join(candidate.get("target_roles", []) or []),
        candidate.get("domain", "") or "",
    ])


def _run(candidate_id: str, cfg: dict) -> dict:
    bm25_weight = float(cfg.get("bm25_weight", 0.4))
    embedding_weight = float(cfg.get("embedding_weight", 0.3))
    top_k_ranked = int(cfg.get("top_k_ranked", 15))

    entry = _DATASET["candidates"][candidate_id]
    candidate = entry["candidate_json"]
    jobs = entry["jobs"]
    job_ids = [j["job_id"] for j in jobs]
    job_texts = [j["job_text"] for j in jobs]
    # ground truth from the golden dataset (see evals/scripts/build_ranking_dataset_from_xlsx.py)
    rule_score_by_id = {j["job_id"]: j["ground_truth_rule_score"] for j in jobs}
    true_rank_by_id = {j["job_id"]: j["ground_truth_rank"] for j in jobs}
    true_top5_ids = {j["job_id"] for j in jobs if j["ground_truth_top5"]}

    query_text = _candidate_query_text(candidate)

    t0 = time.perf_counter()
    bm25_scores = _bm25_scores(query_text, job_texts)
    bm25_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    query_embedding = _embed(query_text)
    job_embeddings = [_embed(t) for t in job_texts]
    embed_ms = (time.perf_counter() - t1) * 1000

    weight_sum = bm25_weight + embedding_weight
    scored = []
    for jid, bm25_s, job_emb in zip(job_ids, bm25_scores, job_embeddings):
        cos = _cosine(query_embedding, job_emb)
        cos_clipped = max(0.0, min(1.0, (cos + 1) / 2))
        hybrid_raw = bm25_weight * bm25_s + embedding_weight * cos_clipped
        hybrid = hybrid_raw / weight_sum if weight_sum else hybrid_raw
        scored.append((jid, hybrid))

    scored.sort(key=lambda x: x[1], reverse=True)
    ranked_ids_full = [jid for jid, _ in scored]  # full permutation of all 10 jobs
    ranked_ids = ranked_ids_full[:top_k_ranked]
    predicted_rank_by_id = {jid: i + 1 for i, jid in enumerate(ranked_ids_full)}

    total_ms = bm25_ms + embed_ms

    return {
        "candidate_id": candidate_id,
        "mode": "real_embeddings" if _REAL_EMBEDDINGS else "mock_embeddings",
        "ranked_top5": ranked_ids[:5],
        "precision_at_5": round(precision_at_k(ranked_ids, true_top5_ids, 5), 4),
        "ndcg_at_10": round(ndcg_at_k(ranked_ids_full, rule_score_by_id, 10), 4),
        "spearman_correlation": round(spearman_rank_correlation(predicted_rank_by_id, true_rank_by_id), 4),
        "bm25_latency_ms": round(bm25_ms, 2),
        "embedding_latency_ms": round(embed_ms, 2),
        "total_latency_ms": round(total_ms, 2),
        "params": {
            "bm25_weight": bm25_weight,
            "embedding_weight": embedding_weight,
            "top_k_ranked": top_k_ranked,
        },
    }


def call_api(prompt: str, options: dict, context: dict) -> dict:
    cfg = (options or {}).get("config", {}) or {}
    candidate_id = (context.get("vars") or {}).get("candidate_id") or prompt.strip()
    try:
        result = _run(candidate_id, cfg)
        return {"output": json.dumps(result), "metadata": result}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
