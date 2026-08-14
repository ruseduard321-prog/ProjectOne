"""Conversation memory, context assembly, and the honesty of a failed turn.

These run offline against a fake conversation store, so they assert *behaviour*
rather than persistence -- the database-backed properties (tenant isolation,
erasure, the role vocabulary matching its constraint) live in
`test_chat_isolation.py`, which needs a real PostgreSQL to mean anything.

The assertions worth making here are the ones a passing provider call would hide:
that the context window is genuinely bounded, that a failure persists the
question but never a fabricated answer, and that the governed path is the only
path to a provider.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from app.ai.crypto import CredentialCipher
from app.ai.errors import (
    AllProvidersFailedError,
    NoProviderAvailableError,
    ProviderUnavailableError,
)
from app.ai.health import ProviderHealthTracker
from app.ai.provider import Role
from app.ai.router import AIRouter
from app.repositories.chat_turns import TurnClaim
from app.repositories.conversations import ChatMessage, Conversation
from app.services.ai_service import AIService
from app.services.ai_spend_service import AISpendService
from app.services.chat_service import (
    _CONTEXT_MESSAGE_LIMIT,
    ChatService,
    ConversationNotFoundError,
    TurnNotClaimableError,
    _title_from,
)
from app.services.provider_credential_service import ProviderCredentialService
from tests.fakes import FakeSpendRepository
from tests.test_ai_router import FakeProvider
from tests.test_byok_credentials import FakeRepository

KEY = "sk-workspace-key-0000000000"  # noqa: S105 - test fixture


class FakeConversationRepository:
    """An in-memory stand-in for `ConversationRepository`.

    Records what it was asked for as well as what it stored: several assertions
    below are about the *query* the service made -- specifically the limit it
    passed -- rather than about the rows that came back.
    """

    def __init__(self) -> None:
        self.conversations: dict[uuid.UUID, Conversation] = {}
        self.messages: list[ChatMessage] = []
        self.history_limits: list[int] = []
        self.touched: list[uuid.UUID] = []

    def create(
        self,
        workspace_id: uuid.UUID,
        title: str,
        project_id: uuid.UUID | None,
        created_by: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> Conversation:
        # Mirrors the primary key: a caller-supplied id that is already taken --
        # including by another tenant, which `get` correctly hides -- is refused
        # rather than silently adopting or overwriting the existing row.
        if conversation_id is not None and conversation_id in self.conversations:
            raise psycopg.errors.UniqueViolation(f"conversation {conversation_id} already exists")

        now = datetime.now(UTC)
        conversation = Conversation(
            id=uuid.uuid4() if conversation_id is None else conversation_id,
            workspace_id=workspace_id,
            title=title,
            project_id=project_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            version=1,
        )
        self.conversations[conversation.id] = conversation
        return conversation

    def get(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
        conversation = self.conversations.get(conversation_id)

        # Mirrors RLS: another tenant's row is indistinguishable from an absent
        # one, so the fake must not reveal it either.
        if conversation is None or conversation.workspace_id != workspace_id:
            return None

        return conversation

    def list_for_workspace(self, workspace_id: uuid.UUID) -> tuple[Conversation, ...]:
        return tuple(
            conversation
            for conversation in self.conversations.values()
            if conversation.workspace_id == workspace_id
        )

    def touch(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        self.touched.append(conversation_id)

    def soft_delete(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
        conversation = self.get(workspace_id, conversation_id)

        if conversation is None:
            return False

        del self.conversations[conversation_id]
        return True

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
        # Mirrors `uq_messages_reply_to`, which is total rather than partial: a
        # turn is consumed permanently, so a second reply to one is refused even
        # after the first is deleted.
        if reply_to is not None and any(m.reply_to == reply_to for m in self.messages):
            raise psycopg.errors.UniqueViolation(f"turn {reply_to} already has a reply")

        message = ChatMessage(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
            token_count=token_count,
            created_at=datetime.now(UTC),
            turn_status=turn_status,
            reply_to=reply_to,
        )
        self.messages.append(message)
        return message

    def list_messages(
        self, workspace_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> tuple[ChatMessage, ...]:
        return tuple(
            message
            for message in self.messages
            if message.conversation_id == conversation_id and message.workspace_id == workspace_id
        )

    def history_for_context(
        self, workspace_id: uuid.UUID, conversation_id: uuid.UUID, limit: int
    ) -> tuple[ChatMessage, ...]:
        self.history_limits.append(limit)
        stored = self.list_messages(workspace_id, conversation_id)
        return stored[-limit:]


class FakeTurnRepository:
    """An in-memory stand-in for `ChatTurnRepository`.

    **This fake cannot prove the property the real one exists for.** The claim
    is durable specifically because it commits on its own connection, outside
    the request transaction that a provider failure rolls back -- and a dict has
    no transaction to roll back, so these tests would pass against an
    implementation that wrote the claim inside the request and lost it.

    That is exactly how the original defect survived a green suite. The
    transaction behaviour is asserted in `test_chat_turn_claims.py`, against a
    real database, and this fake only covers the decisions layered on top of it.
    """

    def __init__(self) -> None:
        self.status: dict[uuid.UUID, str] = {}
        self.tokens: dict[uuid.UUID, uuid.UUID] = {}
        self.claims: list[uuid.UUID] = []
        self.releases: list[uuid.UUID] = []
        #: Which conversation each question belongs to.
        #:
        #: Tracked because the real predicate now includes it. Without this the
        #: fake would answer a cross-conversation claim happily and this suite
        #: would stay green against the very defect the change fixes -- the
        #: pattern that already let three defects through this step.
        self.conversations: dict[uuid.UUID, uuid.UUID] = {}

    def claim(
        self,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
    ) -> object | None:
        if self.status.get(user_message_id) != "pending":
            return None

        if self.conversations.get(user_message_id) != conversation_id:
            return None

        token = uuid.uuid4()
        self.status[user_message_id] = "in_progress"
        self.tokens[user_message_id] = token
        self.claims.append(user_message_id)

        return TurnClaim(user_message_id=user_message_id, claim_token=token)

    def release(self, workspace_id: uuid.UUID, claim: TurnClaim) -> bool:
        if self.tokens.get(claim.user_message_id) != claim.claim_token:
            return False

        self.status[claim.user_message_id] = "pending"
        del self.tokens[claim.user_message_id]
        self.releases.append(claim.user_message_id)

        return True

    def complete(self, workspace_id: uuid.UUID, claim: TurnClaim) -> bool:
        if self.tokens.get(claim.user_message_id) != claim.claim_token:
            return False

        self.status[claim.user_message_id] = "completed"
        del self.tokens[claim.user_message_id]

        return True

    def status_of(
        self,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
    ) -> str | None:
        if self.conversations.get(user_message_id) != conversation_id:
            return None

        return self.status.get(user_message_id)


class FakeProjectRepository:
    """Returns whichever project a test planted, scoped by workspace."""

    def __init__(self) -> None:
        self.projects: dict[uuid.UUID, object] = {}

    def get(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> object | None:
        project = self.projects.get(project_id)

        if project is None or project.workspace_id != workspace_id:  # type: ignore[attr-defined]
            return None

        return project


class StubProject:
    """The two fields `_project_context` reads."""

    def __init__(self, workspace_id: uuid.UUID, name: str, description: str | None) -> None:
        self.workspace_id = workspace_id
        self.name = name
        self.description = description


def build(
    providers: tuple[FakeProvider, ...] | None = None,
    *,
    configure_key: bool = True,
) -> tuple[ChatService, FakeConversationRepository, FakeProjectRepository, uuid.UUID]:
    """Wire a chat service over fakes, returning it with its stores and workspace.

    The workspace is created here and its key configured by default, because a
    workspace with no key raises before any of these assertions are reachable --
    that path has its own test.
    """
    workspace = uuid.uuid4()
    conversations = FakeConversationRepository()
    projects = FakeProjectRepository()

    credentials = ProviderCredentialService(FakeRepository(), CredentialCipher(os.urandom(32)))
    router = AIRouter(providers or (FakeProvider("openai"),), ProviderHealthTracker())
    ai = AIService(router, credentials, AISpendService(FakeSpendRepository()))

    if configure_key:
        credentials.store(workspace, "openai", KEY, uuid.uuid4())

    turns = FakeTurnRepository()

    service = ChatService(conversations, projects, ai, turns)  # type: ignore[arg-type]

    # The fake mirrors the schema's own rule: a user message is `pending` from
    # the moment it is stored. Wiring it here rather than in each test keeps the
    # two halves of a turn in step without every test restating the setup.
    original_add = conversations.add_message

    def add_message(*args: object, **kwargs: object) -> ChatMessage:
        message = original_add(*args, **kwargs)  # type: ignore[arg-type]

        if message.role == "user":
            turns.status[message.id] = "pending"
            turns.conversations[message.id] = message.conversation_id

        return message

    conversations.add_message = add_message  # type: ignore[assignment,method-assign]

    return service, conversations, projects, workspace


def send(
    service: ChatService,
    workspace: uuid.UUID,
    content: str,
    actor: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> object:
    """Run both halves of a turn, as a caller does.

    The API is two requests now (`start_turn`, then `complete_turn`), so a test
    asserting end-to-end behaviour makes both calls. Kept as a helper rather
    than repeated, so the *ordering* is stated in one place -- and a test that
    deliberately exercises only one half calls that half directly.
    """
    actor_id = actor or uuid.uuid4()

    pending = service.start_turn(
        workspace, content, actor_id, conversation_id=conversation_id, project_id=project_id
    )

    return service.complete_turn(
        workspace_id=workspace,
        conversation_id=pending.conversation.id,
        user_message_id=pending.user_message.id,
        actor_id=actor_id,
    )


def test_a_turn_persists_the_question_and_the_reply() -> None:
    service, store, _, workspace = build()

    turn = send(service, workspace, "What should I film?", uuid.uuid4())

    assert turn.user_message.role == "user"
    assert turn.assistant_message.role == "assistant"
    assert len(store.messages) == 2


def test_the_reply_records_which_provider_answered() -> None:
    # After a fallback the answering provider is not the one selection chose, so
    # a reply that does not say which is one the caller cannot attribute.
    service, _, _, workspace = build((FakeProvider("openai", model="fake-model"),))

    turn = send(service, workspace, "Hello", uuid.uuid4())

    assert turn.assistant_message.provider == "openai"
    assert turn.assistant_message.model == "fake-model"


def test_a_new_conversation_takes_its_title_from_the_first_message() -> None:
    service, _, _, workspace = build()

    turn = send(service, workspace, "Plan my launch week", uuid.uuid4())

    assert turn.conversation.title == "Plan my launch week"


def test_the_context_window_is_bounded() -> None:
    # The step's central cost property: every message in the window is replayed
    # on every later turn, so an unbounded window grows the bill forever.
    service, store, _, workspace = build()
    actor = uuid.uuid4()

    turn = send(service, workspace, "First", actor)

    for index in range(30):
        send(service, workspace, f"Message {index}", actor, turn.conversation.id)

    assert store.history_limits, "the service never read a bounded history"
    assert set(store.history_limits) == {_CONTEXT_MESSAGE_LIMIT}


def test_a_long_conversation_sends_no_more_than_the_window() -> None:
    # Asserted against what the provider actually received, not only against the
    # limit passed to the query -- the two could disagree.
    provider = FakeProvider("openai")
    service, _, _, workspace = build((provider,))
    actor = uuid.uuid4()

    turn = send(service, workspace, "First", actor)

    for index in range(30):
        send(service, workspace, f"Message {index}", actor, turn.conversation.id)

    # One system instruction plus at most the window of stored turns.
    assert provider.requests_seen[-1] <= _CONTEXT_MESSAGE_LIMIT + 1


def test_a_provider_failure_raises_rather_than_fabricating_a_reply() -> None:
    # CLAUDE.md §15: no canned apology stored as though the model said it.
    service, store, _, workspace = build(
        (FakeProvider("openai", fail_with=ProviderUnavailableError("upstream is down", "openai")),)
    )

    with pytest.raises(AllProvidersFailedError):
        send(service, workspace, "Are you there?", uuid.uuid4())

    assert all(message.role != "assistant" for message in store.messages)


def test_a_failed_turn_still_keeps_the_users_question() -> None:
    # A provider outage costs the user their answer; it must not also discard
    # what they typed.
    service, store, _, workspace = build(
        (FakeProvider("openai", fail_with=ProviderUnavailableError("upstream is down", "openai")),)
    )

    with pytest.raises(AllProvidersFailedError):
        send(service, workspace, "Remember this", uuid.uuid4())

    assert [message.content for message in store.messages] == ["Remember this"]


def test_a_workspace_with_no_key_fails_honestly() -> None:
    service, store, _, workspace = build(configure_key=False)

    with pytest.raises(NoProviderAvailableError):
        send(service, workspace, "Hello", uuid.uuid4())

    assert all(message.role != "assistant" for message in store.messages)


def test_an_unknown_conversation_id_starts_a_conversation_with_it() -> None:
    # This replaces an earlier `ConversationNotFoundError`, and the change is the
    # whole of the first-turn recovery fix.
    #
    # Refusing an unknown id meant the id of a new conversation existed only
    # inside a successful response. A first turn that failed at the provider
    # therefore saved the user's question under an id the client never learned,
    # and the retry -- which had no id to send -- created a *second* conversation
    # holding a *second* copy of the question.
    #
    # Accepting the id makes the retry land in the conversation that already
    # holds the question, which is what "try that again" means to the user.
    service, store, _, workspace = build()
    chosen = uuid.uuid4()

    turn = send(service, workspace, "Hi", uuid.uuid4(), chosen)

    assert turn.conversation.id == chosen
    assert store.conversations[chosen].workspace_id == workspace


def test_retrying_with_the_same_id_continues_one_conversation() -> None:
    # The property the fix exists for, asserted end to end at the service level:
    # two sends carrying one id produce one conversation, not two.
    service, store, _, workspace = build()
    chosen = uuid.uuid4()
    actor = uuid.uuid4()

    send(service, workspace, "Hi", actor, chosen)
    send(service, workspace, "Hi", actor, chosen)

    assert len(store.conversations) == 1

    # And the title still comes from the first message rather than being
    # rewritten by the retry -- the conversation was continued, not recreated.
    assert store.conversations[chosen].title == "Hi"


def test_a_stored_question_survives_a_provider_failure() -> None:
    # The defect manual testing caught, asserted at the service layer.
    #
    # `start_turn` makes no network call, so what it stores is committed before
    # anything can fail. The old single-method design persisted the question and
    # then called the provider inside one transaction, so the failure rolled the
    # question back -- while this suite's fake, having no transaction, reported
    # that it had not.
    service, store, _, workspace = build(
        (FakeProvider("openai", fail_with=ProviderUnavailableError("down", "openai")),)
    )
    actor = uuid.uuid4()

    pending = service.start_turn(workspace, "Remember this", actor)

    with pytest.raises(AllProvidersFailedError):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=pending.conversation.id,
            user_message_id=pending.user_message.id,
            actor_id=actor,
        )

    assert [m.content for m in store.messages] == ["Remember this"]
    assert all(m.role != "assistant" for m in store.messages)


def test_a_failed_turn_is_released_so_it_can_be_retried() -> None:
    # Releasing is what makes a provider outage retryable rather than terminal:
    # the question stays stored and the turn becomes claimable again, so the
    # user's retry is another attempt at the same question.
    provider = FakeProvider("openai", fail_with=ProviderUnavailableError("down", "openai"))
    service, _, _, workspace = build((provider,))
    actor = uuid.uuid4()

    pending = service.start_turn(workspace, "Hello", actor)

    with pytest.raises(AllProvidersFailedError):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=pending.conversation.id,
            user_message_id=pending.user_message.id,
            actor_id=actor,
        )

    turns = service._turns  # noqa: SLF001 - asserting the collaborator's state
    assert turns.status[pending.user_message.id] == "pending"
    assert turns.releases == [pending.user_message.id]


def test_a_second_completion_of_one_turn_is_refused() -> None:
    # The concurrency property, at the service layer: a turn already answered
    # cannot be answered again, so a double-submitted completion cannot reach a
    # provider twice. The database-backed half -- that concurrent claims
    # serialise -- is in `test_chat_turn_claims.py`, where it can actually be
    # proven.
    service, store, _, workspace = build()
    actor = uuid.uuid4()

    pending = service.start_turn(workspace, "Hello", actor)
    service.complete_turn(
        workspace_id=workspace,
        conversation_id=pending.conversation.id,
        user_message_id=pending.user_message.id,
        actor_id=actor,
    )

    with pytest.raises(TurnNotClaimableError):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=pending.conversation.id,
            user_message_id=pending.user_message.id,
            actor_id=actor,
        )

    assert len([m for m in store.messages if m.role == "assistant"]) == 1


def test_a_question_cannot_be_answered_through_another_conversation() -> None:
    # **The defect review caught, at the service layer.**
    #
    # `conversation_id` and `user_message_id` were each validated against the
    # workspace and neither against the other, so naming conversation A in the
    # URL and a pending question from conversation B in the body passed both
    # checks. The claim succeeded, the provider was called and charged against
    # A's context, and only then did the database refuse the reply -- leaving
    # B's question `in_progress`, unanswered, and paid for.
    #
    # The provider must never be reached. That is the whole assertion: no call,
    # no charge, no reply, and B's question still exactly as it was.
    provider = FakeProvider("openai")
    service, store, _, workspace = build((provider,))
    actor = uuid.uuid4()

    a = service.start_turn(workspace, "asked in A", actor)
    b = service.start_turn(workspace, "asked in B", actor)

    assert a.conversation.id != b.conversation.id

    calls_before = provider.calls
    assistant_before = len([m for m in store.messages if m.role == "assistant"])

    # Conversation A's endpoint, conversation B's question.
    with pytest.raises(ConversationNotFoundError):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=a.conversation.id,
            user_message_id=b.user_message.id,
            actor_id=actor,
        )

    # No provider call, so no charge could have been incurred.
    assert provider.calls == calls_before
    # No reply was stored anywhere.
    assert len([m for m in store.messages if m.role == "assistant"]) == assistant_before
    # B's question is untouched and still answerable through its own
    # conversation -- refusing the request must not consume the turn.
    turns = service._turns  # noqa: SLF001 - asserting the collaborator's state
    assert turns.status[b.user_message.id] == "pending"
    assert b.user_message.id not in turns.tokens


def test_a_question_refused_this_way_is_still_answerable_properly() -> None:
    # The refusal must not leave a scar. After the cross-conversation attempt,
    # answering B through B's own endpoint has to work normally -- otherwise the
    # fix would have turned a stuck turn into a permanently unanswerable one.
    service, store, _, workspace = build()
    actor = uuid.uuid4()

    a = service.start_turn(workspace, "asked in A", actor)
    b = service.start_turn(workspace, "asked in B", actor)

    with pytest.raises(ConversationNotFoundError):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=a.conversation.id,
            user_message_id=b.user_message.id,
            actor_id=actor,
        )

    turn = service.complete_turn(
        workspace_id=workspace,
        conversation_id=b.conversation.id,
        user_message_id=b.user_message.id,
        actor_id=actor,
    )

    turns = service._turns  # noqa: SLF001 - asserting the collaborator's state
    assert turn.assistant_message.reply_to == b.user_message.id
    assert turns.status[b.user_message.id] == "completed"


def test_each_question_is_its_own_turn() -> None:
    # Idempotency is per user message, not per conversation. Keying on the
    # conversation would make a legitimate follow-up look like a retry and
    # refuse it.
    service, store, _, workspace = build()
    actor = uuid.uuid4()

    first = service.start_turn(workspace, "One", actor)
    service.complete_turn(
        workspace_id=workspace,
        conversation_id=first.conversation.id,
        user_message_id=first.user_message.id,
        actor_id=actor,
    )

    second = service.start_turn(workspace, "Two", actor, conversation_id=first.conversation.id)
    service.complete_turn(
        workspace_id=workspace,
        conversation_id=second.conversation.id,
        user_message_id=second.user_message.id,
        actor_id=actor,
    )

    assert first.conversation.id == second.conversation.id
    assert len([m for m in store.messages if m.role == "assistant"]) == 2


def test_another_tenants_conversation_is_not_continuable() -> None:
    # The service-level half of the isolation property; the RLS half is proven
    # against a real database in `test_chat_isolation.py`.
    #
    # **The refusal moved, and that is the point.** It used to be a 404 from
    # `get`. Now `get` still hides the row -- so the service treats the id as
    # new -- and the *primary key* refuses the insert. A caller therefore cannot
    # reach, adopt or overwrite another tenant's conversation by naming its id,
    # and the failure is loud rather than a silent cross-tenant write.
    service, store, _, workspace = build()
    theirs = store.create(uuid.uuid4(), "Theirs", None, uuid.uuid4())

    with pytest.raises(psycopg.errors.UniqueViolation):
        send(service, workspace, "Hi", uuid.uuid4(), theirs.id)

    # Their conversation is untouched: same workspace, same title, and no
    # message was smuggled into it.
    assert store.conversations[theirs.id].workspace_id == theirs.workspace_id
    assert store.conversations[theirs.id].title == "Theirs"
    assert store.messages == []


def test_the_active_project_reaches_the_model() -> None:
    provider = FakeProvider("openai")
    service, _, projects, workspace = build((provider,))
    project_id = uuid.uuid4()
    projects.projects[project_id] = StubProject(workspace, "Spring campaign", "Launch video")

    send(service, workspace, "What next?", uuid.uuid4(), project_id=project_id)

    sent = provider.last_request
    assert sent is not None
    system_text = " ".join(
        message.content for message in sent.messages if message.role == Role.SYSTEM
    )
    assert "Spring campaign" in system_text
    assert "Launch video" in system_text


def test_a_deleted_project_does_not_fail_the_turn() -> None:
    # The project is read on every turn; one deleted mid-conversation should
    # contribute no context rather than break the conversation.
    service, _, _, workspace = build()

    turn = send(service, workspace, "Still here?", uuid.uuid4(), project_id=uuid.uuid4())

    assert turn.assistant_message.content


def test_a_conversation_without_a_project_sends_no_project_context() -> None:
    provider = FakeProvider("openai")
    service, _, _, workspace = build((provider,))

    send(service, workspace, "Hello", uuid.uuid4())

    sent = provider.last_request
    assert sent is not None
    system_messages = [m for m in sent.messages if m.role == Role.SYSTEM]
    assert len(system_messages) == 1


def test_deleting_a_conversation_reports_whether_it_existed() -> None:
    service, store, _, workspace = build()
    turn = send(service, workspace, "Hello", uuid.uuid4())

    assert service.delete_conversation(workspace, turn.conversation.id) is True
    assert service.delete_conversation(workspace, turn.conversation.id) is False


def test_a_conversations_project_is_fixed_after_creation() -> None:
    # Changing it mid-conversation would silently rewrite what earlier turns
    # were answered against.
    service, _, projects, workspace = build()
    first = uuid.uuid4()
    projects.projects[first] = StubProject(workspace, "First", None)

    turn = send(service, workspace, "Hello", uuid.uuid4(), project_id=first)
    again = send(
        service, workspace, "Again", uuid.uuid4(), turn.conversation.id, project_id=uuid.uuid4()
    )

    assert again.conversation.project_id == first


def test_the_transcript_is_unbounded_while_the_context_is_not() -> None:
    # The window bounds spend, not the user's access to their own history.
    service, _, _, workspace = build()
    actor = uuid.uuid4()
    turn = send(service, workspace, "First", actor)

    for index in range(25):
        send(service, workspace, f"Message {index}", actor, turn.conversation.id)

    transcript = service.list_messages(workspace, turn.conversation.id)

    assert len(transcript) > _CONTEXT_MESSAGE_LIMIT


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("Short question", "Short question"),
        ("  collapsed   whitespace  ", "collapsed whitespace"),
    ],
)
def test_a_title_is_derived_from_the_message(content: str, expected: str) -> None:
    assert _title_from(content) == expected


def test_a_long_title_is_truncated_on_a_word_boundary() -> None:
    title = _title_from("word " * 40)

    assert title.endswith("…")
    assert len(title) <= 61
    # Truncated mid-word would leave a severed fragment before the ellipsis.
    assert not title.removesuffix("…").endswith("wor")


def _spend_records(service: ChatService) -> list[object]:
    """Every spend record written through the governed path.

    Reached through the service's own collaborators rather than a fixture,
    because the assertion these tests make is precisely that the *service* did
    not cause a second charge -- so the count has to come from the same object
    the service spent through.
    """
    return service._ai._spend._repository.records  # noqa: SLF001 - asserting spend


def test_a_provider_failure_returns_the_turn_and_charges_nothing() -> None:
    # The first half of the spend boundary: **before** the provider returns,
    # nothing external has happened, so the turn goes back to `pending` and the
    # user may retry at no cost.
    provider = FakeProvider("openai", fail_with=ProviderUnavailableError("down", "openai"))
    service, store, _, workspace = build((provider,))
    actor = uuid.uuid4()

    pending = service.start_turn(workspace, "Hello", actor)

    with pytest.raises(AllProvidersFailedError):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=pending.conversation.id,
            user_message_id=pending.user_message.id,
            actor_id=actor,
        )

    turns = service._turns  # noqa: SLF001 - asserting the collaborator's state
    assert turns.status[pending.user_message.id] == "pending"
    assert pending.user_message.id not in turns.tokens
    assert _spend_records(service) == []
    assert [m for m in store.messages if m.role == "assistant"] == []


def test_a_reply_that_cannot_be_stored_leaves_the_turn_stuck_not_retryable() -> None:
    # **The regression this test exists for.**
    #
    # An earlier revision widened the release block to cover persisting the
    # reply. That closed a stuck-turn hole and opened a worse one: by the time
    # `add_message` runs the provider has answered and the workspace has been
    # charged, so releasing the claim would let Retry invoke and charge a
    # *second* time for one question.
    #
    # This is the documented post-provider crash window, reached by a different
    # route: the external side effect completed and the reply was not durably
    # recorded. It gets the same treatment -- visibly stuck, never silently
    # retried.
    provider = FakeProvider("openai")
    service, store, _, workspace = build((provider,))
    actor = uuid.uuid4()

    pending = service.start_turn(workspace, "Hello", actor)

    # Fail only the assistant insert, leaving the user message path intact.
    def refuse_reply(*args: object, **kwargs: object) -> ChatMessage:
        if kwargs.get("role") == "assistant":
            raise psycopg.errors.CheckViolation("reply refused")

        raise AssertionError("only the reply should be written here")

    store.add_message = refuse_reply  # type: ignore[assignment,method-assign]

    with pytest.raises(psycopg.errors.CheckViolation):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=pending.conversation.id,
            user_message_id=pending.user_message.id,
            actor_id=actor,
        )

    turns = service._turns  # noqa: SLF001 - asserting the collaborator's state

    # Stuck, deliberately: not returned to `pending`, so nothing can retry it.
    assert turns.status[pending.user_message.id] == "in_progress"
    assert pending.user_message.id not in turns.releases

    # One call, one charge -- the guarantee the widened block had broken.
    assert provider.calls == 1
    assert len(_spend_records(service)) == 1

    # And no fabricated answer anywhere.
    assert [m for m in store.messages if m.role == "assistant"] == []


def test_retrying_a_stranded_turn_is_refused_rather_than_charged_again() -> None:
    # The user-facing half: a turn stranded after a charge answers 409, which
    # the UI reports as "already being answered". It must not reach a provider.
    provider = FakeProvider("openai")
    service, store, _, workspace = build((provider,))
    actor = uuid.uuid4()

    pending = service.start_turn(workspace, "Hello", actor)

    def refuse_reply(*args: object, **kwargs: object) -> ChatMessage:
        raise psycopg.errors.CheckViolation("reply refused")

    store.add_message = refuse_reply  # type: ignore[assignment,method-assign]

    with pytest.raises(psycopg.errors.CheckViolation):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=pending.conversation.id,
            user_message_id=pending.user_message.id,
            actor_id=actor,
        )

    calls_after_first = provider.calls
    charges_after_first = len(_spend_records(service))

    # The retry the user would press.
    with pytest.raises(TurnNotClaimableError):
        service.complete_turn(
            workspace_id=workspace,
            conversation_id=pending.conversation.id,
            user_message_id=pending.user_message.id,
            actor_id=actor,
        )

    # Refused before reaching a provider: still one call, still one charge.
    assert provider.calls == calls_after_first == 1
    assert len(_spend_records(service)) == charges_after_first == 1
