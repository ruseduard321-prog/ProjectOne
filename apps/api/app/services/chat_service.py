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
from app.repositories.chat_turns import (
    PENDING,
    ChatTurnRepository,
)
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


@dataclass(frozen=True)
class PendingTurn:
    """A stored question awaiting its answer.

    What `start_turn` returns, and what the client needs to ask for a
    completion: the conversation to navigate to, and the user message id that
    identifies this turn for the rest of its life.
    """

    conversation: Conversation
    user_message: ChatMessage


class TurnNotClaimableError(Exception):
    """The turn is already being answered, or has been.

    Raised rather than silently answering again. A second concurrent completion
    must not reach a provider -- that is a duplicate charge, not a duplicate
    row -- and a caller who asked to complete a turn someone else is completing
    deserves to be told, not quietly given someone else's answer as though they
    had caused it.

    **A turn stuck by a crash raises this too**, rather than a distinct error,
    and the reason is that the database cannot tell the two apart: a turn
    abandoned by a dead process and one a live process is answering right now
    are both `in_progress` with a token and a timestamp. Distinguishing them
    needs a lease, and a lease is exactly what STEP-23 excludes -- expiring one
    would return the turn to `pending` and risk re-invoking a provider that has
    already accepted and charged for the request.

    `claimed_at` is recorded for an operator diagnosing the difference by hand.
    Nothing in this step reads it to make a decision; reconciliation belongs to
    the follow-up ADR-backed step.
    """

    public_message = "This message is already being answered"


class ChatService:
    """Holds conversations, assembles their context, and runs one turn at a time."""

    def __init__(
        self,
        conversations: ConversationRepository,
        projects: ProjectRepository,
        ai: AIService,
        turns: ChatTurnRepository,
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
        self._turns = turns

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

    def start_turn(
        self,
        workspace_id: uuid.UUID,
        content: str,
        actor_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> PendingTurn:
        """Persist a question, and nothing else.

        **The first half of a turn, and the reason a turn is split at all.**

        The single-request design persisted the question and then called the
        provider inside one request -- and therefore inside one transaction,
        because `RequestSessionFactory.authenticated_as` wraps the whole request.
        A provider failure rolled the question back with it, so the screen said
        "your message was saved" while nothing had been. Found by manual testing
        rather than review: every unit test asserted against an in-memory fake
        with no transaction semantics, so the assertion passed while the
        behaviour did not.

        This method makes no network call, so it commits cleanly. What it stores
        survives whatever happens next.

        Args:
            workspace_id: The tenant, from the verified request context.
            content: What the user said.
            actor_id: Who said it, for `created_by` and spend attribution.
            conversation_id: The conversation to continue, or the id to start one
                with. None lets the database choose. See `_resolve_conversation`
                for why an unknown id creates rather than refuses.
            project_id: The project a *new* conversation is about. Ignored when
                continuing an existing one, whose project is already fixed.

        Returns:
            The conversation and the stored question. The user message's id is
            the turn key every later completion names.
        """
        conversation = self._resolve_conversation(
            workspace_id, content, actor_id, conversation_id, project_id
        )

        user_message = self._conversations.add_message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            role="user",
            content=content,
            turn_status=PENDING,
        )

        self._conversations.touch(workspace_id, conversation.id)

        return PendingTurn(conversation=conversation, user_message=user_message)

    def complete_turn(
        self,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> ConversationTurn:
        """Answer a stored question, calling the provider at most once.

        **The second half, and where the concurrency control lives.**

        The turn is claimed with a conditional UPDATE before any network call,
        and that claim is committed on its own connection -- so the provider
        request runs with no transaction open and no row locked, while a second
        concurrent caller cannot reach a provider at all.

        A unique index on the reply was tried first and rejected: it prevents a
        duplicate reply *row*, but only after both callers have already invoked
        and been billed. It deduplicates storage, never spend. The index is kept
        as defence in depth, not as the mechanism.

        Raises:
            ConversationNotFoundError: no such conversation or message here.
            TurnNotClaimableError: another caller holds the turn, or it is done.
            ProviderError: the provider failed. The claim is released first, so
                the turn stays retryable.
            GovernanceError: a ceiling refused the call before any provider was
                contacted. Also released.
        """
        conversation = self._conversations.get(workspace_id, conversation_id)

        if conversation is None:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} was not found in this workspace"
            )

        claim = self._turns.claim(workspace_id, user_message_id)

        if claim is None:
            raise self._not_claimable(workspace_id, user_message_id)

        # Everything below runs with the claim committed and no transaction of
        # ours open. A failure must release it, or the turn is stranded in
        # exactly the state this step refuses to recover from automatically.
        try:
            request = CompletionRequest(
                messages=self._context_for(workspace_id, conversation),
                workspace_id=workspace_id,
            )

            response = self._ai.complete(
                workspace_id=workspace_id,
                request=request,
                actor_id=actor_id,
            )
        except Exception:
            # Released rather than left claimed: an ordinary failure must leave
            # the turn retryable. The spend reservation is settled by
            # `AIService`'s own `finally`, so no charge leaks either.
            self._turns.release(workspace_id, claim)
            raise

        assistant_message = self._conversations.add_message(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            role="assistant",
            content=response.content,
            provider=response.provider,
            model=response.model,
            token_count=response.usage.total_tokens,
            reply_to=user_message_id,
        )

        # After the reply is stored, never before: a turn marked complete
        # without one could never be retried and would have no answer.
        self._turns.complete(workspace_id, claim)
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
            user_message=self._user_message(workspace_id, conversation_id, user_message_id),
            assistant_message=assistant_message,
        )

    def _not_claimable(
        self,
        workspace_id: uuid.UUID,
        user_message_id: uuid.UUID,
    ) -> Exception:
        """Choose the honest error for a turn that could not be claimed.

        A turn absent from this workspace is a 404 for the reason
        `ConversationNotFoundError` gives -- absent and hidden must not be
        distinguishable. Anything else is a live or finished turn, and the
        caller is told so rather than being handed someone else's answer as
        though they had caused it.
        """
        status = self._turns.status_of(workspace_id, user_message_id)

        if status is None:
            return ConversationNotFoundError(
                f"Message {user_message_id} was not found in this conversation"
            )

        return TurnNotClaimableError(TurnNotClaimableError.public_message)

    def _user_message(
        self,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
    ) -> ChatMessage:
        """Read back the question this turn answered."""
        for message in self._conversations.list_messages(workspace_id, conversation_id):
            if message.id == user_message_id:
                return message

        raise ConversationNotFoundError(  # pragma: no cover - defensive
            f"Message {user_message_id} was not found in this conversation"
        )

    def _resolve_conversation(
        self,
        workspace_id: uuid.UUID,
        content: str,
        actor_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        project_id: uuid.UUID | None,
    ) -> Conversation:
        """Return the conversation this turn belongs to, creating one if needed.

        Three cases, and the third is what makes a first turn retryable:

        1. **No id** -- start a conversation and let the database name it.
        2. **An id naming a live conversation** -- continue it. Its `project_id`
           is left alone, because earlier turns were answered against it.
        3. **An id naming nothing** -- start a conversation *with that id*.

        Case 3 replaces an earlier `ConversationNotFoundError`, and the reason is
        the failure it was causing. A first turn that failed at the provider left
        the conversation and the user's question persisted under an id the client
        never learned, because the id only ever appeared in a successful
        response. Retrying therefore started a *second* conversation and stored
        the question again. Letting the client choose the id up front makes the
        retry land in the same conversation, which is what the user means by
        "try that again".

        The id is never a way to reach another tenant's conversation: `get` runs
        under RLS, so another workspace's id reads as absent here and the insert
        that follows is refused by the primary key rather than adopting the row.
        That is a `UniqueViolation`, not a silent cross-tenant write, and it is
        asserted rather than assumed.
        """
        if conversation_id is not None:
            conversation = self._conversations.get(workspace_id, conversation_id)

            if conversation is not None:
                return conversation

        return self._conversations.create(
            workspace_id=workspace_id,
            title=_title_from(content),
            project_id=project_id,
            created_by=actor_id,
            conversation_id=conversation_id,
        )

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
