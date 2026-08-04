import os
import psycopg2
from dotenv import load_dotenv, find_dotenv

def setup_database():
    # find_dotenv() will automatically locate the .env file in the project root
    load_dotenv(find_dotenv())
    
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("SUPABASE_DB_URL is missing from .env")

    # The SQL instructions to initialize pgvector, the table, and the search function
    sql_commands = """
    -- 1. Enable the pgvector extension
    CREATE EXTENSION IF NOT EXISTS vector;

    -- 2. Create a table to store your chunks and embeddings
    CREATE TABLE IF NOT EXISTS documents (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      content text,
      metadata jsonb,
      embedding vector(768)
    );

    -- 3. Create the LangChain similarity search RPC function
    CREATE OR REPLACE FUNCTION match_documents (
      query_embedding vector(768),
      match_count int,
      filter jsonb DEFAULT '{}'
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
        id,
        content,
        metadata,
        1 - (documents.embedding <=> query_embedding) AS similarity
      FROM documents
      WHERE metadata @> filter
      ORDER BY documents.embedding <=> query_embedding
      LIMIT match_count;
    END;
    $$;
    """

    try:
        # Connect directly to the PostgreSQL database
        print("Connecting to Supabase PostgreSQL...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Execute the SQL
        print("Executing schema initialization...")
        cur.execute(sql_commands)
        conn.commit()
        
        print("Success: Supabase pgvector schema initialized!")
        
    except Exception as e:
        print(f"Error setting up database: {e}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    setup_database()