from langchain_chroma import Chroma
from services.llm_client import embeddings
from core.config import GlobalConfig

def get_vector_store() -> Chroma:
    """
    Returns a configured instance of the Chroma vector store.
    All modules should call this function to interact with the DB.
    """

    return Chroma(
        persist_directory=GlobalConfig.CHROMA_DB_DIR,
        embedding_function=embeddings
    )


