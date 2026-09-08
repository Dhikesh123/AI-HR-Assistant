"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central settings object. Never hard-code secrets - everything comes from env."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -------------------------------------------------------
    APP_NAME: str = "AI HR Assistant"
    COMPANY_NAME: str = "Acme Corp"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- LLM -----------------------------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 600
    LLM_TIMEOUT_SECONDS: int = 60

    # --- Embeddings ----------------------------------------------------
    # auto | openai | sentence_transformers | local
    EMBEDDING_PROVIDER: str = "auto"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    ST_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    LOCAL_EMBEDDING_DIM: int = 512

    # --- RAG -----------------------------------------------------------
    TOP_K: int = 4
    CHUNK_SIZE: int = 900
    CHUNK_OVERLAP: int = 150
    MIN_RELEVANCE_SCORE: float = 0.15
    CHROMA_DIR: str = str(BASE_DIR / "chroma_db")
    CHROMA_COLLECTION: str = "hr_documents"
    HISTORY_TURNS: int = 4

    # --- Database ------------------------------------------------------
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'hr_assistant.db').as_posix()}"

    # --- Auth ----------------------------------------------------------
    JWT_SECRET_KEY: str = "change_this_secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # --- Uploads -------------------------------------------------------
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_MB: int = 20
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".docx", ".txt", ".md"]

    # --- Bootstrap demo accounts --------------------------------------
    SEED_ADMIN_EMAIL: str = "admin@acme.com"
    SEED_ADMIN_PASSWORD: str = "Admin@123"
    SEED_EMPLOYEE_EMAIL: str = "employee@acme.com"
    SEED_EMPLOYEE_PASSWORD: str = "Employee@123"

    # --- Frontend ------------------------------------------------------
    API_BASE_URL: str = "http://127.0.0.1:8000"

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def llm_enabled(self) -> bool:
        return bool(self.OPENAI_API_KEY.strip())


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()


settings = get_settings()
