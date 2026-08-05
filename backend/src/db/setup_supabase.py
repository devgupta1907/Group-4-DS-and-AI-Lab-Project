import os
import psycopg2
from dotenv import load_dotenv, find_dotenv


SQL = """
-- 1. pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. documents table
CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content text,
  metadata jsonb,
  embedding vector(768)
);

-- 3. remove any mismatched signatures of match_documents
DROP FUNCTION IF EXISTS public.match_documents(vector, int, jsonb);
DROP FUNCTION IF EXISTS public.match_documents(vector, jsonb);

-- 4. LangChain-compatible signature.
--    langchain-community sends only query_embedding (+ filter when non-empty)
--    and applies k as a client-side LIMIT, so there is no match_count
--    parameter and no LIMIT inside the function.
CREATE OR REPLACE FUNCTION public.match_documents (
  query_embedding vector(768),
  filter jsonb DEFAULT '{}'::jsonb
) RETURNS TABLE (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) AS similarity
  FROM documents
  WHERE documents.metadata @> filter
  ORDER BY documents.embedding <=> query_embedding;
END;
$$;

-- 5. ANN index for cosine distance
CREATE INDEX IF NOT EXISTS documents_embedding_idx
  ON public.documents USING hnsw (embedding vector_cosine_ops);

-- 6. make PostgREST pick up the new signature immediately
NOTIFY pgrst, 'reload schema';
"""


def setup_database():
    load_dotenv(find_dotenv())

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("SUPABASE_DB_URL is missing from .env")

    conn = None
    try:
        print("Connecting to Supabase PostgreSQL...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        print("Executing schema initialization...")
        cur.execute(SQL)
        conn.commit()

        # verify what landed
        cur.execute("""
            SELECT p.oid::regprocedure::text
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname = 'match_documents';
        """)
        print("match_documents signatures now present:")
        for row in cur.fetchall():
            print("  ", row[0])

        cur.execute("""
            SELECT count(*), count(DISTINCT metadata->>'occupation_uri')
            FROM documents;
        """)
        total, uniq = cur.fetchone()
        print(f"documents: {total} rows, {uniq} unique occupation_uri")

        cur.close()
        print("Success.")
    except Exception as e:
        print(f"Error setting up database: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    setup_database()