"""Environment-backed settings with validation for paired Supabase values."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:3000")

    supabase_url: AnyHttpUrl | None = None
    supabase_publishable_key: SecretStr | None = None
    supabase_secret_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_raw_bucket: str = "dst-wiki-raw"

    wiki_base_url: AnyHttpUrl = AnyHttpUrl("https://dontstarve.wiki.gg")
    wiki_api_url: AnyHttpUrl = AnyHttpUrl("https://dontstarve.wiki.gg/api.php")
    wiki_user_agent: str = (
        "DSTVietnameseAssistant/0.2 "
        "(https://github.com/FlynnBui399/Vietnamese-DontStarveTogether-RAG)"
    )
    wiki_request_delay_ms: int = 500
    wiki_max_concurrency: int = Field(default=1, ge=1, le=1)
    wiki_request_timeout_seconds: float = 20.0
    wiki_max_retries: int = 3
    wiki_cache_dir: Path = Path("data/cache/mediawiki")
    wiki_cache_ttl_seconds: int = 3600

    embedding_dimensions: int = Field(default=1024, gt=0)

    @model_validator(mode="after")
    def validate_supabase_pair(self) -> Self:
        """Require a URL and key together while allowing an unconfigured local app."""
        has_key = self.supabase_api_key is not None
        if (self.supabase_url is None) != (not has_key):
            raise ValueError("SUPABASE_URL and a Supabase API key must be configured together")
        return self

    @property
    def supabase_api_key(self) -> SecretStr | None:
        """Prefer modern server credentials while retaining local/legacy compatibility."""
        return (
            self.supabase_secret_key
            or self.supabase_service_role_key
            or self.supabase_publishable_key
        )

    @property
    def supabase_configured(self) -> bool:
        """Return whether the minimum values for a connectivity probe are available."""
        return self.supabase_url is not None and self.supabase_api_key is not None

    @property
    def supabase_admin_api_key(self) -> SecretStr | None:
        """Return only a server-side key suitable for ingestion writes."""
        return self.supabase_secret_key or self.supabase_service_role_key


@lru_cache
def get_settings() -> Settings:
    """Build settings once per process."""
    return Settings()
