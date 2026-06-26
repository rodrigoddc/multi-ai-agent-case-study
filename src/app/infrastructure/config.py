"""Application settings aggregate and validation."""

import logging

from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parents[3]
ENV_FILE = BASE_DIR / "src" / ".env"

logger = logging.getLogger(__name__)
logging.debug(f"Loading application settings from '{ENV_FILE}'")


class EnvSettings(BaseSettings):
    """Base settings class that reads from process env and project .env."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AppEnvironment(StrEnum):
    """Supported application runtime environments."""

    LOCAL = "local"
    TEST = "test"
    DEV = "dev"
    PROD = "prod"


class DatabaseSettings(EnvSettings):
    """Database settings and URL builders."""

    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    DB_HOST: str
    DB_PORT: int
    DATABASE_URL: str

    def sqlalchemy_url(self) -> str:
        """Build SQLAlchemy asyncio URL for psycopg3."""
        if self.DATABASE_URL and "$" not in self.DATABASE_URL:
            return _normalize_sqlalchemy_async_url(self.DATABASE_URL)
        password = self.POSTGRES_PASSWORD.get_secret_value()
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"

    def psycopg_url(self) -> str:
        """Build plain psycopg URL for LangGraph persistence."""
        if self.DATABASE_URL and "$" not in self.DATABASE_URL:
            return _normalize_psycopg_url(self.DATABASE_URL)
        password = self.POSTGRES_PASSWORD.get_secret_value()
        return f"postgresql://{self.POSTGRES_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"


def _normalize_sqlalchemy_async_url(url: str) -> str:
    """Normalize Postgres URLs to SQLAlchemy's psycopg3 asyncio dialect."""
    clean_url = url.strip()
    if clean_url.startswith("postgresql+psycopg://"):
        return clean_url
    if clean_url.startswith("postgresql+asyncpg://"):
        return clean_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if clean_url.startswith("postgresql://"):
        return clean_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return clean_url


def _normalize_psycopg_url(url: str) -> str:
    """Normalize Postgres URLs to a plain psycopg DSN."""
    clean_url = url.strip()
    if clean_url.startswith("postgresql+psycopg://"):
        return clean_url.replace("postgresql+psycopg://", "postgresql://", 1)
    if clean_url.startswith("postgresql+asyncpg://"):
        return clean_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return clean_url


class LangfuseSettings(EnvSettings):
    """Langfuse observability configuration."""

    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: SecretStr
    LANGFUSE_HOST: str


class LLMSettings(EnvSettings):
    """Generic LLM provider configuration."""

    LLM_PROVIDER: str
    LLM_PROVIDER_API_KEY: SecretStr
    LLM_PROVIDER_MODEL: str
    LLM_TIMEOUT_SECONDS: float = Field(default=300.0)


class LlamaCppSettings(LLMSettings):
    """Local llama.cpp OpenAI-compatible server settings."""

    LLAMACPP_BASE_URL: str


class ServerSettings(EnvSettings):
    """HTTP server settings."""

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")


class FeatureSettings(EnvSettings):
    """Feature flags controlled by app strategy and env."""

    persistence_enabled: bool = True
    auto_create_tables: bool = False
    langfuse_required: bool = True
    mount_static: bool = True


class AppSettings(EnvSettings):
    """Typed aggregate of runtime settings."""

    APP_ENV: AppEnvironment


database: DatabaseSettings = DatabaseSettings()
llm: LLMSettings = LLMSettings()
llama_cpp: LlamaCppSettings = LlamaCppSettings()
langfuse: LangfuseSettings = LangfuseSettings()
server: ServerSettings = ServerSettings()
features: FeatureSettings = FeatureSettings()
settings = AppSettings()
