"""Application settings, loaded once from the environment / `.env`."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- app ---
    app_name: str = "DSAI Backend"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- database ---
    database_url: str = "postgresql+asyncpg://dsai:dsai@localhost:5432/dsai"
    db_echo: bool = False

    # --- auth (dev resolver; Google SSO replaces this later) ---
    dev_user_id: str = "dev-user"
    dev_user_email: str = "dev@example.com"

    # --- encryption at rest (Fernet, urlsafe base64 32-byte key) ---
    # Generate one with:
    #   python -c "from cryptography.fernet import Fernet; \
    #              print(Fernet.generate_key().decode())"
    profile_encryption_key: str = ""

    # --- Google AI Studio (resume parsing) ---
    google_ai_studio_api_key: str = ""
    resume_primary_model: str = "gemma-3-27b-it"
    resume_fallback_model: str = "gemini-2.5-flash"
    resume_request_timeout_seconds: float = 120.0

    # --- resume parsing limits ---
    resume_max_upload_bytes: int = 10 * 1024 * 1024
    resume_max_pages: int = 10
    resume_render_dpi: int = 150
    resume_text_layer_min_chars: int = 100
    resume_completeness_threshold: float = 0.4


@lru_cache
def get_settings() -> Settings:
    return Settings()
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
