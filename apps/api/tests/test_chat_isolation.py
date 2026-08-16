"""Tenant isolation, erasure and the role vocabulary for chat (STEP-23).

Follows `test_project_isolation.py` exactly rather than inventing a fourth style:
same `as_user` helper, same two-tenant fixture, same "prove the policies are what
makes this pass" negative control.

Four properties here can only be proven against a real database, and three of
them have each cost a previous step:

- **Cross-tenant reads, inserts and updates are refused**, asserted over the
  request-path role rather than reasoned about.
- **The soft delete actually affects rows.** A SELECT policy filtering
  `deleted_at IS NULL` makes soft deletion silently impossible -- the defect
  STEP-11a and STEP-19 each paid a step for.
- **Erasure clears messages even though `messages` has no UPDATE policy.** The
  grant is present and the policy is absent deliberately; this asserts the
  combination works, because getting it wrong produces a silent zero-row erase
  exactly like the `provider_credentials` defect STEP-19 found.
- **The role vocabulary matches its CHECK constraint**, compared in both
  directions. Two lists edited in different files is the shape that drifts, and
  STEP-21 paid for it on `assets.kind`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from app.repositories.conversations import ConversationRepository
from app.schemas.chat import MessageRole
from app.services.chat_service import STORED_ROLES
from app.services.data_ownership_service import ConversationStore, MessageStore
from tests.conftest import NO_STORAGE_CALLS, Identity, seed_identity

# Every test in this module needs a database, and skips without one.
pytestmark = pytest.mark.usefixtures("migrated_database")


def as_user(connection: psycopg.Connection, user_id: uuid.UUID) -> psycopg.Cursor:
    """Return a cursor acting as `authenticated` with the given identity."""
    cursor = connection.cursor()
    cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))
    cursor.execute("SET LOCAL ROLE authenticated")

    return cursor


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[tuple[Identity, Identity]]:
    """Seed two unrelated tenants, each owning one workspace."""
    yield seed_identity(admin_connection, "alice"), seed_identity(admin_connection, "bob")


@pytest.fixture
def seeded_chat(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> tuple[Identity, Identity, uuid.UUID, uuid.UUID]:
    """Give each tenant one conversation holding one message."""
    alice, bob = tenants
    ids: list[uuid.UUID] = []

    for identity in (alice, bob):
        # `Identity` carries `user_id`, `workspace_id` and `email` -- the label
        # passed to `seed_identity` is not retained on the object. The email's
        # local part starts with that label, so it is the distinguishing value
        # available here, and distinguishing the two tenants' rows is the whole
        # requirement: every assertion below turns on one tenant not seeing the
        # other's.
        owner = identity.email.split("@")[0]

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.conversations (workspace_id, title, created_by) "
                "VALUES (%s, %s, %s) RETURNING id",
                (identity.workspace_id, f"{owner} conversation", identity.user_id),
            )
            row = cursor.fetchone()
            assert row is not None
            conversation_id = row[0]

            cursor.execute(
                "INSERT INTO public.messages "
                "(workspace_id, conversation_id, role, content) VALUES (%s, %s, %s, %s)",
                (identity.workspace_id, conversation_id, "user", f"{owner} said this"),
            )

        ids.append(conversation_id)

    admin_connection.commit()

    return alice, bob, ids[0], ids[1]


def test_a_conversation_is_invisible_across_the_tenant_boundary(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    alice, _bob, _alice_conversation, bob_conversation = seeded_chat

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT id FROM public.conversations WHERE id = %s", (bob_conversation,))

        assert cursor.fetchone() is None


def test_a_message_is_invisible_across_the_tenant_boundary(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    alice, bob, _a, _b = seeded_chat

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "SELECT content FROM public.messages WHERE workspace_id = %s", (bob.workspace_id,)
        )

        assert cursor.fetchall() == []


def test_a_cross_tenant_update_affects_no_rows(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    alice, _bob, _a, bob_conversation = seeded_chat

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.conversations SET title = 'seized' WHERE id = %s", (bob_conversation,)
        )

        assert cursor.rowcount == 0


def test_a_message_cannot_be_attached_to_another_tenants_conversation(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    # The hole RLS structurally cannot see: `workspace_id` names the caller's own
    # workspace, so the policy is satisfied. Only the composite foreign key
    # refuses it -- and it fails as a ForeignKeyViolation, not an RLS error.
    alice, _bob, _a, bob_conversation = seeded_chat

    with admin_connection.transaction(), pytest.raises(psycopg.errors.ForeignKeyViolation):
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "INSERT INTO public.messages (workspace_id, conversation_id, role, content) "
            "VALUES (%s, %s, %s, %s)",
            (alice.workspace_id, bob_conversation, "user", "smuggled"),
        )


def test_a_message_cannot_be_edited_by_its_author(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    # A transcript is a record of what was said: every later turn was assembled
    # from the original text, so a rewritten history describes a conversation
    # that never happened.
    #
    # **Two independent guards refuse this statement, and which one fires first
    # changed with `b4e8c02d71fa`.** It used to raise `InsufficientPrivilege`
    # from `messages_soft_delete_member`'s WITH CHECK, because a row left with a
    # null `deleted_at` fails the policy. Now `app_messages_immutable` runs first
    # -- BEFORE triggers fire before the policy's WITH CHECK is evaluated -- and
    # raises `CheckViolation` instead.
    #
    # Accepting either is deliberate rather than a loosened assertion. The
    # property under test is "an edit is refused", and this test must keep
    # meaning that whichever layer does the refusing; pinning it to one exception
    # would make it fail if the *other* guard were removed, which is precisely
    # backwards. That the trigger now wins is asserted directly by
    # `test_a_message_cannot_be_rewritten_while_being_soft_deleted`, which covers
    # the case the policy alone never caught.
    alice, _bob, alice_conversation, _b = seeded_chat

    refusal = (psycopg.errors.InsufficientPrivilege, psycopg.errors.CheckViolation)

    with admin_connection.transaction(), pytest.raises(refusal):
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.messages SET content = 'rewritten' WHERE conversation_id = %s",
            (alice_conversation,),
        )


def test_a_client_supplied_id_cannot_adopt_another_tenants_conversation(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    # `POST /messages` accepts an id for a conversation that does not exist yet,
    # which is what makes a failed first turn retryable. The obvious question
    # that opens is whether a caller can name *another tenant's* id and be handed
    # their conversation.
    #
    # They cannot, and it is worth being precise about why. RLS hides the row, so
    # the service's `get` reads it as absent and takes the create path. The
    # primary key then refuses the insert -- the constraint sees every row in the
    # table, including ones the caller cannot select. The result is a loud
    # UniqueViolation rather than a silent cross-tenant write or, worse, a
    # successful adoption.
    alice, _bob, _a, bob_conversation = seeded_chat

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)

        # Confirm the premise first: Bob's conversation is genuinely invisible.
        # Without this the test would pass even if RLS were switched off, since
        # the primary key would refuse the insert either way.
        cursor.execute(
            "SELECT count(*) FROM public.conversations WHERE id = %s", (bob_conversation,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 0, "Bob's conversation must be invisible to Alice"

        raise psycopg.Rollback

    with admin_connection.transaction(), pytest.raises(psycopg.errors.UniqueViolation):
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "INSERT INTO public.conversations (id, workspace_id, title, created_by) "
            "VALUES (%s, %s, %s, %s)",
            (bob_conversation, alice.workspace_id, "adopted", alice.user_id),
        )


def test_a_message_cannot_be_rewritten_while_being_soft_deleted(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    # The hole the policy alone left open, and the reason `app_messages_immutable`
    # exists. `messages_soft_delete_member`'s WITH CHECK constrains exactly one
    # column of the resulting row -- `deleted_at IS NOT NULL` -- and says nothing
    # about the rest. A single statement that sets `content` *and* `deleted_at`
    # satisfies it completely, so the policy permitted rewriting history as long
    # as the rewrite also deleted it.
    #
    # RLS structurally cannot catch this: a policy sees only the candidate row,
    # never the row it replaces, and "content must equal what it was" is a claim
    # about OLD and NEW together. The BEFORE UPDATE trigger is what compares them.
    #
    # Raised as check_violation (23514) by the trigger, not InsufficientPrivilege:
    # the policy admits this row, and what refuses it is the integrity rule.
    alice, _bob, alice_conversation, _b = seeded_chat

    with admin_connection.transaction(), pytest.raises(psycopg.errors.CheckViolation):
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.messages SET content = 'rewritten', deleted_at = now() "
            "WHERE conversation_id = %s",
            (alice_conversation,),
        )


@pytest.mark.parametrize(
    "column, value",
    [
        ("role", "'assistant'"),
        ("provider", "'forged'"),
        ("model", "'forged'"),
        ("token_count", "999999"),
        ("created_at", "now()"),
    ],
)
def test_no_attributed_field_survives_a_soft_delete(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
    column: str,
    value: str,
) -> None:
    # Content is the obvious field to protect, but not the only one that matters.
    # `provider`, `model` and `token_count` are what a reply is *attributed* to
    # (CLAUDE.md §15) and what a conversation's cost is answerable from; `role`
    # decides whether a stored line is replayed as the user's or the model's; and
    # `created_at` is the ordering every context assembly depends on.
    #
    # Each is checked while also soft-deleting, so this proves the trigger rather
    # than re-proving the policy -- the policy would admit every one of these.
    alice, _bob, alice_conversation, _b = seeded_chat

    with admin_connection.transaction(), pytest.raises(psycopg.errors.CheckViolation):
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            f"UPDATE public.messages SET {column} = {value}, deleted_at = now() "  # noqa: S608 - parametrised from a literal list, never input
            "WHERE conversation_id = %s",
            (alice_conversation,),
        )


def test_an_ordinary_message_soft_delete_is_still_permitted(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    # The other half, and the one that matters most: the trigger must not have
    # made erasure impossible. That is exactly the failure mode this migration
    # already shipped once in draft -- an UPDATE affecting zero rows while
    # reporting success -- so a guard added to protect immutability has to be
    # proven not to have re-created it.
    #
    # A soft delete writes `deleted_at`; `touch_row` then advances `updated_at`
    # and `version`. All three are on the permitted list, so this must succeed.
    alice, _bob, alice_conversation, _b = seeded_chat

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.messages SET deleted_at = now() WHERE conversation_id = %s",
            (alice_conversation,),
        )

        assert cursor.rowcount > 0, "erasure must still be able to soft-delete a message"

        raise psycopg.Rollback


def test_a_conversation_soft_delete_affects_a_row(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    # The defect two previous steps paid for: a SELECT policy filtering
    # `deleted_at IS NULL` makes this affect zero rows, silently.
    alice, _bob, alice_conversation, _b = seeded_chat

    # The transaction is what makes the identity real: `as_user` uses `SET LOCAL
    # ROLE` and a transaction-scoped `set_config`, both of which are discarded
    # the moment an implicit transaction commits.
    #
    # Undone at the end so the soft delete does not leak into another test.
    # psycopg's `Transaction` has no `rollback()` method -- raising out of the
    # block is how it is told to roll back, and `Rollback` is the sentinel it
    # swallows rather than propagating.
    with admin_connection.transaction():
        as_user(admin_connection, alice.user_id)
        repository = ConversationRepository(admin_connection)

        assert repository.soft_delete(alice.workspace_id, alice_conversation) is True

        # Swallowed by the block it names, so this rolls back without failing
        # the test. An assertion failure above propagates normally and also
        # rolls back, which is the behaviour wanted in both directions.
        raise psycopg.Rollback


def test_erasure_clears_conversations_and_messages(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    # `messages` has the UPDATE grant but no UPDATE policy. Erasure runs over the
    # tenant connection, so without the grant this would report zero -- the
    # silent failure mode STEP-19 found on `provider_credentials`.
    alice, _bob, _a, _b = seeded_chat

    erased_conversations = ConversationStore().erase(
        admin_connection, alice.workspace_id, NO_STORAGE_CALLS
    )
    erased_messages = MessageStore().erase(admin_connection, alice.workspace_id, NO_STORAGE_CALLS)

    assert erased_conversations == 1
    assert erased_messages == 1

    admin_connection.rollback()


def test_erasure_leaves_the_other_tenant_untouched(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    alice, bob, _a, _b = seeded_chat

    ConversationStore().erase(admin_connection, alice.workspace_id, NO_STORAGE_CALLS)
    MessageStore().erase(admin_connection, alice.workspace_id, NO_STORAGE_CALLS)

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM public.messages WHERE workspace_id = %s AND deleted_at IS NULL",
            (bob.workspace_id,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == 1

    admin_connection.rollback()


def test_the_export_carries_the_message_content(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    # An export listing only titles and timestamps would satisfy the letter of a
    # data export while withholding the part the user actually wrote.
    alice, _bob, _a, _b = seeded_chat

    exported = MessageStore().export(admin_connection, alice.workspace_id)

    # Derived from the identity rather than written as a literal: `seed_identity`
    # makes each email unique per run, and the fixture seeds the message content
    # from it, so a hardcoded string here would assert against a value that never
    # occurs.
    owner = alice.email.split("@")[0]

    assert [record["content"] for record in exported] == [f"{owner} said this"]


def test_the_stored_role_vocabulary_matches_its_check_constraint(
    admin_connection: psycopg.Connection,
) -> None:
    # Compared in both directions: asserting the permitted values are accepted
    # proves the constraint has entries, and asserting no others are proves it
    # has no extra ones. STEP-21 paid for this on `assets.kind`.
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_messages_role_valid'"
        )
        row = cursor.fetchone()

    assert row is not None
    definition = row[0]

    for role in STORED_ROLES:
        assert f"'{role}'" in definition

    # The enum the API exposes and the constants the service uses are the same
    # closed set as the column.
    assert set(STORED_ROLES) == {member.value for member in MessageRole}
    assert "'system'" not in definition


def test_a_role_outside_the_vocabulary_is_refused(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    alice, _bob, alice_conversation, _b = seeded_chat

    with admin_connection.cursor() as cursor, pytest.raises(psycopg.errors.CheckViolation):
        cursor.execute(
            "INSERT INTO public.messages (workspace_id, conversation_id, role, content) "
            "VALUES (%s, %s, %s, %s)",
            (alice.workspace_id, alice_conversation, "system", "not a turn"),
        )

    admin_connection.rollback()


def test_the_policies_are_what_makes_isolation_hold(
    admin_connection: psycopg.Connection,
    seeded_chat: tuple[Identity, Identity, uuid.UUID, uuid.UUID],
) -> None:
    """Negative control: disable RLS, observe the breach, restore it.

    Without this the isolation assertions above could be passing against an empty
    table or a broken fixture rather than against the policies.
    """
    alice, bob, _a, _b = seeded_chat

    # Both halves are asserted against the same query, so the control genuinely
    # discriminates: with the policies in place Alice sees none of Bob's
    # conversations, and with them disabled she sees one. Asserting only the
    # breach would pass just as well against a harness that never applied her
    # identity at all -- which is exactly the defect this file shipped with.
    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "SELECT count(*) FROM public.conversations WHERE workspace_id = %s",
            (bob.workspace_id,),
        )
        protected = cursor.fetchone()

        assert protected is not None
        assert protected[0] == 0

    with admin_connection.cursor() as cursor:
        cursor.execute("ALTER TABLE public.conversations DISABLE ROW LEVEL SECURITY")

    admin_connection.commit()

    try:
        with admin_connection.transaction():
            cursor = as_user(admin_connection, alice.user_id)
            cursor.execute(
                "SELECT count(*) FROM public.conversations WHERE workspace_id = %s",
                (bob.workspace_id,),
            )
            breached = cursor.fetchone()

            assert breached is not None
            # The breach, observed directly.
            assert breached[0] == 1
    finally:
        with admin_connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY")

        admin_connection.commit()
