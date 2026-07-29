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
