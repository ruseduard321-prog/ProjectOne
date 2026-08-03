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
from ipaddress import IPv4Network, IPv6Network

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.client_address import parse_trusted_proxies


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

    # Peers permitted to set forwarding headers, as CIDR ranges or bare
    # addresses (ADR-002 §3). Comma-separated; parsed by
    # `trusted_proxy_networks` below.
    #
    # **Defaults to empty, and empty means trust nothing.** A default that
    # trusted loopback would be wrong in the one deployment shape that matters:
    # a container behind a sidecar sees the sidecar on a private address, not on
    # 127.0.0.1, while a misconfigured production API exposed directly to the
    # internet would start honouring forged headers the moment someone ran it
    # behind any local process. Empty degrades to peer-address limiting, which
    # is weaker but never forgeable (CLAUDE.md §16).
    trusted_proxies: str = ""

    # Optional single-hop header a platform overwrites on every request --
    # Cloudflare's `CF-Connecting-IP` is the canonical one. Honoured only when
    # the peer is already trusted, because such a header is trustworthy solely
    # because the platform rewrites it, which holds only if the request actually
    # came from that platform.
    #
    # Empty means "use X-Forwarded-For only". Not defaulted to a vendor's header
    # name: a default naming a CDN the deployment does not use would silently
    # honour a header any client could send once a proxy is trusted.
    client_address_header: str = ""

    # The AES-256 key BYOK provider credentials are encrypted with, base64
    # encoded (32 bytes -> 44 characters). Required: the alternative to a
    # configured key is storing provider keys in plaintext, and a default here
    # would be a hardcoded encryption key shared by every deployment -- which is
    # not encryption (CLAUDE.md §16).
    #
    # Generate one with:
    #   python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
    #
    # Rotating it makes every stored credential undecryptable until each
    # workspace re-enters its keys; there is no re-encryption path yet, and that
    # limitation is recorded in the step note rather than hidden here.
    # No explicit alias, unlike the Supabase fields above: those carry one
    # because Supabase names them, so a PROJECTONE_ prefix would contradict
    # every dashboard and tutorial. This variable is ProjectOne's own, so it
    # takes the standard prefix and reads as PROJECTONE_BYOK_ENCRYPTION_KEY.
    byok_encryption_key: SecretStr

    # Per-attempt timeout for an AI provider call. Bounded for the same reason
    # every other timeout here is: one hanging upstream call must not hold a
    # worker open indefinitely. Generous relative to the others because
    # generation genuinely is slow -- a completion is not a health check.
    ai_provider_timeout_seconds: float = 30.0

    @property
    def trusted_proxy_networks(self) -> tuple[IPv4Network | IPv6Network, ...]:
        """Return the parsed trusted-proxy allowlist.

        Parsed on access rather than stored as a field so `Settings` keeps a
        flat, environment-shaped surface. `get_settings()` is cached, so the
        parse happens once per process in practice.

        Raises:
            ValueError: if any entry is malformed. Fatal by design -- silently
                dropping a bad entry narrows the allowlist without a signal,
                which restores the very defect ADR-002 exists to close.
        """
        return parse_trusted_proxies(self.trusted_proxies.split(","))

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
        settings = Settings()  # type: ignore[call-arg]
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

    # Forced at startup rather than left to the first request that reads it.
    # A malformed allowlist is a security misconfiguration, and discovering it
    # on a request would mean the process ran for some time honouring a
    # narrower allowlist than intended -- silently falling back to
    # proxy-address limiting, which is the defect ADR-002 closes.
    #
    # The result is bound and reported below rather than discarded: an empty
    # allowlist behind a proxy is the defect itself, and it is invisible unless
    # something says so at boot (CLAUDE.md §26).
    try:
        trusted = settings.trusted_proxy_networks
    except ValueError as error:
        sys.exit(
            f"ProjectOne API cannot start: {Settings.model_config['env_prefix']}TRUSTED_PROXIES "
            f"is invalid.\n  - {error}\n"
            "See apps/api/.env.example for the expected format."
        )

    # Validated at startup for the same reason as the allowlist above: a
    # malformed encryption key means every BYOK operation fails, and finding
    # that out on a user's first AI call is strictly worse than not starting.
    #
    # Imported here rather than at module scope to keep `app.core.config` free
    # of a dependency on `app.ai` -- configuration is the lower layer, and an
    # import in that direction would invert it (CLAUDE.md §28).
    from app.ai.crypto import CredentialEncryptionError, parse_encryption_key

    try:
        parse_encryption_key(settings.byok_encryption_key.get_secret_value())
    except CredentialEncryptionError as error:
        sys.exit(
            f"ProjectOne API cannot start: {Settings.model_config['env_prefix']}"
            f"BYOK_ENCRYPTION_KEY is invalid.\n  - {error}\n"
            "See apps/api/.env.example for how to generate one."
        )

    if not trusted:
        # Not fatal: running with nothing in front of the API is a legitimate
        # deployment, and limiting correctly falls back to the peer address.
        # But behind a proxy it means every user shares one bucket, which is
        # precisely the regression this configuration exists to fix -- so it is
        # said out loud rather than left for someone to infer from a support
        # ticket.
        print(  # noqa: T201 - before logging is configured; must reach the console
            f"WARNING: {Settings.model_config['env_prefix']}TRUSTED_PROXIES is empty. "
            "Forwarded client addresses will be ignored and public endpoints will be "
            "rate limited by peer address. Correct when running behind a proxy.",
            file=sys.stderr,
        )

    return settings
