"""Recording authentication events, without answering questions nobody asked.

**FA-06.** `AuditService` records who changed what inside a workspace. This
records who tried to authenticate, and whether it worked — the events that
precede having a workspace at all, and the ones a breach investigation starts
from.

## The rule that shapes this module

**A failed authentication must reveal nothing about whether the account
exists.** That constraint reaches further than it first appears:

- `record_failure` takes no user, no workspace and no address. Not "takes them
  and discards them" — the parameters do not exist, so a caller cannot supply
  one by mistake and no future edit can start passing one through.
- The submitted address is never stored in any form, hashed included. A hash is
  an oracle to anyone who can compute it over a guess.
- The *reason* is a short allowlisted token (`invalid_credentials`,
  `provider_unavailable`), never the provider's message. Supabase's own wording
  distinguishes cases that the public response deliberately does not.

## Failures are swallowed, for the same reason `AuditService` swallows them

`record` never raises. A security-event write failing must not turn a successful
sign-in into a 500 the caller retries — an audit-infrastructure problem would
become an availability problem, which is strictly worse than a missing line.

The trade-off is sharper here than for `AuditService`, and worth naming: the
events most likely to coincide with a security-event write failing are the ones
during an incident. The mitigation is that failures log at `exception` level
with the correlation id attached, so they are alertable (CLAUDE.md §26) rather
than silent. An event whose record must be atomic with the action needs a
different mechanism, and none of these do.
"""

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger, log_context
from app.repositories.security_events import SecurityEvent, SecurityEventRepository

logger = get_logger(__name__)


class SecurityEventType(StrEnum):
    """The authentication events this platform records.

    Values match `ck_security_event_log_type_valid` exactly. `StrEnum` so a
    value compares equal to the string the database stores, keeping the boundary
    between the two layers free of conversions that could silently disagree —
    the same reasoning as `AuditAction`.

    The set covers `app/routers/auth.py` completely. Adding a value here means
    widening that CHECK constraint in a migration; the constraint is what makes
    an unrecognised event a loud failure rather than a row nobody can interpret.
    """

    SIGN_UP = "auth.sign_up"
    SIGN_IN = "auth.sign_in"
    SIGN_OUT = "auth.sign_out"
    TOKEN_REFRESH = "auth.token_refresh"


class SecurityEventOutcome(StrEnum):
    """Whether the event succeeded.

    Both exist because recording only successes proves nothing about an attack:
    a credential-stuffing run is invisible in a log of what worked.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"


#: Failure reasons that may be stored.
#:
#: An allowlist rather than free text, and that is the security property. The
#: identity provider's own message distinguishes "user not found" from "wrong
#: password" — precisely the distinction the public response refuses to make, so
#: storing it would rebuild the oracle inside the table that exists to be safe.
class SecurityEventReason(StrEnum):
    """Why an authentication attempt failed, in terms that reveal nothing."""

    INVALID_CREDENTIALS = "invalid_credentials"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_TOKEN = "invalid_token"  # noqa: S105 - an outcome label, not a credential


class SecurityEventService:
    """Records authentication events."""

    def __init__(self, events: SecurityEventRepository) -> None:
        """Store the repository writes go through."""
        self._events = events

    def record(
        self,
        event_type: SecurityEventType,
        outcome: SecurityEventOutcome,
        *,
        request_id: str,
        user_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
        **metadata: Any,  # noqa: ANN401 - event-specific detail, validated by SecurityEvent
    ) -> None:
        """Record one event, never raising.

        Args:
            event_type: Which authentication event occurred.
            outcome: Whether it succeeded.
            request_id: The request's correlation id, tying this to the request
                log without either side carrying the other's data.
            user_id: The verified identity, where one was established. Must be
                None for a failed outcome — `SecurityEvent` refuses otherwise.
            workspace_id: The workspace, on the rare event that has one.
            **metadata: Bounded, allowlisted context. Forbidden keys and
                secret-shaped values are refused before anything is stored.
        """
        try:
            self._events.record(
                SecurityEvent(
                    event_type=event_type.value,
                    outcome=outcome.value,
                    request_id=request_id,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    metadata=dict(metadata),
                )
            )
        except Exception:
            # Loud, but not fatal — see the module docstring. `log_context`
            # redacts credential-shaped values, and nothing here should carry
            # one: metadata is validated before it reaches this point.
            logger.exception(
                log_context(
                    event="security_event_write_failed",
                    security_event_type=event_type.value,
                    outcome=outcome.value,
                )
            )

    def record_failure(
        self,
        event_type: SecurityEventType,
        *,
        request_id: str,
        reason: SecurityEventReason | str,
    ) -> None:
        """Record a failed authentication attempt, anonymously.

        **Takes no identity of any kind, deliberately.** There is no `user_id`
        parameter, no `workspace_id` and no address — so a caller cannot supply
        one by mistake, and a future edit cannot start threading one through
        without changing this signature and confronting why it is shaped this
        way.

        Args:
            event_type: Which authentication event failed.
            request_id: The request's correlation id.
            reason: A short allowlisted token, never the provider's message.
        """
        self.record(
            event_type,
            SecurityEventOutcome.FAILED,
            request_id=request_id,
            reason=str(reason),
        )

    @staticmethod
    def retention_cutoff(settings: Settings) -> datetime | None:
        """Return the timestamp before which security events have expired.

        The same 90-day window as the audit log, from the same setting: these
        are two halves of one retention commitment, and letting them drift apart
        would make the disclosure users are shown true of only one table.

        Returns None when retention is disabled. `audit_retention_days = 0`
        means *retain indefinitely*, and the dangerous misreading is "keep
        nothing" — a cutoff of `now` would expire the entire log. Refusing to
        produce a cutoff makes that unreachable rather than merely unlikely.
        """
        if settings.audit_retention_days <= 0:
            return None

        return datetime.now(UTC) - timedelta(days=settings.audit_retention_days)

    def purge_expired(self, settings: Settings) -> int:
        """Delete security events past the retention window.

        Unlike `record`, this does **not** swallow failures. A silent write
        failure loses one line; a silent purge failure means retention is not
        happening, which is a compliance position quietly becoming false — the
        caller needs to know so it can alert (CLAUDE.md §26).

        Args:
            settings: The configuration holding the retention window.

        Returns:
            How many rows were deleted. Zero when retention is disabled, and the
            repository is not asked to delete at all in that case.
        """
        cutoff = self.retention_cutoff(settings)

        if cutoff is None:
            return 0

        deleted = self._events.purge_older_than(cutoff)

        logger.info(
            log_context(
                event="security_event_retention_purge",
                retention_days=settings.audit_retention_days,
                deleted=deleted,
            )
        )

        return deleted
