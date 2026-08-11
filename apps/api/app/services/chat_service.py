"""Conversation memory, context assembly, and the one AI call a turn makes.

This is the business logic of [[AI Chat]]: what a conversation is, what the model
is allowed to see, and what is persisted afterwards. It holds no HTTP types and
returns none, so it is testable without the web framework around it
(CLAUDE.md §12).

## The context window is the cost control

`_CONTEXT_MESSAGE_LIMIT` bounds how much history is replayed into each call.
Every message inside that window is re-sent on **every subsequent turn**, so an
unbounded window does not cost more once -- it costs more forever, growing with
the conversation. That is a CLAUDE.md §15a failure before it is a quality one,
which is why the bound lives here rather than being left to the provider's own
context limit to enforce by truncation.

The bound is applied in SQL (`history_for_context`), not by slicing in Python.

## What the model sees, and what it does not

Assembled fresh on every turn, in this order:

1. A system instruction, built in code and never persisted (see the migration's
   note on the role vocabulary).
2. The active project's name and description, when the conversation names one.
   This is the whole of STEP-23's project context -- assets, other conversations
   and the four other memory scopes are explicitly out of scope.
3. The last `_CONTEXT_MESSAGE_LIMIT` messages, oldest first.

## Both turns are persisted, and the user's first

The user's message is written before the provider is called, so a failed call
leaves the question in the transcript rather than discarding it. A user whose
provider is down should not also lose what they typed.

The reply is persisted only when one genuinely arrived. There is no fallback
text, no canned apology stored as though the model said it -- CLAUDE.md §15
forbids exactly that, and an error is raised for the route to translate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.ai.provider import CompletionRequest, Message, Role
from app.core.logging import get_logger, log_context
from app.repositories.conversations import (
    ChatMessage,
    Conversation,
    ConversationRepository,
)
from app.repositories.projects import ProjectRepository
from app.services.ai_service import AIService

logger = get_logger(__name__)

#: How many past messages are replayed into a completion.
#:
#: Twenty is ten exchanges -- enough for a conversation to hold its thread, and
#: small enough that the prompt cost of the twenty-first turn equals the
#: eleventh rather than growing forever. A larger window is a spend decision, so
#: it belongs in a constant with this reasoning next to it rather than inline at
#: the call site.
_CONTEXT_MESSAGE_LIMIT = 20

#: Longest title derived from a first message, in characters.
#:
#: Comfortably under the column's 200-character ceiling so truncation happens
#: here, where it can end on a word, rather than at the database, where it would
#: be a constraint violation.
_TITLE_MAX_LENGTH = 60

#: What the model is told it is. Versioned with this module, never persisted.
_SYSTEM_INSTRUCTION = (
    "You are the AI assistant inside ProjectOne, a platform for content "
    "businesses. Answer clearly and concisely. If you are uncertain or lack the "
    "information to answer, say so plainly rather than guessing."
)

#: Roles a stored message may carry. Mirrors `ck_messages_role_valid` exactly.
#:
#: The database constrains this set, so the outermost schema enumerates the same
#: set -- the rule STEP-21 paid for on `assets.kind`. A test compares this
#: against `pg_constraint` in both directions.
STORED_ROLES: tuple[str, ...] = ("user", "assistant")


@dataclass(frozen=True)
class ConversationTurn:
    """One completed exchange: what was asked, and what answered it."""

    conversation: Conversation
    user_message: ChatMessage
    assistant_message: ChatMessage


class ChatService:
    """Holds conversations, assembles their context, and runs one turn at a time."""

    def __init__(
        self,
        conversations: ConversationRepository,
        projects: ProjectRepository,
        ai: AIService,
    ) -> None:
        """Wire the transcript store, the project store and the governed AI path.

        `ai` is `AIService` rather than `AIRouter`, and that is the security
        property: `AIService.complete` is the only sanctioned path to a provider
        and applies every CLAUDE.md §15a control before the call. Taking the
        router here would be a second path that spends without a ceiling --
        `test_no_ai_call_path_bypasses_governance` asserts no such path exists.
        """
        self._conversations = conversations
        self._projects = projects
        self._ai = ai

    def list_conversations(self, workspace_id: uuid.UUID) -> tuple[Conversation, ...]:
        """Return every live conversation in a workspace, most recently active first."""
        return self._conversations.list_for_workspace(workspace_id)

    def get_conversation(
        self, workspace_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> Conversation | None:
        """Return one live conversation, or None when absent or hidden by RLS."""
        return self._conversations.get(workspace_id, conversation_id)

    def list_messages(
        self, workspace_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> tuple[ChatMessage, ...]:
        """Return a conversation's full transcript, oldest first.

        Unbounded deliberately, unlike `_context_for`: this is the user reading
        their own conversation, which costs a query rather than a provider call.
        The bound exists to limit *spend*, not to hide history from its author.
        """
        return self._conversations.list_messages(workspace_id, conversation_id)

    def delete_conversation(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
        """Soft-delete one conversation.

        Returns:
            True when a live row was affected, False when there was none.
        """
        return self._conversations.soft_delete(workspace_id, conversation_id)

    def send_message(
        self,
        workspace_id: uuid.UUID,
        content: str,
        actor_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> ConversationTurn:
        """Run one turn: persist the question, call the model, persist the reply.

        Args:
            workspace_id: The tenant, from the verified request context.
            content: What the user said.
            actor_id: Who said it, for `created_by` and spend attribution.
            conversation_id: The conversation to continue. None starts a new one.
            project_id: The project a *new* conversation is about. Ignored when
                continuing an existing one, whose project is already fixed --
                changing it mid-conversation would silently rewrite what earlier
                turns were answered against.

        Returns:
            The conversation and both messages of the completed turn.

        Raises:
            ConversationNotFoundError: `conversation_id` names no conversation
                this caller can see.
            ProviderError: The provider failed, or none was available. Raised
                rather than answered with a fabricated reply (CLAUDE.md §15).
            GovernanceError: A spend ceiling, breaker or shutdown refused the
                call before any provider was contacted.
        """
        conversation = self._resolve_conversation(
            workspace_id, content, actor_id, conversation_id, project_id
        )

        # Persisted before the call, so a provider failure does not also discard
        # what the user typed. See the module docstring.
        user_message = self._conversations.add_message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            role="user",
            content=content,
        )

        request = CompletionRequest(
            messages=self._context_for(workspace_id, conversation),
            workspace_id=workspace_id,
        )

        # No try/except: a failure must reach the route, which translates it into
        # an honest status. Catching it here to store a placeholder reply would
        # be the fabricated answer CLAUDE.md §15 forbids -- and the user's
        # message is already safely persisted above.
        response = self._ai.complete(
            workspace_id=workspace_id,
            request=request,
            actor_id=actor_id,
        )

        assistant_message = self._conversations.add_message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            role="assistant",
            content=response.content,
            provider=response.provider,
            model=response.model,
            token_count=response.usage.total_tokens,
        )

        # So the conversation list orders by real activity. Explicit rather than
        # trigger-driven -- see `ConversationRepository.touch`.
        self._conversations.touch(workspace_id, conversation.id)

        logger.info(
            log_context(
                event="chat_turn_completed",
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                provider=response.provider,
                tokens=response.usage.total_tokens,
                served_after_fallback=response.served_after_fallback,
            )
        )

        return ConversationTurn(
            conversation=conversation,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    def _resolve_conversation(
        self,
        workspace_id: uuid.UUID,
        content: str,
        actor_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        project_id: uuid.UUID | None,
    ) -> Conversation:
        """Return the conversation this turn belongs to, creating one if needed."""
        if conversation_id is None:
            return self._conversations.create(
                workspace_id=workspace_id,
                title=_title_from(content),
                project_id=project_id,
                created_by=actor_id,
            )

        conversation = self._conversations.get(workspace_id, conversation_id)

        if conversation is None:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} was not found in this workspace"
            )

        return conversation

    def _context_for(
        self, workspace_id: uuid.UUID, conversation: Conversation
    ) -> tuple[Message, ...]:
        """Assemble what the model sees for this turn.

        Bounded by `_CONTEXT_MESSAGE_LIMIT`, which is the cost control the module
        docstring describes. The history read here already includes the user's
        message for this turn, because it was persisted first.
        """
        messages: list[Message] = [Message(role=Role.SYSTEM, content=_SYSTEM_INSTRUCTION)]

        project_context = self._project_context(workspace_id, conversation.project_id)

        if project_context is not None:
            messages.append(Message(role=Role.SYSTEM, content=project_context))

        history = self._conversations.history_for_context(
            workspace_id, conversation.id, _CONTEXT_MESSAGE_LIMIT
        )

        for stored in history:
            # The stored vocabulary is a strict subset of `Role`, so this is
            # total rather than defensive -- `ck_messages_role_valid` permits
            # only the two values, and `STORED_ROLES` mirrors it.
            messages.append(Message(role=Role(stored.role), content=stored.content))

        return tuple(messages)

    def _project_context(self, workspace_id: uuid.UUID, project_id: uuid.UUID | None) -> str | None:
        """Describe the active project, or None when the conversation names none.

        Reads through `ProjectRepository` on the same tenant connection, so a
        conversation whose project has since been deleted simply contributes no
        project context rather than failing the turn.
        """
        if project_id is None:
            return None

        project = self._projects.get(workspace_id, project_id)

        if project is None:
            return None

        description = project.description or "No description."

        return (
            "The user is working on a project in this workspace.\n"
            f"Project name: {project.name}\n"
            f"Project description: {description}"
        )


class ConversationNotFoundError(Exception):
    """No conversation with that id is visible to this caller.

    Absent and hidden-by-RLS are deliberately the same error, so a conversation
    id cannot be used to probe whether one exists in another workspace -- the
    same non-oracle property `ProjectNotFoundError` carries, and answered with
    the same 404.
    """

    public_message = "Conversation not found"


def _title_from(content: str) -> str:
    """Derive a conversation title from its first message.

    Truncates on a word boundary where one is available, so a cut title reads as
    a phrase rather than a severed word. The ellipsis marks it as shortened
    rather than as the user's complete sentence.
    """
    collapsed = " ".join(content.split())

    if len(collapsed) <= _TITLE_MAX_LENGTH:
        return collapsed

    truncated = collapsed[:_TITLE_MAX_LENGTH]
    boundary = truncated.rfind(" ")

    # Only honour a boundary that is not near the very start, otherwise a first
    # "word" longer than the limit would truncate to almost nothing.
    if boundary > _TITLE_MAX_LENGTH // 2:
        truncated = truncated[:boundary]

    return f"{truncated.rstrip()}…"
