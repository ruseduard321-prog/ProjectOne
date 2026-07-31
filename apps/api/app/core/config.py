"""Application configuration.

Settings are read from the environment, never hardcoded, and never
environment-conditional in application code (CLAUDE.md 28a). Configuration
changes behavior; it does not select code paths.

Validation happens once, at startup, through `get_settings()`. A missing or
malformed required variable stops the process with a message naming the
variable -- it never surfaces as a confusing failure at first use, hours later,
in a request handler.
"""

import sys
from enum import StrEnum
from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """The deployment environments ProjectOne runs in.

    Strictly isolated from each other -- separate credentials, separate data,
    separate AI provider keys (CLAUDE.md 28a). A value outside this set is a
    misconfiguration, not a new environment, so it fails validation.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Environment-driven settings for the API application.

    Fields without a default are **required**: the application will not start
    without them. Fields with a default are genuinely optional, and the default
    is the safe choice rather than the convenient one.
    """

    model_config = SettingsConfigDict(
        env_prefix="PROJECTONE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required. Deliberately has no default: defaulting to "development" would
    # mean a production deploy that forgets this variable starts anyway, in the
    # wrong mode, silently. Failing loudly is the safer outcome.
    environment: Environment

    app_name: str = "ProjectOne API"
    version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Cached so configuration is parsed and validated once. Exposed through
    FastAPI's dependency system rather than imported as a global, so tests can
    override it without patching module state (CLAUDE.md 12).

    Raises:
        SystemExit: if required configuration is missing or invalid. The
            message names every offending variable. Exiting rather than
            propagating a `ValidationError` keeps the startup failure readable
            for whoever is reading a container log at 3am; the detail is not
            lost, it is reformatted.
    """
    try:
        # mypy sees a required field with no argument passed and reports a
        # missing argument. That is exactly the intent: pydantic-settings
        # populates required fields from the environment at runtime, which the
        # type checker cannot see. Narrowly ignored here rather than given a
        # default, because a default is what this design is avoiding.
        return Settings()  # type: ignore[call-arg]
    except ValidationError as error:
        details = "\n".join(
            f"  - {Settings.model_config['env_prefix']}{str(item['loc'][0]).upper()}: {item['msg']}"
            for item in error.errors()
        )
        sys.exit(
            "ProjectOne API cannot start: environment configuration is invalid.\n"
            f"{details}\n"
            "See apps/api/.env.example for the required variables."
        )
