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
from app.repositories.conversations import ChatMessage, Conversation
from app.services.ai_service import AIService
from app.services.ai_spend_service import AISpendService
from app.services.chat_service import (
    _CONTEXT_MESSAGE_LIMIT,
    ChatService,
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
    ) -> ChatMessage:
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

    return ChatService(conversations, projects, ai), conversations, projects, workspace  # type: ignore[arg-type]


def test_a_turn_persists_the_question_and_the_reply() -> None:
    service, store, _, workspace = build()

    turn = service.send_message(workspace, "What should I film?", uuid.uuid4())

    assert turn.user_message.role == "user"
    assert turn.assistant_message.role == "assistant"
    assert len(store.messages) == 2


def test_the_reply_records_which_provider_answered() -> None:
    # After a fallback the answering provider is not the one selection chose, so
    # a reply that does not say which is one the caller cannot attribute.
    service, _, _, workspace = build((FakeProvider("openai", model="fake-model"),))

    turn = service.send_message(workspace, "Hello", uuid.uuid4())

    assert turn.assistant_message.provider == "openai"
    assert turn.assistant_message.model == "fake-model"


def test_a_new_conversation_takes_its_title_from_the_first_message() -> None:
    service, _, _, workspace = build()

    turn = service.send_message(workspace, "Plan my launch week", uuid.uuid4())

    assert turn.conversation.title == "Plan my launch week"


def test_the_context_window_is_bounded() -> None:
    # The step's central cost property: every message in the window is replayed
    # on every later turn, so an unbounded window grows the bill forever.
    service, store, _, workspace = build()
    actor = uuid.uuid4()

    turn = service.send_message(workspace, "First", actor)

    for index in range(30):
        service.send_message(workspace, f"Message {index}", actor, turn.conversation.id)

    assert store.history_limits, "the service never read a bounded history"
    assert set(store.history_limits) == {_CONTEXT_MESSAGE_LIMIT}


def test_a_long_conversation_sends_no_more_than_the_window() -> None:
    # Asserted against what the provider actually received, not only against the
    # limit passed to the query -- the two could disagree.
    provider = FakeProvider("openai")
    service, _, _, workspace = build((provider,))
    actor = uuid.uuid4()

    turn = service.send_message(workspace, "First", actor)

    for index in range(30):
        service.send_message(workspace, f"Message {index}", actor, turn.conversation.id)

    # One system instruction plus at most the window of stored turns.
    assert provider.requests_seen[-1] <= _CONTEXT_MESSAGE_LIMIT + 1


def test_a_provider_failure_raises_rather_than_fabricating_a_reply() -> None:
    # CLAUDE.md §15: no canned apology stored as though the model said it.
    service, store, _, workspace = build(
        (FakeProvider("openai", fail_with=ProviderUnavailableError("upstream is down", "openai")),)
    )

    with pytest.raises(AllProvidersFailedError):
        service.send_message(workspace, "Are you there?", uuid.uuid4())

    assert all(message.role != "assistant" for message in store.messages)


def test_a_failed_turn_still_keeps_the_users_question() -> None:
    # A provider outage costs the user their answer; it must not also discard
    # what they typed.
    service, store, _, workspace = build(
        (FakeProvider("openai", fail_with=ProviderUnavailableError("upstream is down", "openai")),)
    )

    with pytest.raises(AllProvidersFailedError):
        service.send_message(workspace, "Remember this", uuid.uuid4())

    assert [message.content for message in store.messages] == ["Remember this"]


def test_a_workspace_with_no_key_fails_honestly() -> None:
    service, store, _, workspace = build(configure_key=False)

    with pytest.raises(NoProviderAvailableError):
        service.send_message(workspace, "Hello", uuid.uuid4())

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

    turn = service.send_message(workspace, "Hi", uuid.uuid4(), chosen)

    assert turn.conversation.id == chosen
    assert store.conversations[chosen].workspace_id == workspace


def test_retrying_with_the_same_id_continues_one_conversation() -> None:
    # The property the fix exists for, asserted end to end at the service level:
    # two sends carrying one id produce one conversation, not two.
    service, store, _, workspace = build()
    chosen = uuid.uuid4()
    actor = uuid.uuid4()

    service.send_message(workspace, "Hi", actor, chosen)
    service.send_message(workspace, "Hi", actor, chosen)

    assert len(store.conversations) == 1

    # And the title still comes from the first message rather than being
    # rewritten by the retry -- the conversation was continued, not recreated.
    assert store.conversations[chosen].title == "Hi"


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
        service.send_message(workspace, "Hi", uuid.uuid4(), theirs.id)

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

    service.send_message(workspace, "What next?", uuid.uuid4(), project_id=project_id)

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

    turn = service.send_message(workspace, "Still here?", uuid.uuid4(), project_id=uuid.uuid4())

    assert turn.assistant_message.content


def test_a_conversation_without_a_project_sends_no_project_context() -> None:
    provider = FakeProvider("openai")
    service, _, _, workspace = build((provider,))

    service.send_message(workspace, "Hello", uuid.uuid4())

    sent = provider.last_request
    assert sent is not None
    system_messages = [m for m in sent.messages if m.role == Role.SYSTEM]
    assert len(system_messages) == 1


def test_deleting_a_conversation_reports_whether_it_existed() -> None:
    service, store, _, workspace = build()
    turn = service.send_message(workspace, "Hello", uuid.uuid4())

    assert service.delete_conversation(workspace, turn.conversation.id) is True
    assert service.delete_conversation(workspace, turn.conversation.id) is False


def test_a_conversations_project_is_fixed_after_creation() -> None:
    # Changing it mid-conversation would silently rewrite what earlier turns
    # were answered against.
    service, _, projects, workspace = build()
    first = uuid.uuid4()
    projects.projects[first] = StubProject(workspace, "First", None)

    turn = service.send_message(workspace, "Hello", uuid.uuid4(), project_id=first)
    again = service.send_message(
        workspace, "Again", uuid.uuid4(), turn.conversation.id, project_id=uuid.uuid4()
    )

    assert again.conversation.project_id == first


def test_the_transcript_is_unbounded_while_the_context_is_not() -> None:
    # The window bounds spend, not the user's access to their own history.
    service, _, _, workspace = build()
    actor = uuid.uuid4()
    turn = service.send_message(workspace, "First", actor)

    for index in range(25):
        service.send_message(workspace, f"Message {index}", actor, turn.conversation.id)

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
