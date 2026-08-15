"""Append-only writes to `public.security_event_log`.

**FA-06.** Authentication events — sign-up, sign-in, sign-out, token refresh —
recorded so a security question has an answer, without the recording itself
becoming an attack surface.

## One connection, and it is the privileged one

Unlike `AuditRepository` there is no read path here at all. The table has no
policies and no grants (migration `b2e94c17a5d3`), so `authenticated` cannot
select, insert, update, delete or truncate it. That is the owner's requirement —
no tenant-facing read path, no public endpoint — and it is why this module
exposes writing and retention and nothing else.

## Why validation lives in the record rather than at the write

`SecurityEvent` refuses forbidden metadata *at construction*, before anything is
stored. A filter applied inside `record()` would protect the write it runs in;
refusing in the constructor protects every future caller too, including one that
builds an event and hands it somewhere this module never sees. The failure is a
`ValueError` at the call site rather than a redacted row nobody notices.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg

from app.core.config import Settings

#: Event types the database's CHECK constraint accepts.
#:
#: Duplicated from migration `b2e94c17a5d3` deliberately, so an unrecognised
#: type fails at the call site with a readable message instead of as an
#: `IntegrityError` from a constraint the caller has never heard of. The
#: constraint remains the authority; this is the courtesy.
ALLOWED_EVENT_TYPES = frozenset(
    {
        "auth.sign_up",
        "auth.sign_in",
        "auth.sign_out",
        "auth.token_refresh",
    }
)

ALLOWED_OUTCOMES = frozenset({"succeeded", "failed"})

#: Metadata keys that must never appear, matched case-insensitively as
#: substrings.
#:
#: Substring matching rather than exact, because the shape this guards against
#: is `{"user_email": ...}` and `{"raw_authorization_header": ...}` — a
#: well-meaning debugging addition, not a deliberate leak. An exact-match list
#: would need every variation enumerated, and the one nobody thought of is the
#: one that ships.
FORBIDDEN_METADATA_KEYS = (
    "password",
    "token",
    "secret",
    "key",
    "credential",
    "authorization",
    "cookie",
    "email",
    "identifier",
    "username",
    "dsn",
    "database_url",
    "ip",
)

#: Value shapes that must never be stored, whatever key they arrive under.
#:
#: Key-name filtering alone is defeated by `{"note": "<the token>"}`. These
#: catch the value itself: a connection string carrying credentials, a bearer
#: header, a dotted token triple, a provider API key, an address, or a
#: token-named cookie pair.
#:
#: **The honest limit, stated rather than papered over.** A bare password has no
#: shape. `hunter2` and `correct-horse-battery` are indistinguishable from a
#: failure reason by inspection, and no pattern will ever catch them. That gap
#: is closed by the key allowlist above and by `record_failure` having no
#: parameter that could carry a credential — not by this regex. Treating a
#: pattern as the primary defence is precisely the false confidence FA-05 was
#: about; this is the backstop, and the shape of the API is the control.
_SECRET_SHAPED_VALUE = re.compile(
    r"""(?ix)
    (
        [a-z][a-z0-9+.-]*://[^:@/\s]+:[^:@/\s]+@             # scheme://user:pass@host
      | \bbearer\s+\S+                                       # an Authorization header
      | [a-z0-9_-]{3,}\.[a-z0-9_-]{3,}\.[a-z0-9_-]{3,}       # a dotted token triple
      | \bsk-[a-z0-9_-]{8,}                                  # a provider API key
      | [a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}                # an address
      | [a-z0-9_-]*token[a-z0-9_-]*\s*=                      # a token-named cookie
    )
    """
)

#: The serialized-metadata ceiling, matching the database's own CHECK.
#:
#: Enforced here as well so the failure names the problem at the call site
#: rather than arriving as a constraint violation.
MAX_METADATA_BYTES = 2048


@dataclass(frozen=True)
class SecurityEvent:
    """One authentication event, validated the moment it is built.

    Frozen, so an event cannot be mutated between validation and the write —
    which would make the validation decorative.

    Raises:
        ValueError: The event type or outcome is not allowed, the metadata
            carries a forbidden key or a secret-shaped value, the metadata is
            too large, or a failed event names a user or workspace.
    """

    event_type: str
    outcome: str
    request_id: str
    user_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject anything that must never reach the table."""
        if self.event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"'{self.event_type}' is not an allowed event type")

        if self.outcome not in ALLOWED_OUTCOMES:
            raise ValueError(f"'{self.outcome}' is not an allowed outcome")

        # **The oracle rule.** A row saying "sign-in failed for user X" answers
        # "does X exist?" from its own contents, so the association is made
        # impossible rather than merely discouraged. The database's
        # `ck_security_event_log_failure_is_anonymous` enforces the same thing;
        # this is the half that fails at the call site, where it is readable.
        if self.outcome == "failed" and (self.user_id is not None or self.workspace_id is not None):
            raise ValueError(
                "a failed event must not name a user or workspace — doing so "
                "turns the log into an account-existence oracle"
            )

        for key, value in self.metadata.items():
            lowered = key.lower()

            for forbidden in FORBIDDEN_METADATA_KEYS:
                if forbidden in lowered:
                    raise ValueError(f"metadata key '{key}' is not permitted in a security event")

            if isinstance(value, str) and _SECRET_SHAPED_VALUE.search(value):
                # Deliberately does not echo the value. Naming it in the
                # exception would move the secret from a row into a traceback,
                # which is the same leak by a different route (FA-05).
                raise ValueError(
                    f"the value under metadata key '{key}' is secret-shaped and "
                    "is not permitted in a security event"
                )

        if len(json.dumps(self.metadata).encode()) > MAX_METADATA_BYTES:
            raise ValueError(
                f"security event metadata is too large (limit {MAX_METADATA_BYTES} bytes)"
            )


class SecurityEventRepository:
    """Appends security events, and enforces their retention."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding the privileged connection string."""
        self._settings = settings

    def record(self, event: SecurityEvent) -> None:
        """Append one security event.

        Opens its own privileged connection rather than joining a caller's
        transaction, for the reason `AuditRepository.record` does: a security
        event must survive the rollback of whatever it describes. A failed
        sign-in has no successful transaction to attach to at all, so this is
        not merely preferable here — it is the only shape that works.
        """
        with (
            psycopg.connect(
                self._settings.database_url.get_secret_value(),
                connect_timeout=self._settings.database_health_timeout_seconds,
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO public.security_event_log
                    (event_type, outcome, request_id, user_id, workspace_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    event.event_type,
                    event.outcome,
                    event.request_id,
                    event.user_id,
                    event.workspace_id,
                    json.dumps(event.metadata),
                ),
            )

    @staticmethod
    def purge_statement() -> str:
        """Return the retention purge statement.

        Exposed as a string so it is directly assertable, for the reason
        `AuditRepository.purge_statement` is: the failure this guards is a
        `DELETE` whose predicate is wrong or missing, and once an unfiltered
        delete has run, the evidence it was wrong is the thing it destroyed.

        `TRUNCATE` is deliberately not used despite being faster — it bypasses
        row-level filtering entirely, so a bug in the caller could not be
        limited by the statement itself.
        """
        return """
            DELETE FROM public.security_event_log
            WHERE created_at < %s
        """

    def purge_older_than(self, cutoff: datetime) -> int:
        """Delete security events created before `cutoff`, returning how many.

        Runs over the privileged connection: the table grants nothing to
        `authenticated` and carries no policies, so this is the approved
        maintenance path CLAUDE.md §16 requires for an operation RLS forbids —
        not a licence for anything else to delete here.

        Args:
            cutoff: Rows strictly older than this are removed.

        Returns:
            The number of rows deleted, so retention can be monitored rather
            than trusted (CLAUDE.md §26).
        """
        with (
            psycopg.connect(
                self._settings.database_url.get_secret_value(),
                connect_timeout=self._settings.database_health_timeout_seconds,
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(self.purge_statement(), (cutoff,))

            return cursor.rowcount
