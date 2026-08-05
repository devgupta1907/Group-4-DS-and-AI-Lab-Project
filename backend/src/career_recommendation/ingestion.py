"""
Career Recommendation — ESCO ingestion into Supabase pgvector.

This is the ONLY file that writes the vector index. It prepares one
document per ESCO occupation, embeds them locally, and writes them
straight into the `documents` table via psycopg2.

Run from backend/:
    uv run python src/career_recommendation/ingestion.py            # rebuild index
    uv run python src/career_recommendation/ingestion.py --verify   # check only

WHY DIRECT SQL AND NOT langchain's SupabaseVectorStore
    SupabaseVectorStore.add_documents() wrote malformed embeddings: the
    stored vectors had an L2 norm of ~0.59 (BGE always emits ~1.0) and
    were orthogonal to a re-embedding of their own text (cosine -0.007).
    Content and metadata landed correctly, so the corruption was silent
    and only surfaced as nonsense retrieval results. Writing the pgvector
    literal ourselves ("[0.1,0.2,...]"::vector) avoids it entirely.
    Reads through langchain (db/supabase_manager.py) are fine — it is
    only the write path that is broken.

KNOWN LIMITATION
    BGE truncates at 512 tokens; the longest occupation documents reach
    ~1,300 tokens, so tails (usually the optional-skills segment) are
    silently dropped by the encoder. Chunking would fix this but requires
    changing retrieval to dedupe/aggregate multiple chunks per
    occupation. Accepted and recorded rather than worked around here.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os

import pandas as pd
import psycopg2
from dotenv import find_dotenv, load_dotenv
from langchain_core.documents import Document
from psycopg2.extras import execute_batch

from career_recommendation.config import CareerRecommendationModuleConfig
from core.config import GlobalConfig
from services.llm_client import document_embeddings

logger = logging.getLogger(__name__)

BATCH = 128

# BGE runs locally with no quota. Gemini's free tier allows ~100 embed
# requests/minute, so it needs a smaller batch and a pause between them.
GEMINI_BATCH = 90
GEMINI_PAUSE_SECONDS = 62


# ---------------------------------------------------------------------
# Document preparation
# ---------------------------------------------------------------------

def _clean(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _split_skills(value) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    return [s.strip() for s in text.split(";") if s.strip()]


def prepare_documents(csv_path: str) -> list[Document]:
    """
    Builds one Document per ESCO occupation from the cleaned dataset.

    page_content is `career_role_context` (pre-built by preprocessing:
    title + alternative titles + description + essential + optional
    skills). If that column is empty for a row, an equivalent string is
    rebuilt from the component fields.

    Essential and optional skills are kept as SEPARATE metadata fields so
    the re-ranker can weight an essential match above an optional one.
    """
    logger.info("Reading data from %s...", csv_path)
    df = pd.read_csv(csv_path)
    logger.info("  %d rows, %d unique occupations", len(df), df["occupation_title"].nunique())

    docs = []
    for _, row in df.iterrows():
        title = _clean(row["occupation_title"])
        uri = _clean(row["conceptUri"])
        alt_labels = _clean(row.get("alt_occupation_title"))
        description = _clean(row.get("occ_description"))
        essential = _split_skills(row.get("essential_skills_text"))
        optional = _split_skills(row.get("optional_skills_text"))

        text_payload = _clean(row.get("career_role_context"))
        if not text_payload:
            parts = [f"Occupation title: {title}."]
            if alt_labels:
                parts.append(f"Alternative titles: {alt_labels}.")
            if description:
                parts.append(f"Description: {description}.")
            if essential:
                parts.append(f"Essential skills: {'; '.join(essential)}.")
            if optional:
                parts.append(f"Optional or related skills: {'; '.join(optional)}.")
            text_payload = " ".join(parts)

        metadata = {
            "occupation_title": title,
            "occupation_uri": uri,
            "alt_occupation_title": alt_labels,
            "occ_description": description,
            "essential_skills": "; ".join(essential),
            "optional_skills": "; ".join(optional),
            "essential_skill_count": len(essential),
            "optional_skill_count": len(optional),
            "isco_group": _clean(row.get("isco_group")),
            "occupation_code": _clean(row.get("occupation_code")),
        }
        docs.append(Document(page_content=text_payload, metadata=metadata))

    return docs


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------

def _connect():
    load_dotenv(find_dotenv())
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("SUPABASE_DB_URL is missing from .env")
    return psycopg2.connect(db_url)


def _to_pgvector(vec) -> str:
    """pgvector literal format. Passing a JSON list here is what produced
    the corrupt embeddings, so the format matters."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


def build_vector_store() -> None:
    """Truncates `documents` and rewrites the full ESCO index."""
    docs = prepare_documents(CareerRecommendationModuleConfig.ESCO_DATA_PATH)
    logger.info("Prepared %d occupation documents.", len(docs))

    is_gemini = GlobalConfig.EMBEDDING_PROVIDER == "gemini"
    model_name = GlobalConfig.GEMINI_EMBEDDING_MODEL if is_gemini else GlobalConfig.HF_EMBEDDING_MODEL
    batch_size = GEMINI_BATCH if is_gemini else BATCH

    logger.info(
        "Provider: %s | Model: %s | Dims: %s",
        GlobalConfig.EMBEDDING_PROVIDER, model_name, GlobalConfig.EMBEDDING_DIM,
    )

    conn = _connect()
    cur = conn.cursor()

    cur.execute("TRUNCATE documents;")
    conn.commit()
    logger.info("Cleared documents table")

    total = len(docs)
    for start in range(0, total, batch_size):
        chunk = docs[start:start + batch_size]
        vecs = document_embeddings.embed_documents([d.page_content for d in chunk])

        rows = [
            (d.page_content, json.dumps(d.metadata), _to_pgvector(vec))
            for d, vec in zip(chunk, vecs)
        ]
        execute_batch(
            cur,
            "INSERT INTO documents (content, metadata, embedding) "
            "VALUES (%s, %s::jsonb, %s::vector)",
            rows,
            page_size=batch_size,
        )
        conn.commit()
        logger.info("  inserted %d/%d", min(start + batch_size, total), total)

        if is_gemini and start + batch_size < total:
            import time
            time.sleep(GEMINI_PAUSE_SECONDS)

    cur.close()
    conn.close()
    logger.info("Index rebuilt.")

    verify()


# ---------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------

def verify() -> bool:
    """
    Confirms the stored vectors are real embeddings and not corrupt.

    Checks row count, uniqueness, that a stored vector is unit-normalised,
    and that re-embedding a document's own text reproduces its stored
    vector (cosine ~1.0). That last check is the one that caught the
    langchain write bug.
    """
    conn = _connect()
    cur = conn.cursor()

    cur.execute("SELECT count(*), count(DISTINCT metadata->>'occupation_uri') FROM documents;")
    total, unique = cur.fetchone()
    logger.info("Rows: %d  |  unique occupation_uri: %d", total, unique)

    if total == 0:
        logger.error("Table is empty — run without --verify to build the index.")
        cur.close(); conn.close()
        return False

    cur.execute("""
        SELECT content, metadata->>'occupation_title', embedding::text
        FROM documents
        WHERE metadata->>'occupation_title' IS NOT NULL
        LIMIT 1;
    """)
    content, title, emb_text = cur.fetchone()
    cur.close()
    conn.close()

    stored = json.loads(emb_text)
    norm = math.sqrt(sum(v * v for v in stored))

    reference = document_embeddings.embed_documents([content])[0]
    dot = sum(a * b for a, b in zip(stored, reference))
    rnorm = math.sqrt(sum(v * v for v in reference))
    cosine = dot / (norm * rnorm) if norm and rnorm else 0.0

    logger.info("Sample occupation : %s", title)
    logger.info("Dimensions        : %d (expected %d)", len(stored), GlobalConfig.EMBEDDING_DIM)
    logger.info("Stored L2 norm    : %.4f (expected ~1.0)", norm)
    logger.info("Self-similarity   : %.4f (expected ~1.0)", cosine)

    ok = (
        total == unique
        and len(stored) == GlobalConfig.EMBEDDING_DIM
        and abs(norm - 1.0) < 0.05
        and cosine > 0.99
    )
    if ok:
        logger.info("VERIFIED — index is healthy.")
    else:
        logger.error(
            "FAILED — vectors do not match a re-embedding of their own text, "
            "or the index contains duplicates. Rebuild the index."
        )
    return ok


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Build or verify the ESCO vector index.")
    parser.add_argument("--verify", action="store_true", help="Check the existing index without rebuilding.")
    args = parser.parse_args()

    if args.verify:
        verify()
    else:
        build_vector_store()
