"""Application settings, loaded once from the environment / `.env`."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- app ---
    app_name: str = "DSAI Backend"
    # `DEBUG` is commonly injected by shells, IDEs, and other tooling with
    # non-boolean values such as "release". Use an application-specific name
    # so unrelated process configuration cannot prevent the backend starting.
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- database ---
    database_url: str = "postgresql+asyncpg://dsai:dsai@localhost:5432/dsai"
    db_echo: bool = False
    database_pool_size: int = 2
    database_max_overflow: int = 1

    # --- auth (dev resolver; Google SSO replaces this later) ---
    dev_user_id: str = "dev-user"
    dev_user_email: str = "dev@example.com"

    # --- encryption at rest (Fernet, urlsafe base64 32-byte key) ---
    # Generate one with:
    #   python -c "from cryptography.fernet import Fernet; \
    #              print(Fernet.generate_key().decode())"
    profile_encryption_key: str = ""

    # --- Google AI Studio (resume parsing) ---
    google_api_key: str = ""
    google_ai_studio_api_key: str = ""
    resume_primary_model: str = "gemini-3.5-flash-lite"
    resume_fallback_model: str = "gemini-2.5-flash"
    resume_request_timeout_seconds: float = 120.0
    # How scanned/image-only PDFs reach the LLM. `direct_vision` is the
    # production baseline; `docling_text` enables the experimental OCR/layout
    # branch while keeping the downstream prompt and schema unchanged.
    resume_scanned_pdf_strategy: Literal["direct_vision", "docling_text"] = (
        "direct_vision"
    )

    # --- resume parsing limits ---
    resume_max_upload_bytes: int = 10 * 1024 * 1024
    resume_max_pages: int = 10
    resume_render_dpi: int = 150
    resume_text_layer_min_chars: int = 100
    resume_completeness_threshold: float = 0.4

    @property
    def effective_google_api_key(self) -> str:
        """One shared key, with the old resume-specific name kept as an alias."""
        return self.google_api_key or self.google_ai_studio_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()


class GlobalConfig:
    """Application-wide configuration for the Career Recommendation stack."""

    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_AI_STUDIO_API_KEY")

    # Raw datasets live at the PROJECT root, not under backend/.
    DATA_DIR = BASE_DIR.parent / "data"

    # --- embeddings ---
    # "huggingface" -> BAAI/bge-base-en-v1.5, local CPU, no quota
    # "gemini"      -> hosted, quota-limited (free tier: ~100 req/min,
    #                  ~1,000/day against 3,039 occupations)
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "huggingface")
    HF_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
    GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

    # --- vector store (Supabase pgvector) ---
    # Connection details are read from the environment by
    # db/supabase_manager.py and career_recommendation/ingestion.py:
    #   SUPABASE_URL, SUPABASE_SERVICE_KEY   (PostgREST / langchain reads)
    #   SUPABASE_DB_URL                      (direct psycopg2 writes)
    SUPABASE_TABLE = os.getenv("SUPABASE_TABLE", "documents")
    SUPABASE_QUERY_FN = os.getenv("SUPABASE_QUERY_FN", "match_documents")

    # --- LLM ---
    LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-3.5-flash-lite")


if not GlobalConfig.GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY or GOOGLE_AI_STUDIO_API_KEY is not set. Please check your .env file."
    )
