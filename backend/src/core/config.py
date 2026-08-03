import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class GlobalConfig:
    """Application-wide configuration."""
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    DATA_DIR = BASE_DIR.parent / "data"
    DB_DIR = BASE_DIR / "src/data"

    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "gemini")
    HF_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
    GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

    CHROMA_DB_DIR_BGE = str(DB_DIR / "chroma_db")
    CHROMA_DB_DIR_GEMINI = str(DB_DIR / "chroma_db_gemini")

    _default_dir = CHROMA_DB_DIR_GEMINI if EMBEDDING_PROVIDER == "gemini" else CHROMA_DB_DIR_BGE
    CHROMA_DB_DIR = str(DB_DIR / os.getenv("CHROMA_SUBDIR")) if os.getenv("CHROMA_SUBDIR") else _default_dir

    CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "esco_occupations")

    LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-3.5-flash-lite")


if not GlobalConfig.GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set. Please check your .env file.")