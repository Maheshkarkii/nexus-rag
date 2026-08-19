"""Application settings and environment configuration management using Pydantic Settings."""

import json
import logging
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("ai_research_assistant.config")

EnvironmentType = Literal["development", "testing", "production"]


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --------------------------------------------------------------------------
    # 1. Application Settings
    # --------------------------------------------------------------------------
    APP_NAME: str = "AI Research Assistant"
    APP_ENV: EnvironmentType = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # --------------------------------------------------------------------------
    # 2. API Prefix & Server Settings
    # --------------------------------------------------------------------------
    API_V1_STR: str = "/api/v1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # --------------------------------------------------------------------------
    # 3. CORS Settings
    # --------------------------------------------------------------------------
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from JSON array, comma-separated string, or Python list."""
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    parsed = json.loads(v_trimmed)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if item]
                except Exception:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        elif isinstance(v, list):
            return [str(item).strip() for item in v if item]
        return ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"]

    # --------------------------------------------------------------------------
    # 4. PostgreSQL Relational Database Settings
    # --------------------------------------------------------------------------
    POSTGRES_SERVER: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ai_research_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_dev_password"
    DATABASE_URL: str | None = None

    @property
    def async_database_url(self) -> str:
        """Construct the async database URL for AsyncPG / SQLAlchemy with fallback for local dev."""
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            url = self.DATABASE_URL.strip()
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        # In non-Docker local dev without a postgres container running, fallback to SQLite
        if self.POSTGRES_SERVER == "localhost" or self.POSTGRES_SERVER == "127.0.0.1":
            return (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """Construct synchronous database URL (e.g. for migrations)."""
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            url = self.DATABASE_URL.strip()
            if url.startswith("postgresql+asyncpg://"):
                return url.replace("postgresql+asyncpg://", "postgresql://", 1)
            return url
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --------------------------------------------------------------------------
    # 5. Storage & File Ingestion Settings (Stage 8)
    # --------------------------------------------------------------------------
    STORAGE_PATH: str = "storage"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [
        ".pdf",
        ".docx",
        ".txt",
        ".csv",
        ".xlsx",
        ".xls",
        ".json",
    ]

    @property
    def storage_directory(self) -> Path:
        """Get absolute path to local storage directory."""
        return Path(self.STORAGE_PATH).resolve()

    @property
    def max_upload_size_bytes(self) -> int:
        """Convert max upload size from megabytes to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def get_project_storage_directory(self, project_id: uuid.UUID) -> Path:
        """Get absolute storage directory for a specific research project."""
        return self.storage_directory / "projects" / str(project_id)

    # --------------------------------------------------------------------------
    # 6. Intelligent Chunking Settings (Stage 10)
    # --------------------------------------------------------------------------
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    MIN_CHUNK_SIZE: int = 50
    MAX_CHUNK_SIZE: int = 800

    # --------------------------------------------------------------------------
    # 7. Qdrant Vector Store Settings
    # --------------------------------------------------------------------------
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "research_documents"
    QDRANT_UPSERT_BATCH_SIZE: int = 100
    QDRANT_TIMEOUT: int = 60

    # --------------------------------------------------------------------------
    # 8. Reranker & Context Optimization Settings
    # --------------------------------------------------------------------------
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_BATCH_SIZE: int = 32
    RERANKER_SCORE_THRESHOLD: float | None = None
    RETRIEVAL_CANDIDATE_K: int = 20
    FINAL_CONTEXT_K: int = 5
    MAX_CONTEXT_TOKENS: int = 2048

    # Stage 19 Comparison settings
    MAX_DOCUMENTS_FOR_COMPARISON: int = 10
    MAX_CHUNKS_PER_DOCUMENT: int = 4
    MIN_CHUNKS_PER_DOCUMENT: int = 1
    COMPARISON_CONTEXT_BUDGET: int = 4096

    # Stage 20 Research Planning settings
    MAX_RESEARCH_STEPS: int = 5
    MAX_RESEARCH_DEPTH: int = 3
    MAX_RESEARCH_LLM_CALLS: int = 10
    RESEARCH_CONTEXT_BUDGET: int = 8192

    # Stage 21 Report & Export settings
    MAX_REPORT_SECTIONS: int = 8
    MAX_SECTION_LENGTH: int = 2000
    MAX_REPORT_CONTEXT: int = 12288

    # Stage 22 Data Analysis settings
    MAX_ANALYSIS_ROWS: int = 100000
    MAX_GROUPS: int = 100
    MAX_RESULT_ROWS: int = 500
    MAX_COLUMNS: int = 100

    # Stage 23 Hybrid Retrieval & Search Optimization settings
    SEMANTIC_WEIGHT: float = 0.7
    LEXICAL_WEIGHT: float = 0.3
    INITIAL_RETRIEVAL_K: int = 50
    RERANK_K: int = 20
    MIN_RELEVANCE_THRESHOLD: float = -10.0
    ENABLE_RETRIEVAL_CACHE: bool = True

    # Stage 26 Production Scalability & Background Jobs settings
    MAX_CONCURRENT_JOBS: int = 5
    EMBEDDING_BATCH_SIZE: int = 32
    JOB_TIMEOUT_SECONDS: int = 600
    MAX_JOB_RETRIES: int = 3

    # --------------------------------------------------------------------------
    # 8. Future AI & Cache Settings (Stage 11+)
    # --------------------------------------------------------------------------
    REDIS_URL: str | None = None
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "groq/compound-mini"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_OUTPUT_TOKENS: int = 1000
    LLM_TIMEOUT: int = 30
    CONVERSATION_HISTORY_LIMIT: int = 10
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "auto"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_NORMALIZE: bool = True

    # --------------------------------------------------------------------------
    # Helper Properties & Environment Validation
    # --------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """Check if currently running in production environment."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if currently running in development environment."""
        return self.APP_ENV == "development"

    @property
    def is_testing(self) -> bool:
        """Check if currently running in testing environment."""
        return self.APP_ENV == "testing"

    @model_validator(mode="after")
    def validate_environment_settings(self) -> "Settings":
        """Enforce stricter security checks for production environments."""
        if self.is_production:
            if self.DEBUG:
                logger.warning(
                    "Security Warning: DEBUG mode is enabled in production! Setting DEBUG=False recommended."
                )
            if self.POSTGRES_PASSWORD == "postgres_dev_password":
                logger.warning(
                    "Security Warning: Default development database password in use in production environment."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    return Settings()
