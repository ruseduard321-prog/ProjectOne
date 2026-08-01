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

from pydantic import Field, SecretStr, ValidationError
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

    # Supabase / PostgreSQL. Required: the API is not useful without its
    # database, and a process that starts without one only fails later, on a
    # request, somewhere less obvious.
    #
    # These carry explicit aliases because they are named by Supabase, not by
    # ProjectOne — the PROJECTONE_ prefix would make them PROJECTONE_SUPABASE_URL,
    # which no Supabase documentation, dashboard or tutorial would ever show.
    #
    # SecretStr keeps the values out of logs, tracebacks and repr() output: it
    # renders as "**********" unless explicitly unwrapped with
    # .get_secret_value() (CLAUDE.md §16, §25).
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_secret_key: SecretStr = Field(alias="SUPABASE_SECRET_KEY")

    # The **privileged** connection, connecting as `postgres`. Correct for
    # Alembic, which must create tables and policies, and wrong for serving
    # requests: `postgres` carries `rolbypassrls`, so every RLS policy is
    # skipped for it (STEP-09, RLS Policy Pattern).
    #
    # Nothing on the request path may use this. `request_database_url` below is
    # what serves requests, and the split is the whole point.
    database_url: SecretStr = Field(alias="DATABASE_URL")

    # The **request-path** connection, connecting as a role WITHOUT
    # `rolbypassrls` (`authenticator`). Every tenant query goes over this one so
    # the STEP-09 policies actually apply — see AuthenticatedSession.
    #
    # Required, deliberately with no fallback to `database_url`: a default that
    # silently reused the privileged connection would turn a missing variable
    # into total, invisible loss of tenant isolation. Failing to start is the
    # only safe behaviour (CLAUDE.md §16).
    request_database_url: SecretStr = Field(alias="REQUEST_DATABASE_URL")

    # Bounded on purpose. A health check that can hang holds a worker and turns
    # a degraded database into an unresponsive API — the failure mode the check
    # exists to report, caused by the check itself.
    database_health_timeout_seconds: int = 5

    # How long a fetched JWKS key set is trusted before being re-fetched.
    # Supabase rotates signing keys, and a cache with no expiry would keep
    # rejecting valid tokens after a rotation until the process restarted.
    jwks_cache_seconds: int = 600

    # Bounded so a slow or unreachable Supabase cannot hold a request worker
    # open indefinitely.
    supabase_timeout_seconds: int = 10

    @property
    def supabase_auth_url(self) -> str:
        """Return the base URL of the Supabase Auth (GoTrue) API."""
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwt_issuer(self) -> str:
        """Return the `iss` claim value tokens from this project must carry.

        Verified rather than ignored: a signature check alone would accept a
        correctly-signed token issued by a *different* Supabase project.
        """
        return self.supabase_auth_url


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
