"""Reads and writes conversations and their messages, over the tenant connection.

Every query here runs as `authenticated` with the caller's `sub` set, so RLS is
what decides which rows exist -- this module never adds a workspace check of its
own beyond the explicit `workspace_id` predicate, which is a query optimisation
and an intent statement rather than the security boundary.

The one query worth reading closely is `history_for_context`. It is the hottest
query this step adds (it runs on every turn) and the one with a cost consequence
rather than only a latency one -- see its docstring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import psycopg

_CONVERSATION_COLUMNS = (
    "id, workspace_id, title, project_id, created_by, created_at, updated_at, version"
)

_MESSAGE_COLUMNS = (
    "id, workspace_id, conversation_id, role, content, provider, model, token_count, "
    "created_at, turn_status, reply_to"
)


@dataclass(frozen=True)
class Conversation:
    """One conversation, as stored.

    Frozen for the reason `Project` is: a repository result is a snapshot of what
    was read, and a mutable row invites a caller to edit it and expect the
    database to notice.
    """

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    project_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True)
class ChatMessage:
    """One message in a conversation.

    Named `ChatMessage` rather than `Message` deliberately: `app.ai.provider`
    already exports a `Message`, and two types with one name in the same import
    graph is how a caller ends up converting one into the other by accident. This
    is the *stored* row; that one is the *wire* format for a provider call.
    """

    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    provider: str | None
    model: str | None
    token_count: int
    created_at: datetime

    #: Where this question is in being answered, or None on a reply.
    #:
    #: `pending` until a completion claims it, `in_progress` while a provider
    #: call is in flight, `completed` once the reply is stored. A turn stuck in
    #: `in_progress` is one whose process died mid-call -- STEP-23 surfaces that
    #: rather than recovering from it, because the provider may already have
    #: charged for the request.
    turn_status: str | None = None

    #: The question an assistant reply answers, or None on a question.
    reply_to: uuid.UUID | None = None


def _conversation_from_row(row: tuple[object, ...]) -> Conversation:
    """Build a `Conversation` from a row selected with `_CONVERSATION_COLUMNS`."""
    return Conversation(
        id=row[0],  # type: ignore[arg-type]
        workspace_id=row[1],  # type: ignore[arg-type]
        title=row[2],  # type: ignore[arg-type]
        project_id=row[3],  # type: ignore[arg-type]
        created_by=row[4],  # type: ignore[arg-type]
        created_at=row[5],  # type: ignore[arg-type]
        updated_at=row[6],  # type: ignore[arg-type]
        version=row[7],  # type: ignore[arg-type]
    )


def _message_from_row(row: tuple[object, ...]) -> ChatMessage:
    """Build a `ChatMessage` from a row selected with `_MESSAGE_COLUMNS`."""
    return ChatMessage(
        id=row[0],  # type: ignore[arg-type]
        workspace_id=row[1],  # type: ignore[arg-type]
        conversation_id=row[2],  # type: ignore[arg-type]
        role=row[3],  # type: ignore[arg-type]
        content=row[4],  # type: ignore[arg-type]
        provider=row[5],  # type: ignore[arg-type]
        model=row[6],  # type: ignore[arg-type]
        token_count=row[7],  # type: ignore[arg-type]
        created_at=row[8],  # type: ignore[arg-type]
        turn_status=row[9],  # type: ignore[arg-type]
        reply_to=row[10],  # type: ignore[arg-type]
    )


class ConversationRepository:
    """Reaches `conversations` and `messages` over an RLS-subject connection."""

    def __init__(self, connection: psycopg.Connection) -> None:
        """Store the tenant-scoped connection every query runs on."""
        self._connection = connection

    # ------------------------------------------------------ conversations --

    def create(
        self,
        workspace_id: uuid.UUID,
        title: str,
        project_id: uuid.UUID | None,
        created_by: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> Conversation:
        """Insert a conversation and return it as stored.

        Args:
            workspace_id: The tenant, from the verified request context.
            title: Derived from the first message by the service.
            project_id: The project this conversation is about, when it is
                about one.
            created_by: Who started it.
            conversation_id: The id to create it with. None lets the database
                generate one. A caller-supplied id is what makes a first turn
                retryable -- see `MessageSendRequest.conversation_id`. An id that
                already exists raises `UniqueViolation` rather than overwriting
                anything, including one held by another tenant, which RLS hides
                but the primary key still sees.

        Returns:
            The created conversation, read back so trigger-maintained columns are
            the real values rather than this layer's guess at them.
        """
        with self._connection.cursor() as cursor:
            # `DEFAULT` rather than a second SQL string: one statement with one
            # column list, so the two paths cannot drift apart.
            cursor.execute(
                f"""
                INSERT INTO public.conversations
                    (id, workspace_id, title, project_id, created_by)
                VALUES (COALESCE(%s, gen_random_uuid()), %s, %s, %s, %s)
                RETURNING {_CONVERSATION_COLUMNS}
                """,  # noqa: S608 - module constant, not input
                (conversation_id, workspace_id, title, project_id, created_by),
            )
            row = cursor.fetchone()

        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Conversation insert returned no row")

        return _conversation_from_row(row)

    def get(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
        """Return one live conversation, or None.

        Returns None both when none exists and when RLS hid it -- indistinguishable
        by design, exactly as `ProjectRepository.get` is.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_CONVERSATION_COLUMNS}
                FROM public.conversations
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """,  # noqa: S608 - module constant, not input
                (conversation_id, workspace_id),
            )
            row = cursor.fetchone()

        return None if row is None else _conversation_from_row(row)

    def list_for_workspace(self, workspace_id: uuid.UUID) -> tuple[Conversation, ...]:
        """Return every live conversation in a workspace, most recently active first.

        Ordered by `updated_at DESC`, not `created_at`: a conversation list is
        useful in the order the user last spoke in them, and the `touch_row`
        trigger keeps `updated_at` honest whenever a turn is appended. `id` breaks
        ties so the order is stable rather than one PostgreSQL may vary.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_CONVERSATION_COLUMNS}
                FROM public.conversations
                WHERE workspace_id = %s AND deleted_at IS NULL
                ORDER BY updated_at DESC, id DESC
                """,  # noqa: S608 - module constant, not input
                (workspace_id,),
            )
            rows = cursor.fetchall()

        return tuple(_conversation_from_row(row) for row in rows)

    def touch(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        """Mark a conversation as recently active.

        A no-op UPDATE would not fire `touch_row`, whose trigger condition is
        `OLD.* IS DISTINCT FROM NEW.*` -- so this writes `updated_at` explicitly
        rather than relying on a trigger that will correctly decline to fire.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.conversations
                SET updated_at = now()
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """,
                (conversation_id, workspace_id),
            )

    def soft_delete(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
        """Soft-delete one conversation.

        The messages are left addressable by their conversation rather than being
        stamped individually: every read path filters through a live conversation,
        so a deleted conversation's messages are already unreachable. Erasure --
        which must genuinely clear the rows -- reaches `messages` directly through
        its own registered store.

        Returns:
            True when a live row was affected, False when there was none to
            delete or RLS hid it.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.conversations
                SET deleted_at = now()
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """,
                (conversation_id, workspace_id),
            )
            return cursor.rowcount > 0

    # ----------------------------------------------------------- messages --

    def add_message(
        self,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        token_count: int = 0,
        turn_status: str | None = None,
        reply_to: uuid.UUID | None = None,
    ) -> ChatMessage:
        """Append one message to a conversation.

        Args:
            workspace_id: The tenant, from the verified request context.
            conversation_id: Which conversation to append to.
            role: `user` or `assistant`, the vocabulary the CHECK permits.
            content: What was said.
            provider: Which provider produced an assistant message.
            model: Which model produced it.
            token_count: What it consumed.
            turn_status: `pending` on a user message awaiting an answer. Null on
                an assistant message, which is not a turn to be claimed --
                `ck_messages_turn_state_matches_role` enforces the pairing.
            reply_to: The user message an assistant reply answers. Refused by
                `app_messages_reply_eligible` unless it names a `user` message
                in the same conversation, and by `uq_messages_reply_to` if that
                turn already has a reply.

        Returns:
            The stored message. A cross-tenant `conversation_id` raises
            `ForeignKeyViolation` from the composite key rather than inserting --
            see the migration's module docstring.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO public.messages
                    (workspace_id, conversation_id, role, content,
                     provider, model, token_count, turn_status, reply_to)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {_MESSAGE_COLUMNS}
                """,  # noqa: S608 - module constant, not input
                (
                    workspace_id,
                    conversation_id,
                    role,
                    content,
                    provider,
                    model,
                    token_count,
                    turn_status,
                    reply_to,
                ),
            )
            row = cursor.fetchone()

        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Message insert returned no row")

        return _message_from_row(row)

    def list_messages(
        self, workspace_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> tuple[ChatMessage, ...]:
        """Return a conversation's live messages, oldest first.

        Oldest-first because a transcript reads in the order it was said. Ordered
        by `created_at, id` so two messages written inside one transaction --
        which is exactly what a turn is, the user's message and the reply -- have
        a stable order rather than one PostgreSQL may vary.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_MESSAGE_COLUMNS}
                FROM public.messages
                WHERE conversation_id = %s AND workspace_id = %s AND deleted_at IS NULL
                ORDER BY created_at ASC, id ASC
                """,  # noqa: S608 - module constant, not input
                (conversation_id, workspace_id),
            )
            rows = cursor.fetchall()

        return tuple(_message_from_row(row) for row in rows)

    def history_for_context(
        self, workspace_id: uuid.UUID, conversation_id: uuid.UUID, limit: int
    ) -> tuple[ChatMessage, ...]:
        """Return the most recent `limit` messages, oldest first.

        **This is a cost control, not a convenience.** Every message returned here
        is replayed into the next provider call, so an unbounded read is an
        unbounded prompt and therefore unbounded spend (CLAUDE.md §15a). The
        bound is applied in SQL rather than by slicing in Python: slicing would
        transfer the entire conversation out of the database first, so the
        expensive part -- reading a thousand-message history -- would still
        happen on every turn.

        The subquery takes the *newest* rows and the outer query re-sorts them
        into reading order, because "the last N turns" and "in the order they
        were said" are different orderings and a provider needs the second.

        Args:
            workspace_id: The tenant, from the verified request context.
            conversation_id: Which conversation's history to read.
            limit: How many messages to include. Must be positive; the service
                owns the value.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_MESSAGE_COLUMNS} FROM (
                    SELECT {_MESSAGE_COLUMNS}
                    FROM public.messages
                    WHERE conversation_id = %s
                      AND workspace_id = %s
                      AND deleted_at IS NULL
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                ) AS recent
                ORDER BY created_at ASC, id ASC
                """,  # noqa: S608 - module constant, not input
                (conversation_id, workspace_id, limit),
            )
            rows = cursor.fetchall()

        return tuple(_message_from_row(row) for row in rows)
