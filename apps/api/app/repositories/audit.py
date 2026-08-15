"""Append-only writes and tenant-scoped reads of `public.audit_log`.

Two connections, for the same reason they appear in `UserRepository`:

- **Writing** runs over the **privileged** connection. The table has no INSERT
  policy and `authenticated` holds no INSERT grant, both deliberately
  (migration `a3c07d5e91f4`): a client able to write its own audit rows could
  forge them, and a forged trail is worse than no trail because it is trusted.
- **Reading** runs over the **request** connection, subject to
  `audit_log_select_same_workspace`, so a caller only ever sees the actions of
  workspaces they belong to.

This is the same audited-service-path shape CLAUDE.md §16 requires for the
operations RLS deliberately forbids -- not a convenience bypass.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg

from app.core.config import Settings


@dataclass(frozen=True)
class AuditEntry:
    """One recorded action."""

    action: str
    workspace_id: uuid.UUID
    actor_id: uuid.UUID
    actor_email: str | None = None
    target_id: uuid.UUID | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditRecord:
    """An audit row as read back."""

    id: uuid.UUID
    created_at: str
    action: str
    workspace_id: uuid.UUID
    actor_id: uuid.UUID
    actor_email: str | None
    target_id: uuid.UUID | None
    detail: dict[str, Any]


class AuditRepository:
    """Persists and reads audit records."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding the privileged connection string."""
        self._settings = settings

    def record(self, entry: AuditEntry) -> None:
        """Append one audit row.

        Opens its own privileged connection rather than joining the caller's
        transaction, and that separation is deliberate: an audit record must
        survive the rollback of the action it describes. A failed or
        rolled-back mutation that was nonetheless *attempted* is precisely the
        kind of event an auditor wants to see, and folding the write into the
        caller's transaction would erase exactly those.

        The trade-off is the honest one: a recorded action is not strictly
        guaranteed to have succeeded, so callers record *after* the operation
        commits. See `AuditService` for where that ordering is enforced.
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
                INSERT INTO public.audit_log
                    (workspace_id, actor_id, actor_email, action, target_id, detail)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    entry.workspace_id,
                    entry.actor_id,
                    entry.actor_email,
                    entry.action,
                    entry.target_id,
                    json.dumps(entry.detail),
                ),
            )

    @staticmethod
    def purge_statement() -> str:
        """Return the retention purge statement.

        Exposed as a string so it is directly assertable. The failure this
        guards is a `DELETE` whose predicate is wrong or missing, and that is
        not a defect any downstream test catches — once an unfiltered delete has
        run, the evidence it was wrong is the thing it destroyed.

        `TRUNCATE` is deliberately not used despite being faster: it bypasses
        row-level filtering entirely, so a bug in the caller could not be
        limited by the statement itself.
        """
        return """
            DELETE FROM public.audit_log
            WHERE created_at < %s
        """

    def purge_older_than(self, cutoff: datetime) -> int:
        """Delete audit rows created before `cutoff`, returning how many.

        Runs over the **privileged** connection, like `record`: the table has no
        DELETE policy and `authenticated` holds no DELETE grant, both
        deliberately (migration `a3c07d5e91f4`), because a client able to delete
        its own audit rows could erase the trail of what it did.

        This is the audited-service-path shape CLAUDE.md §16 requires for the
        operations RLS forbids — a scheduled retention purge is exactly such an
        operation, and it is not a licence for anything else to delete here.

        Args:
            cutoff: Rows strictly older than this are removed.

        Returns:
            The number of rows deleted, so the purge can be monitored rather
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

    @staticmethod
    def read_for_workspace(
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        limit: int,
    ) -> list[AuditRecord]:
        """Return a workspace's audit trail, newest first.

        Takes an already-authenticated connection rather than opening one, so
        this cannot accidentally be invoked over the privileged connection --
        the session's identity is the connection's, and this function has no way
        to widen it. The same defence `UserRepository.read_visible_profiles`
        uses.

        The `workspace_id` filter is redundant with the RLS policy for a caller
        who belongs to exactly one workspace, and load-bearing for one who
        belongs to several: the policy decides which rows are *visible*, the
        WHERE clause decides which of those the caller asked for.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, created_at, action, workspace_id,
                       actor_id, actor_email, target_id, detail
                FROM public.audit_log
                WHERE workspace_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )

            return [
                AuditRecord(
                    id=row[0],
                    created_at=row[1].isoformat(),
                    action=row[2],
                    workspace_id=row[3],
                    actor_id=row[4],
                    actor_email=row[5],
                    target_id=row[6],
                    detail=row[7],
                )
                for row in cursor
            ]
