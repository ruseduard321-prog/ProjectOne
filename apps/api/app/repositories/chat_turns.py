"""Claims a chat turn, so a provider is invoked at most once per question.

This is the only part of chat that does **not** run on the request's tenant
connection, and the reason is the defect [[STEP-23 AI Chat End to End]] shipped
and manual testing caught.

## Why a privileged connection, when everything else is RLS-scoped

`RequestSessionFactory.authenticated_as` wraps the whole request in one
transaction, so anything it wrote is rolled back when the request raises. That
is correct for ordinary work -- a failed request should leave nothing behind --
but a claim is the opposite: its entire purpose is to survive the failure of the
call it guards. A claim rolled back is not a claim.

It cannot be fixed by committing inside that transaction either. `SET LOCAL ROLE`
and the `set_config(..., true)` claim are **discarded by a commit** (verified
against the live database), so a mid-request commit would continue as the
privileged owner with RLS switched off. That is a tenant-isolation breach, not a
workaround.

So the claim runs here, on its own connection with its own commit lifecycle --
the same shape `AISpendRepository` already uses, and for the same underlying
reason: a unit of work whose durability must not depend on the request that
triggered it.

## What replaces RLS on this path

**The caller must have already proven tenancy.** Every method takes
`workspace_id` and filters on it, and the routes reach this only after
`requires(VIEW_WORKSPACE)` and a tenant-connection read of the conversation. The
workspace id is the verified one from the request context, never client input.

That is a weaker guarantee than RLS and it is stated plainly rather than glossed:
this module is trusted to scope its own queries. `test_chat_turn_claims.py`
asserts the cross-tenant refusal directly against a real database, because a
convention that is only documented is one that eventually gets broken.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg

from app.core.config import Settings

#: The states a user message moves through while being answered.
#:
#: Mirrors `ck_messages_turn_status_valid` exactly. A user message is `pending`
#: from the moment it is stored; `in_progress` while a provider call is in
#: flight; `completed` once its reply is persisted.
PENDING = "pending"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"


@dataclass(frozen=True)
class TurnClaim:
    """A successful claim on one turn.

    Carries the token because settling and releasing both require it: a holder
    that has been superseded must not be able to finish a turn it no longer
    owns.
    """

    user_message_id: uuid.UUID
    claim_token: uuid.UUID


class ChatTurnRepository:
    """Claims, settles and releases turns on a privileged connection."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding the privileged connection string."""
        self._settings = settings

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection]:
        """Yield a privileged connection, committing on clean exit.

        Each method here is one logical unit of work that must be durable
        independently of the request -- see the module docstring. The connection
        is closed on exit rather than pooled: a claim is two short statements,
        and holding one open across the provider call is the bottleneck
        `AISpendRepository` documents.
        """
        connection = psycopg.connect(
            self._settings.database_url.get_secret_value(),
            connect_timeout=self._settings.database_health_timeout_seconds,
        )

        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def claim(self, workspace_id: uuid.UUID, user_message_id: uuid.UUID) -> TurnClaim | None:
        """Take exclusive right to answer one turn, or return None.

        **This is the concurrency control**, and it is a conditional UPDATE
        rather than a lock:

            WHERE id = ... AND turn_status = 'pending'

        PostgreSQL serialises the update, so exactly one of any number of
        concurrent callers gets a row back. Verified with four concurrent
        callers against a real database: one claimed, three did not.

        A unique index on the eventual reply was tried first and **rejected**.
        It prevents a duplicate reply *row*, but only after every caller has
        already invoked and been billed by the provider -- it deduplicates
        storage, never spend.

        The caller commits this before making its network call, which is what
        lets the provider request run with no transaction open and no row
        locked.

        Returns:
            The claim when this caller won, None when the turn was already
            `in_progress` or `completed` -- or does not exist in this workspace,
            which is deliberately the same answer for the reason
            `ConversationNotFoundError` gives.
        """
        token = uuid.uuid4()

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.messages
                SET turn_status = %s,
                    claim_token = %s,
                    claimed_at = now()
                WHERE id = %s
                  AND workspace_id = %s
                  AND role = 'user'
                  AND turn_status = %s
                  AND deleted_at IS NULL
                RETURNING id
                """,
                (IN_PROGRESS, token, user_message_id, workspace_id, PENDING),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return TurnClaim(user_message_id=user_message_id, claim_token=token)

    def release(self, workspace_id: uuid.UUID, claim: TurnClaim) -> bool:
        """Return a claimed turn to `pending` after an ordinary failure.

        Scoped by `claim_token`, so a superseded holder cannot release a turn
        someone else now owns. Releasing is what makes a provider outage
        *retryable*: the question stays stored, the turn becomes claimable
        again, and the user's retry is a new attempt at the same turn rather
        than a second question.

        Deliberately **not** called after a crash -- there is nothing running to
        call it. Such a turn stays `in_progress`, visibly stuck, because
        returning it to `pending` on a timer would re-invoke a provider that may
        already have accepted and charged for the request. See
        [[STEP-23 AI Chat End to End]] on the crash window.

        Returns:
            True when this claim still held the turn.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.messages
                SET turn_status = %s,
                    claim_token = NULL,
                    claimed_at = NULL
                WHERE id = %s
                  AND workspace_id = %s
                  AND claim_token = %s
                RETURNING id
                """,
                (PENDING, claim.user_message_id, workspace_id, claim.claim_token),
            )

            return cursor.fetchone() is not None

    def complete(self, workspace_id: uuid.UUID, claim: TurnClaim) -> bool:
        """Mark a claimed turn answered.

        Scoped by `claim_token` for the same reason `release` is. Called after
        the reply is persisted, so a turn is never `completed` without one --
        the ordering matters, and the reverse would leave a turn that can never
        be retried and has no answer.

        Returns:
            True when this claim still held the turn.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.messages
                SET turn_status = %s,
                    claim_token = NULL
                WHERE id = %s
                  AND workspace_id = %s
                  AND claim_token = %s
                RETURNING id
                """,
                (COMPLETED, claim.user_message_id, workspace_id, claim.claim_token),
            )

            return cursor.fetchone() is not None

    def status_of(self, workspace_id: uuid.UUID, user_message_id: uuid.UUID) -> str | None:
        """Return a turn's current state, or None when it is not visible here.

        Used to answer a second caller honestly: a turn already `completed` has
        its reply returned, and one `in_progress` is reported as such rather
        than being answered twice.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT turn_status
                FROM public.messages
                WHERE id = %s
                  AND workspace_id = %s
                  AND role = 'user'
                  AND deleted_at IS NULL
                """,
                (user_message_id, workspace_id),
            )
            row = cursor.fetchone()

        return None if row is None else str(row[0])
