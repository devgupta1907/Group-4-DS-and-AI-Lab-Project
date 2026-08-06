"""Embedding generation for candidate profiles and job postings.

Deliberately does NOT load its own SentenceTransformer, unlike
career-agent's original app/services/embedding_client.py. This repo
already has a shared, provider-switchable embedding client at
`src.services.llm_client` (HuggingFace BGE locally, or Gemini — see
`GlobalConfig.EMBEDDING_PROVIDER`) that career_recommendation's
retrieval.py already uses. Reusing it means this module never loads a
second copy of the same model into memory and automatically follows
whatever embedding provider the rest of the app is configured for.
"""

from __future__ import annotations

import numpy as np

from src.services.llm_client import document_embeddings, query_embeddings


def embed_query(text: str) -> list[float]:
    """Embed a candidate-side query string (e.g. the candidate profile)."""
    return query_embeddings.embed_query(text)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed job-posting texts (batched)."""
    if not texts:
        return []
    return document_embeddings.embed_documents(texts)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    av, bv = np.array(a), np.array(b)
    denom = (np.linalg.norm(av) * np.linalg.norm(bv)) or 1e-9
    return float(np.dot(av, bv) / denom)
