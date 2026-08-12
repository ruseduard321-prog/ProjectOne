"""Turn claims, against a real database (STEP-23).

**Every property here is one the offline suite structurally cannot prove**, and
that is the whole reason this file exists. `test_chat_service.py` asserts the
service's decisions against an in-memory fake; a dict has no transaction to roll
back and no concurrency to lose, so it reports success for an implementation
that would fail in production. That is precisely how the original defect shipped
green: `test_a_failed_turn_still_keeps_the_users_question` passed while a real
provider failure discarded the question.

What only PostgreSQL can answer:

- **A claim survives the failure of the call it guards.** The claim commits on
  its own connection, outside the request transaction that the failure rolls
  back.
- **Concurrent claims serialise.** Exactly one of N simultaneous callers may
  invoke a provider -- the property that stops one question being billed twice.
- **A stale token cannot settle a turn it no longer owns.**
- **The reply constraints hold**: same conversation, user role only, one reply
  per turn even after soft deletion.
- **Cross-tenant claims are refused**, over the real workspace predicate.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator

import psycopg
import pytest

from app.repositories.chat_turns import COMPLETED, IN_PROGRESS, PENDING, ChatTurnRepository
from tests.conftest import Identity, seed_identity

pytestmark = pytest.mark.usefixtures("migrated_database")


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[tuple[Identity, Identity]]:
    """Seed two unrelated tenants, each owning one workspace."""
    yield seed_identity(admin_connection, "alice"), seed_identity(admin_connection, "bob")


def _question(
    connection: psycopg.Connection, identity: Identity, content: str = "q"
) -> tuple[uuid.UUID, uuid.UUID]:
    """Store a conversation and one pending question, returning both ids."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.conversations (workspace_id, title, created_by) "
            "VALUES (%s, %s, %s) RETURNING id",
            (identity.workspace_id, content, identity.user_id),
        )
        row = cursor.fetchone()
        assert row is not None
        conversation_id = row[0]

        cursor.execute(
            "INSERT INTO public.messages "
            "(workspace_id, conversation_id, role, content, turn_status) "
            "VALUES (%s, %s, 'user', %s, 'pending') RETURNING id",
            (identity.workspace_id, conversation_id, content),
        )
        row = cursor.fetchone()
        assert row is not None

    connection.commit()

    return conversation_id, row[0]


class _Secret:
    """Minimal `SecretStr` stand-in exposing only what the repository calls."""

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


@pytest.fixture
def repository(migrated_database: str) -> ChatTurnRepository:
    """The real repository, pointed at the throwaway database.

    A minimal settings stand-in rather than real `Settings`, matching
    `test_ai_spend_isolation.py`: this suite needs no environment beyond the
    test database URL.
    """

    class _Settings:
        database_url = _Secret(migrated_database)
        database_health_timeout_seconds = 10

    return ChatTurnRepository(_Settings())  # type: ignore[arg-type]


def test_only_one_of_many_concurrent_callers_may_invoke_a_provider(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """The property that stops one question being billed twice.

    A unique index on the reply was the first design and was rejected for
    exactly this reason: it would let every caller invoke the provider and be
    charged, then refuse the duplicate *row* afterwards. Deduplicating storage
    is not deduplicating spend.

    Four threads, one shared turn. The claim is a conditional UPDATE, so
    PostgreSQL serialises it and exactly one caller may proceed.
    """
    alice, _bob = tenants
    _conversation_id, user_message_id = _question(admin_connection, alice)

    winners: list[uuid.UUID] = []
    lock = threading.Lock()

    def attempt() -> None:
        claim = repository.claim(alice.workspace_id, user_message_id)

        if claim is not None:
            with lock:
                winners.append(claim.claim_token)

    threads = [threading.Thread(target=attempt) for _ in range(4)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert len(winners) == 1, f"expected exactly one claimant, got {len(winners)}"
    assert repository.status_of(alice.workspace_id, user_message_id) == IN_PROGRESS


def test_a_claim_survives_a_rolled_back_request_transaction(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """The claim must outlive the failure it guards.

    This is the defect in miniature. The request runs inside one transaction, so
    a provider failure rolls back everything written on the request's own
    connection. The claim is written on a *different* connection precisely so it
    does not vanish with it.

    A transaction is opened and rolled back on the tenant-path connection around
    the claim, standing in for the failing request.
    """
    alice, _bob = tenants
    _conversation_id, user_message_id = _question(admin_connection, alice)

    with admin_connection.transaction():
        claim = repository.claim(alice.workspace_id, user_message_id)
        assert claim is not None

        # Whatever this request wrote is about to be discarded.
        raise psycopg.Rollback

    # The claim is still held: it was never part of that transaction.
    assert repository.status_of(alice.workspace_id, user_message_id) == IN_PROGRESS


def test_a_released_turn_can_be_claimed_again(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """An ordinary provider failure must leave the turn retryable."""
    alice, _bob = tenants
    _conversation_id, user_message_id = _question(admin_connection, alice)

    first = repository.claim(alice.workspace_id, user_message_id)
    assert first is not None

    assert repository.release(alice.workspace_id, first) is True
    assert repository.status_of(alice.workspace_id, user_message_id) == PENDING

    second = repository.claim(alice.workspace_id, user_message_id)
    assert second is not None
    assert second.claim_token != first.claim_token


def test_a_superseded_claim_cannot_settle_the_turn(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """A stale holder must not be able to finish someone else's turn.

    Without the token check, a caller whose claim was released could return late
    and mark the turn complete -- overwriting the state of the caller that now
    legitimately owns it.
    """
    alice, _bob = tenants
    _conversation_id, user_message_id = _question(admin_connection, alice)

    stale = repository.claim(alice.workspace_id, user_message_id)
    assert stale is not None
    repository.release(alice.workspace_id, stale)

    current = repository.claim(alice.workspace_id, user_message_id)
    assert current is not None

    assert repository.complete(alice.workspace_id, stale) is False
    assert repository.release(alice.workspace_id, stale) is False
    assert repository.status_of(alice.workspace_id, user_message_id) == IN_PROGRESS

    assert repository.complete(alice.workspace_id, current) is True
    assert repository.status_of(alice.workspace_id, user_message_id) == COMPLETED


def test_another_tenants_turn_cannot_be_claimed(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """The claim path runs on a privileged connection, so it scopes itself.

    RLS is not what protects this query -- the repository's own `workspace_id`
    predicate is. That is a weaker guarantee than the rest of chat enjoys, which
    is exactly why it is asserted here rather than assumed.
    """
    alice, bob = tenants
    _conversation_id, bobs_question = _question(admin_connection, bob)

    assert repository.claim(alice.workspace_id, bobs_question) is None
    assert repository.status_of(alice.workspace_id, bobs_question) is None

    # Still claimable by its rightful owner, so the refusal above was scoping
    # rather than the turn being unclaimable for some unrelated reason.
    assert repository.claim(bob.workspace_id, bobs_question) is not None


def test_a_completed_turn_cannot_be_claimed_again(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """A double-submitted completion must not reach a provider twice."""
    alice, _bob = tenants
    _conversation_id, user_message_id = _question(admin_connection, alice)

    claim = repository.claim(alice.workspace_id, user_message_id)
    assert claim is not None
    assert repository.complete(alice.workspace_id, claim) is True

    assert repository.claim(alice.workspace_id, user_message_id) is None


def test_one_turn_admits_one_reply_even_after_it_is_deleted(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
) -> None:
    """`uq_messages_reply_to` is total, not partial.

    A partial index (`WHERE deleted_at IS NULL`) was tested against a real
    database and permitted a second reply once the first was soft-deleted --
    which would let deleting a reply license a fresh provider call and a fresh
    charge. A turn is consumed permanently.
    """
    alice, _bob = tenants
    conversation_id, user_message_id = _question(admin_connection, alice)

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.messages "
            "(workspace_id, conversation_id, role, content, reply_to) "
            "VALUES (%s, %s, 'assistant', 'a', %s)",
            (alice.workspace_id, conversation_id, user_message_id),
        )
        cursor.execute(
            "UPDATE public.messages SET deleted_at = now() WHERE reply_to = %s",
            (user_message_id,),
        )
    admin_connection.commit()

    with admin_connection.transaction(), pytest.raises(psycopg.errors.UniqueViolation):
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.messages "
                "(workspace_id, conversation_id, role, content, reply_to) "
                "VALUES (%s, %s, 'assistant', 'second', %s)",
                (alice.workspace_id, conversation_id, user_message_id),
            )


def test_a_reply_must_answer_a_user_message_in_its_own_conversation(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
) -> None:
    """The composite FK proves co-tenancy; eligibility needs more than that.

    A reply pointing at another *conversation's* question, or at another
    assistant message, satisfies every foreign key while being nonsense. Both
    are comparisons between two rows, which is neither an FK's nor a policy's
    job -- hence `app_messages_reply_eligible`.
    """
    alice, _bob = tenants
    first_conversation, first_question = _question(admin_connection, alice, "one")
    _second_conversation, second_question = _question(admin_connection, alice, "two")

    with admin_connection.transaction(), pytest.raises(psycopg.errors.CheckViolation):
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.messages "
                "(workspace_id, conversation_id, role, content, reply_to) "
                "VALUES (%s, %s, 'assistant', 'x', %s)",
                (alice.workspace_id, first_conversation, second_question),
            )

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.messages "
            "(workspace_id, conversation_id, role, content, reply_to) "
            "VALUES (%s, %s, 'assistant', 'a', %s) RETURNING id",
            (alice.workspace_id, first_conversation, first_question),
        )
        row = cursor.fetchone()
        assert row is not None
        reply_id = row[0]
    admin_connection.commit()

    # A reply answering a reply is equally refused.
    with admin_connection.transaction(), pytest.raises(psycopg.errors.CheckViolation):
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.messages "
                "(workspace_id, conversation_id, role, content, reply_to) "
                "VALUES (%s, %s, 'assistant', 'x', %s)",
                (alice.workspace_id, first_conversation, reply_id),
            )


def test_every_question_is_an_independent_turn(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """Idempotency is per question, never per conversation.

    Keying on the conversation would make a legitimate follow-up look like a
    retry of the previous question and refuse it -- turning a correctness
    guarantee into a bug that silently blocks conversation.
    """
    alice, _bob = tenants
    conversation_id, first_question = _question(admin_connection, alice, "one")

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.messages "
            "(workspace_id, conversation_id, role, content, turn_status) "
            "VALUES (%s, %s, 'user', 'two', 'pending') RETURNING id",
            (alice.workspace_id, conversation_id),
        )
        row = cursor.fetchone()
        assert row is not None
        second_question = row[0]
    admin_connection.commit()

    first = repository.claim(alice.workspace_id, first_question)
    assert first is not None
    assert repository.complete(alice.workspace_id, first) is True

    # The second question in the same conversation is claimable on its own.
    second = repository.claim(alice.workspace_id, second_question)
    assert second is not None
