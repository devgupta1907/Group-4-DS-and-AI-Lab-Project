import os
from supabase.client import create_client, Client
from langchain_community.vectorstores import SupabaseVectorStore

# Import your BAAI embedding model from wherever you initialized it
from src.services.llm_client import embeddings

def get_vector_store() -> SupabaseVectorStore:
    """
    Initializes and returns the Supabase pgvector store instance.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("Missing Supabase credentials in .env")

    supabase: Client = create_client(supabase_url, supabase_key)
    
    return SupabaseVectorStore(
        client=supabase,
        embedding=embeddings,
        table_name="documents",
        query_name="match_documents"
    )