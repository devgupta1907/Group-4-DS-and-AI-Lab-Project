from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

from src.core.config import GlobalConfig


def _build_embeddings(task_type: str):
    if GlobalConfig.EMBEDDING_PROVIDER == "gemini":
        return GoogleGenerativeAIEmbeddings(
            model=GlobalConfig.GEMINI_EMBEDDING_MODEL,
            google_api_key=GlobalConfig.GOOGLE_API_KEY,
            task_type=task_type,
            output_dimensionality=GlobalConfig.EMBEDDING_DIM,
        )
    return HuggingFaceEmbeddings(model_name=GlobalConfig.HF_EMBEDDING_MODEL)

_IS_GEMINI = GlobalConfig.EMBEDDING_PROVIDER == "gemini"
document_embeddings = _build_embeddings("RETRIEVAL_DOCUMENT")
query_embeddings = _build_embeddings("RETRIEVAL_QUERY") if _IS_GEMINI else document_embeddings
embeddings = query_embeddings

llm = ChatGoogleGenerativeAI(
    model=GlobalConfig.LLM_MODEL,
    google_api_key=GlobalConfig.GOOGLE_API_KEY,
    temperature=0.0,
)
