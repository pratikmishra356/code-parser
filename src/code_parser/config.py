"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "code-parser"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser"
    )

    # Worker settings
    worker_count: int = 4
    job_poll_interval_seconds: float = 1.0
    max_files_per_batch: int = 100

    # Parsing settings
    max_file_size_bytes: int = 1_000_000  # 1MB
    parse_timeout_seconds: int = 30

    # AI / LLM settings
    claude_bedrock_url: str = ""  # Set via CLAUDE_BEDROCK_URL env var or CodeCircle AI Settings
    claude_model_id: str = ""  # Set via CLAUDE_MODEL_ID env var or CodeCircle AI Settings
    claude_api_key: str | None = None  # Set via CLAUDE_API_KEY env var or CodeCircle AI Settings

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @property
    def database_url_sync(self) -> str:
        """Return sync database URL for Alembic."""
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

