"""BM25Okapi scoring for exact technical-skill matching.

BM25 has no learnable parameters and requires no training — it computes
term-frequency statistics over the job corpus at request time. Ported
near-verbatim from career-agent's app/services/bm25_service.py.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word-piece-ish tokeniser so 'Python' and 'python' collide."""
    return _TOKEN_RE.findall(text.lower())


def score_jobs_against_query(query_text: str, job_texts: list[str]) -> list[float]:
    """Return one BM25 score per job_text for the given query_text.

    Scores are min-max normalised into [0, 1] by dividing by the maximum
    score in the batch.
    """
    if not job_texts:
        return []

    corpus_tokens = [tokenize(t) for t in job_texts]
    bm25 = BM25Okapi(corpus_tokens)
    query_tokens = tokenize(query_text)
    raw_scores = bm25.get_scores(query_tokens)

    max_score = max(raw_scores) if len(raw_scores) else 0.0
    if max_score <= 0:
        return [0.0 for _ in raw_scores]
    return [float(s) / float(max_score) for s in raw_scores]
