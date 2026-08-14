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
    conversation_id, user_message_id = _question(admin_connection, alice)

    winners: list[uuid.UUID] = []
    lock = threading.Lock()

    def attempt() -> None:
        claim = repository.claim(alice.workspace_id, conversation_id, user_message_id)

        if claim is not None:
            with lock:
                winners.append(claim.claim_token)

    threads = [threading.Thread(target=attempt) for _ in range(4)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert len(winners) == 1, f"expected exactly one claimant, got {len(winners)}"
    assert repository.status_of(alice.workspace_id, conversation_id, user_message_id) == IN_PROGRESS


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
    conversation_id, user_message_id = _question(admin_connection, alice)

    with admin_connection.transaction():
        claim = repository.claim(alice.workspace_id, conversation_id, user_message_id)
        assert claim is not None

        # Whatever this request wrote is about to be discarded.
        raise psycopg.Rollback

    # The claim is still held: it was never part of that transaction.
    assert repository.status_of(alice.workspace_id, conversation_id, user_message_id) == IN_PROGRESS


def test_a_released_turn_can_be_claimed_again(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """An ordinary provider failure must leave the turn retryable."""
    alice, _bob = tenants
    conversation_id, user_message_id = _question(admin_connection, alice)

    first = repository.claim(alice.workspace_id, conversation_id, user_message_id)
    assert first is not None

    assert repository.release(alice.workspace_id, first) is True
    assert repository.status_of(alice.workspace_id, conversation_id, user_message_id) == PENDING

    second = repository.claim(alice.workspace_id, conversation_id, user_message_id)
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
    conversation_id, user_message_id = _question(admin_connection, alice)

    stale = repository.claim(alice.workspace_id, conversation_id, user_message_id)
    assert stale is not None
    repository.release(alice.workspace_id, stale)

    current = repository.claim(alice.workspace_id, conversation_id, user_message_id)
    assert current is not None

    assert repository.complete(alice.workspace_id, stale) is False
    assert repository.release(alice.workspace_id, stale) is False
    assert repository.status_of(alice.workspace_id, conversation_id, user_message_id) == IN_PROGRESS

    assert repository.complete(alice.workspace_id, current) is True
    assert repository.status_of(alice.workspace_id, conversation_id, user_message_id) == COMPLETED


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
    bobs_conversation, bobs_question = _question(admin_connection, bob)

    assert repository.claim(alice.workspace_id, bobs_conversation, bobs_question) is None
    assert repository.status_of(alice.workspace_id, bobs_conversation, bobs_question) is None

    # Still claimable by its rightful owner, so the refusal above was scoping
    # rather than the turn being unclaimable for some unrelated reason.
    assert repository.claim(bob.workspace_id, bobs_conversation, bobs_question) is not None


def test_a_completed_turn_cannot_be_claimed_again(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """A double-submitted completion must not reach a provider twice."""
    alice, _bob = tenants
    conversation_id, user_message_id = _question(admin_connection, alice)

    claim = repository.claim(alice.workspace_id, conversation_id, user_message_id)
    assert claim is not None
    assert repository.complete(alice.workspace_id, claim) is True

    assert repository.claim(alice.workspace_id, conversation_id, user_message_id) is None


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

    first = repository.claim(alice.workspace_id, conversation_id, first_question)
    assert first is not None
    assert repository.complete(alice.workspace_id, first) is True

    # The second question in the same conversation is claimable on its own.
    second = repository.claim(alice.workspace_id, conversation_id, second_question)
    assert second is not None


def test_a_retried_turn_answers_the_same_question_and_adds_none(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """Retry answers the stored question rather than asking a new one.

    **The defect manual testing caught, asserted where it actually lives.**
    Every resend went through the send path, which stores a question before
    answering one -- so three failed attempts left three identical `pending`
    rows in one conversation and no reply to any of them. The turn was
    retryable by contract and unreachable in practice.

    The sequence below is the fixed one: fail, release, claim the *same* id,
    answer it. What makes it a retry rather than a resend is that the message
    count does not move.
    """
    alice, _bob = tenants
    conversation_id, user_message_id = _question(admin_connection, alice, "ask once")

    def message_count() -> int:
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.messages WHERE conversation_id = %s",
                (conversation_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            return int(row[0])

    assert message_count() == 1

    # A provider failure: claimed, then released, leaving the turn retryable.
    failed = repository.claim(alice.workspace_id, conversation_id, user_message_id)
    assert failed is not None
    assert repository.release(alice.workspace_id, failed) is True
    assert repository.status_of(alice.workspace_id, conversation_id, user_message_id) == PENDING

    # Still one message. The failure stored nothing and lost nothing.
    assert message_count() == 1

    # The retry: the same turn key, claimed again by a fresh holder.
    retried = repository.claim(alice.workspace_id, conversation_id, user_message_id)
    assert retried is not None
    assert retried.user_message_id == user_message_id

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.messages "
            "(workspace_id, conversation_id, role, content, reply_to) "
            "VALUES (%s, %s, 'assistant', 'answered', %s)",
            (alice.workspace_id, conversation_id, user_message_id),
        )
    admin_connection.commit()

    assert repository.complete(alice.workspace_id, retried) is True
    assert repository.status_of(alice.workspace_id, conversation_id, user_message_id) == COMPLETED

    # Two messages: the original question and its reply. **Not four** -- which
    # is what the resend path produced, and the number that made the defect
    # visible on screen.
    assert message_count() == 2

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM public.messages WHERE conversation_id = %s AND role = 'user'",
            (conversation_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert int(row[0]) == 1, "a retry must not store a second question"


def test_concurrent_retries_of_one_question_yield_one_answer(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """Two Retry clicks are one provider call, one reply, one charge.

    Nothing in the UI serialises a double click, and it does not need to: the
    guarantee has to hold against two browsers anyway. This is the same claim
    race as `test_only_one_of_many_concurrent_callers_may_invoke_a_provider`,
    asserted through the path a *retry* takes -- a turn that was already
    claimed and released once, which is the state a failed turn is in when the
    user reaches for the button.
    """
    alice, _bob = tenants
    conversation_id, user_message_id = _question(admin_connection, alice, "retry me")

    # Put the turn in the state a provider failure leaves it in.
    first = repository.claim(alice.workspace_id, conversation_id, user_message_id)
    assert first is not None
    assert repository.release(alice.workspace_id, first) is True

    winners: list[uuid.UUID] = []
    lock = threading.Lock()

    def retry() -> None:
        claim = repository.claim(alice.workspace_id, conversation_id, user_message_id)

        if claim is not None:
            with lock:
                winners.append(claim.claim_token)

    threads = [threading.Thread(target=retry) for _ in range(4)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Exactly one Retry reaches a provider. The losers get 409, which the UI
    # reports as "already being answered" rather than inviting another click.
    assert len(winners) == 1, f"expected one retry to win, got {len(winners)}"
    assert repository.status_of(alice.workspace_id, conversation_id, user_message_id) == IN_PROGRESS


def test_a_question_cannot_be_claimed_through_another_conversation(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """**The defect review caught, against the database that exposed it.**

    `conversation_id` and `user_message_id` were validated separately -- each
    against the workspace, neither against the other. Naming conversation A in
    the URL and a pending question from conversation B in the body passed both
    checks, so the claim succeeded, the provider was called and charged against
    A's context, and only then did `app_messages_reply_eligible` refuse the
    reply. B's question was left `in_progress`, unanswered, and paid for -- the
    exact stuck state STEP-23 refuses to recover from automatically.

    Both conversations belong to the **same tenant**, which is what makes this
    distinct from the cross-tenant test above: RLS and the workspace predicate
    were both satisfied. Only the relationship between the two ids was wrong.

    The claim must be refused *before* any provider could be reached, so the
    turn is left exactly as it was.
    """
    alice, _bob = tenants
    conversation_a, _question_a = _question(admin_connection, alice, "asked in A")
    conversation_b, question_b = _question(admin_connection, alice, "asked in B")

    assert conversation_a != conversation_b

    # The claim that used to succeed.
    assert repository.claim(alice.workspace_id, conversation_a, question_b) is None

    # Untouched: still pending, still unclaimed. A refused request must not
    # consume the turn, or the fix would trade a stuck turn for a lost one.
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT turn_status, claim_token, claimed_at FROM public.messages WHERE id = %s",
            (question_b,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == PENDING
    assert row[1] is None, "a refused claim must leave no claim token"
    assert row[2] is None, "a refused claim must leave no claim timestamp"

    # No reply was written for it, by anyone.
    with admin_connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM public.messages WHERE reply_to = %s", (question_b,))
        replies = cursor.fetchone()
        assert replies is not None
        assert replies[0] == 0

    # Still answerable through its own conversation: the refusal was scoping,
    # not the turn becoming permanently unclaimable.
    assert repository.claim(alice.workspace_id, conversation_b, question_b) is not None


def test_a_turn_is_invisible_through_the_wrong_conversation(
    admin_connection: psycopg.Connection,
    tenants: tuple[Identity, Identity],
    repository: ChatTurnRepository,
) -> None:
    """Naming the wrong conversation reads as absent, never as taken.

    `status_of` decides between 404 and 409. Left unscoped it would find a
    question belonging to another conversation and answer 409 -- confirming to
    the caller that an id they guessed exists and is being answered, when as far
    as the conversation they named is concerned it does not exist at all. That
    is the same oracle `ConversationNotFoundError` exists to avoid, one level
    down.
    """
    alice, _bob = tenants
    conversation_a, _question_a = _question(admin_connection, alice, "asked in A")
    conversation_b, question_b = _question(admin_connection, alice, "asked in B")

    # Absent through the wrong conversation -> the route answers 404.
    assert repository.status_of(alice.workspace_id, conversation_a, question_b) is None

    # Present through its own -> a genuine 409 when it is already held.
    assert repository.status_of(alice.workspace_id, conversation_b, question_b) == PENDING
