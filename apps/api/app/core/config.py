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
from collections.abc import Mapping
from enum import StrEnum
from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network
from typing import Final

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_core import ErrorDetails
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


#: The four R2 variables, mapped to the `Settings` field each one populates.
#:
#: One definition serving three readers: the partial-configuration validator, the
#: startup requirement in `get_settings()`, and the CI guard rail in
#: `tests/test_ci_configuration.py`. Spelling the names out at each of those
#: sites is how a fifth variable gets added to two of them and forgotten in the
#: third -- which is the failure `test_ci_configuration` exists to prevent.
_STORAGE_VARIABLES: Final[Mapping[str, str]] = {
    "PROJECTONE_R2_ACCOUNT_ID": "r2_account_id",
    "PROJECTONE_R2_BUCKET": "r2_bucket",
    "PROJECTONE_R2_ACCESS_KEY_ID": "r2_access_key_id",
    "PROJECTONE_R2_SECRET_ACCESS_KEY": "r2_secret_access_key",
}

#: The storage variables `get_settings()` refuses to start without (STEP-28).
#:
#: **Enforced at startup rather than as required model fields, deliberately.**
#: Making them required on `Settings` would be the more obvious spelling, but it
#: would also make a storage-free `Settings` unconstructable -- and a
#: storage-free `Settings` is exactly what the test suite builds, and what
#: `StorageNotConfiguredError` exists to describe. The requirement belongs to a
#: *deployment*, so it is checked where a deployment is assembled.
#:
#: Exported rather than private because `tests/test_ci_configuration.py` reads
#: it: a startup requirement invisible to that test would break CI on a push
#: instead of in the change that caused it, which is the precise defect that
#: test was written to close after STEP-17.
STARTUP_REQUIRED_STORAGE_VARIABLES: Final[tuple[str, ...]] = tuple(_STORAGE_VARIABLES)


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

    # How long an audit event is kept before being permanently deleted.
    #
    # **90 days, set by the project owner on 2026-08-15** (FA-07). CLAUDE.md §16
    # requires audit logs to be retained on a *stated* schedule and disclosed as
    # a bounded exception to user erasure -- before this, there was no retention
    # mechanism at all, so the exception was unbounded and growing.
    #
    # Configurable rather than hard-coded, because the compliance position will
    # firm up before public release and a window that needs a code change to
    # move is a window nobody moves (CLAUDE.md §28a).
    #
    # **Zero means retain indefinitely**, for a deployment under an obligation
    # to keep everything. It is the safer reading of the ambiguous value: a
    # purge that treats 0 as "keep nothing" would delete the entire trail, so
    # the code refuses to derive a cutoff from it at all rather than relying on
    # arithmetic to land the right way.
    #
    # `ge=0` so a negative window is rejected at startup. A negative value would
    # place the cutoff in the *future*, making every existing row expired -- a
    # configuration typo that silently destroys the audit log is exactly the
    # failure this bound exists to prevent (CLAUDE.md §24).
    audit_retention_days: int = Field(default=90, ge=0)

    # --- Object storage (Cloudflare R2, via the S3-compatible API) -----------
    #
    # ADR-004: R2 is the initial production adapter behind the vendor-neutral
    # StorageProvider boundary. These four variables are what that adapter needs
    # and nothing more; no other part of the codebase reads them.
    #
    # **Required of a deployment since STEP-28**, which introduced the first real
    # caller. Until then an API that refused to start without R2 credentials
    # would have been demanding configuration for a subsystem nothing invoked;
    # now a missing value means uploads fail, which is a broken deployment and
    # belongs at startup rather than in front of the first user to try one.
    #
    # **Still typed as optional here, and that is not an oversight.** The
    # requirement is enforced by `get_settings()` against
    # `STARTUP_REQUIRED_STORAGE_VARIABLES` above, not by making these fields
    # required, so a `Settings` with no storage at all remains constructable —
    # which the test suite depends on, and which is the state
    # `StorageNotConfiguredError` names. A deployment is held to all four; an
    # object built in a test is not.
    #
    # SecretStr on the credentials keeps them out of logs, tracebacks and repr()
    # output (CLAUDE.md §16, §25). The account id and bucket are not secrets and
    # are plain strings, so an operator can read them back to confirm which
    # bucket a deployment is pointed at.
    r2_account_id: str | None = None
    r2_bucket: str | None = None
    r2_access_key_id: SecretStr | None = None
    r2_secret_access_key: SecretStr | None = None

    # --- Asynchronous jobs (ADR-005, STEP-30) --------------------------------
    #
    # Both processes read these. The API needs neither today, and that is
    # deliberate rather than an oversight: one image runs under two commands and
    # validates one configuration surface, so a worker cannot be started with a
    # setting the API has never seen (ADR-005 §3).
    #
    # Neither is required. A queue that refuses to start without a tuning value
    # would be demanding configuration for a decision that has a correct default,
    # and both defaults are the safe end of their trade-off.

    # How long a claimed job's lease runs before it may be taken by another
    # worker.
    #
    # The trade-off is explicit. Too short, and a healthy worker whose job
    # outlives one heartbeat interval loses its lease and the job runs twice.
    # Too long, and a job whose worker was killed sits unclaimable for that long
    # before anyone can recover it.
    #
    # 60 seconds with renewal every 20 (a third of the lease, see
    # `LeaseHeartbeat`) means two consecutive renewals may fail before a lease
    # actually lapses, while a dead worker's job is recoverable inside a minute.
    #
    # `ge=5` so a value that cannot survive a single renewal round trip is
    # rejected at startup rather than producing a queue that duplicates
    # everything it runs.
    job_lease_seconds: int = Field(default=60, ge=5)

    # How long a worker waits before polling an empty queue again.
    #
    # ADR-005 §1 chose polling over `LISTEN`/`NOTIFY` deliberately: latency is
    # bounded by this interval, the interval is configuration rather than code,
    # and ProjectOne has no measurement showing the difference matters
    # ([[CLAUDE|CLAUDE.md]] §17 -- measure before optimizing).
    #
    # A worker that just finished a job polls again immediately, so this bounds
    # how long an *idle* queue takes to notice new work, never how fast a backlog
    # drains.
    #
    # `gt=0` because zero is a busy-wait against the primary database, which is
    # the one way a database-backed queue genuinely does become a load problem.
    job_poll_interval_seconds: float = Field(default=1.0, gt=0)

    @property
    def r2_endpoint_url(self) -> str | None:
        """Return R2's S3-compatible endpoint for the configured account.

        Derived rather than configured. The endpoint is a pure function of the
        account id (`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, per
        Cloudflare's documentation), so accepting it as its own variable would
        create two values that can disagree — and a deployment pointed at
        another account's endpoint is a tenant-isolation failure, not a typo.

        Returns:
            The endpoint URL, or None when no account is configured.
        """
        if self.r2_account_id is None:
            return None
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @model_validator(mode="after")
    def _reject_partial_storage_configuration(self) -> "Settings":
        """Refuse a storage configuration that is present but incomplete.

        **All four, or none.** Four is valid. One, two or three is a mistake,
        and this is where it is caught.

        Zero remains valid *at this level* even though STEP-28 made storage
        required of a deployment, because the two checks answer different
        questions. This one asks whether a `Settings` object is coherent, and a
        storage-free one is — it is what every test that never touches storage
        builds. Whether a *deployment* may omit storage is asked by
        `get_settings()`, against `STARTUP_REQUIRED_STORAGE_VARIABLES`.

        Folding the deployment requirement into this validator would have been
        the shorter change and the wrong one: it would make a storage-free
        `Settings` unconstructable, which breaks roughly fifteen test modules
        and leaves `StorageNotConfiguredError` describing a state that can no
        longer exist.

        Without this check, a partial configuration is silently identical to no
        configuration: `storage_is_configured` reads False, the API starts, and
        the omission surfaces much later as "storage is not configured" on the
        first upload — pointing at the whole subsystem rather than at the one
        variable that was actually missing. An operator who set three of four
        values is told they set none, which is the least useful true statement
        available.

        Fails at startup rather than at first use because this is a deployment
        fault, and a deployment fault found while someone is watching the deploy
        is enormously cheaper than one found by a user (CLAUDE.md §24).

        Returns:
            The validated settings.

        Raises:
            ValueError: naming the **missing variables only**. Never the values:
                two of the four are credentials, and an error message is exactly
                the kind of place a secret leaks into a log (CLAUDE.md §16, §25).
        """
        present = {
            variable: getattr(self, field) is not None
            for variable, field in _STORAGE_VARIABLES.items()
        }

        if any(present.values()) and not all(present.values()):
            missing = sorted(name for name, is_set in present.items() if not is_set)
            raise ValueError(
                "Object storage is partially configured. Set all four R2 "
                "variables or none of them. Missing: " + ", ".join(missing)
            )

        return self

    @property
    def storage_is_configured(self) -> bool:
        """Return whether every value the storage adapter needs is present.

        All four or none — enforced by `_reject_partial_storage_configuration`,
        so by the time this is read the only reachable states are all-four and
        none.

        Still meaningful after STEP-28 made storage required of a deployment:
        `get_settings()` guarantees this reads True for a *running API*, but a
        `Settings` built directly — in a test, or by a tool that never uploads —
        can legitimately be storage-free, and `build_storage_provider()` uses
        this to say so.
        """
        return all(getattr(self, field) is not None for field in _STORAGE_VARIABLES.values())

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


def _error_location(item: ErrorDetails) -> str:
    """Return the environment variable name a validation error refers to.

    Field errors carry the field name in `loc`, which becomes the variable name
    once the `PROJECTONE_` prefix is applied. **Model-level errors carry an
    empty `loc`** -- a `model_validator` checks a relationship between fields
    rather than one field, so there is no single name to report.

    That case is why this helper exists: indexing `loc[0]` unconditionally
    raises `IndexError` while formatting the very message meant to explain a
    misconfiguration, turning a clear startup failure into an unrelated crash
    inside the error handler. The cross-field storage check is the first
    model-level validator in this file, so the latent bug became reachable with
    it.
    """
    location = item["loc"]
    if not location:
        # The validator's own message already names the variables involved.
        return "configuration"
    return f"{Settings.model_config['env_prefix']}{str(location[0]).upper()}"


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
        # `include_input=False` is load-bearing, not tidiness. Pydantic's default
        # error rendering echoes the *entire* input mapping back in an
        # `input_value=...` clause -- and for a settings model that mapping holds
        # every credential the process was started with, in plaintext, on its way
        # to a container log. `SecretStr` does not help here: it masks a value
        # once it is a field, and this echo happens on the raw input before that.
        #
        # Each error is reformatted by hand below rather than passed through, so
        # the only things printed are the variable name and the reason
        # (CLAUDE.md §16, §25).
        details = "\n".join(
            f"  - {_error_location(item)}: {item['msg']}"
            for item in error.errors(include_input=False)
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

    # Object storage became a deployment requirement in STEP-28, the step that
    # introduced the first caller. Before it, refusing to start would have
    # demanded credentials for a subsystem nothing invoked; after it, a missing
    # value means every upload fails.
    #
    # Checked here rather than by making the fields required for the reason
    # recorded on `STARTUP_REQUIRED_STORAGE_VARIABLES`: the requirement belongs
    # to a deployment, and this function is where a deployment is assembled.
    #
    # Reported as a list of *missing* names, never values -- two of the four are
    # credentials, and a startup message is exactly where one leaks into a
    # container log (CLAUDE.md §16, §25).
    missing_storage = [
        variable
        for variable in STARTUP_REQUIRED_STORAGE_VARIABLES
        if getattr(settings, _STORAGE_VARIABLES[variable]) is None
    ]
    if missing_storage:
        sys.exit(
            "ProjectOne API cannot start: object storage is not configured.\n"
            + "\n".join(f"  - {variable}: missing" for variable in missing_storage)
            + "\nUploads and downloads cannot work without it. "
            "See apps/api/.env.example."
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
