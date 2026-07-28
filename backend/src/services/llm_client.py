from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from core.config import GlobalConfig

# Shared Embedding Model
# embeddings = GoogleGenerativeAIEmbeddings(
#     model=GlobalConfig.EMBEDDING_MODEL,
#     google_api_key=GlobalConfig.GOOGLE_API_KEY
# )

embeddings = HuggingFaceEmbeddings(
    model_name=GlobalConfig.EMBEDDING_MODEL
)

# Initialize shared LLM
llm = ChatGoogleGenerativeAI(
    model=GlobalConfig.LLM_MODEL,
    google_api_key=GlobalConfig.GOOGLE_API_KEY,
    temperature=0.0
)