from langchain_chroma import Chroma

from services.llm_client import query_embeddings
from core.config import GlobalConfig


def get_vector_store() -> Chroma:
    return Chroma(
        collection_name=GlobalConfig.CHROMA_COLLECTION,
        persist_directory=GlobalConfig.CHROMA_DB_DIR,
        embedding_function=query_embeddings,
    )