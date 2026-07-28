import os
from pathlib import Path
from dotenv import load_dotenv

# Absolute path to the backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

class GlobalConfig:
    """Application-wide configuration."""
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # Global Paths
    DATA_DIR = BASE_DIR / "data"
    DB_DIR = BASE_DIR / "src/data"
    CHROMA_DB_DIR = str(DB_DIR / "chroma_db")
    
    # Shared Model Names
    # EMBEDDING_MODEL = "models/gemini-embedding-001"
    EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
    LLM_MODEL = "gemini-2.5-flash-lite"

if not GlobalConfig.GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set. Please check your .env file.")