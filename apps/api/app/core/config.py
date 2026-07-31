"""Application configuration.

Settings are read from the environment, never hardcoded, and never
environment-conditional in application code (CLAUDE.md 28a). The real secrets
wiring lands in STEP-05; this holds only what the skeleton needs to start.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings for the API application."""

    model_config = SettingsConfigDict(
        env_prefix="PROJECTONE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ProjectOne API"
    environment: str = "development"
    version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Cached so configuration is parsed once. Exposed through FastAPI's
    dependency system rather than imported as a global, so tests can override
    it without patching module state (CLAUDE.md 12).
    """
    return Settings()
