"""Chat endpoints: conversations, their transcripts, and one turn at a time.

The first HTTP surface where a provider failure reaches a **user** rather than a
workflow run's status column. The rules governing this module:

## 1. No route decides anything

Every handler validates, calls `ChatService`, and renders. Context assembly, the
window bound and the persistence order live in the service, so the non-HTTP
callers later phases bring get the same behaviour (CLAUDE.md §12).

## 2. Errors are raised, never mapped here

`ConversationNotFoundError` reaches the client as 404, `ProviderError` as 502 or
503, and every governance refusal as 402 or 503 -- all through the handler table
in `app.core.errors`. No route here catches any of them.

That matters most for the provider case: catching it to return a friendly empty
reply is exactly the fabricated answer CLAUDE.md §15 forbids, and it would also
persist nothing while *looking* like a completed turn.

## 3. Every live member may chat; the workspace boundary is the gate

`requires(VIEW_WORKSPACE)`, matching `projects`. A conversation is work inside
the workspace, not an administrative setting -- the owner/admin asymmetry that
guards AI keys and budgets does not apply. **No chat-specific permission was
added**, deliberately: the first question a finer model must answer is "may I
read someone else's conversation?", which [[AI Chat]] does not settle, so it is a
decision to raise rather than a detail to invent.

## 4. The message route is rate limited per user, and it is the one that spends

Every other route here reads. `POST /messages` is the only one that reaches a
provider, so it carries the tighter limit -- a bound on *requests* sitting above
the spend ceilings that bound *cost*, which is the CLAUDE.md §15a layering.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import ChatServiceDep, CurrentUserDep, requires
from app.core.permissions import WorkspacePermission, WorkspaceRole
from app.core.user_rate_limit import limit_by_user
from app.repositories.conversations import ChatMessage, Conversation
from app.schemas.chat import (
    CompletionRequestBody,
    ConversationDetailResponse,
    ConversationResponse,
    MessageResponse,
    MessageRole,
    MessageSendRequest,
    PendingTurnResponse,
    TurnResponse,
)
from app.services.chat_service import ConversationNotFoundError

router = APIRouter(prefix="/workspaces/{workspace_id}/chat", tags=["chat"])

#: Admits any live member of the workspace named in the path.
_MemberOfWorkspace = Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))]


def _conversation_response(conversation: Conversation) -> ConversationResponse:
    """Render one conversation."""
    return ConversationResponse(
        id=str(conversation.id),
        workspace_id=str(conversation.workspace_id),
        title=conversation.title,
        project_id=None if conversation.project_id is None else str(conversation.project_id),
        created_by=str(conversation.created_by),
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
        version=conversation.version,
    )


def _message_response(message: ChatMessage) -> MessageResponse:
    """Render one message.

    `workspace_id` is deliberately not carried: the caller already knows it from
    the path they called, and a response repeating it invites a client to trust
    the body over the URL.
    """
    return MessageResponse(
        id=str(message.id),
        conversation_id=str(message.conversation_id),
        # The repository types `role` as `str` because it reads a `text` column.
        # Narrowing here keeps the repository a faithful reflection of the schema;
        # the value came from a row the CHECK constraint already validated.
        role=MessageRole(message.role),
        content=message.content,
        provider=message.provider,
        model=message.model,
        token_count=message.token_count,
        created_at=message.created_at.isoformat(),
    )


def _parse_optional_uuid(value: str | None, field: str) -> uuid.UUID | None:
    """Parse an optional id from a request body, or refuse it as a 422.

    Carried as `str` in the schema and parsed here rather than typed `uuid.UUID`
    directly, so a malformed id is refused with a message naming *which* field
    was wrong -- both ids are optional and a bare "invalid uuid" would not say.
    """
    if value is None:
        return None

    try:
        return uuid.UUID(value)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field} is not a valid identifier",
        ) from error


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    """Parse a required id from a request body, or refuse it as a 422."""
    try:
        return uuid.UUID(value)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field} is not a valid identifier",
        ) from error


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    summary="Every live conversation in a workspace",
)
def list_conversations(
    workspace_id: uuid.UUID,
    chat: ChatServiceDep,
    _role: _MemberOfWorkspace,
) -> list[ConversationResponse]:
    """Return the workspace's conversations, most recently active first.

    Unpaginated, matching `GET /projects` and carrying the same limitation --
    [[API Endpoints]] names that route as where the pagination convention should
    be settled, and settling it here for one endpoint would be a second answer.
    """
    conversations = chat.list_conversations(workspace_id)

    return [_conversation_response(conversation) for conversation in conversations]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="One conversation with its transcript",
)
def read_conversation(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    chat: ChatServiceDep,
    _role: _MemberOfWorkspace,
) -> ConversationDetailResponse:
    """Return one conversation and every message in it, oldest first.

    The full transcript rather than the bounded context window: this is the user
    reading their own conversation, and the window exists to bound *spend*, not
    to hide history from the person who wrote it.
    """
    conversation = chat.get_conversation(workspace_id, conversation_id)

    if conversation is None:
        raise ConversationNotFoundError(
            f"Conversation {conversation_id} was not found in this workspace"
        )

    messages = chat.list_messages(workspace_id, conversation_id)

    return ConversationDetailResponse(
        conversation=_conversation_response(conversation),
        messages=[_message_response(message) for message in messages],
    )


@router.post(
    "/conversations",
    response_model=PendingTurnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store a question, without answering it",
    dependencies=[Depends(limit_by_user("chat-message", limit=20, window_seconds=60))],
)
def start_turn(
    workspace_id: uuid.UUID,
    request: MessageSendRequest,
    user: CurrentUserDep,
    chat: ChatServiceDep,
    _role: _MemberOfWorkspace,
) -> PendingTurnResponse:
    """Persist a question and return the ids needed to answer it.

    **The first of two requests, and the split is the point.**

    A turn used to be one request: persist the question, call the provider,
    persist the reply. Because the whole request runs in one transaction
    (`RequestSessionFactory.authenticated_as`), a provider failure rolled the
    question back with it -- the UI reported "your message was saved" while
    nothing had been. The transaction boundary cannot simply be moved: a commit
    discards `SET LOCAL ROLE`, which would continue the request with RLS off.

    This request makes no network call, so what it stores is durable before any
    provider is contacted. `POST /conversations/{id}/completion` then answers it.

    201 because a question is created. The reply is a separate resource, created
    by a separate request.
    """
    turn = chat.start_turn(
        workspace_id=workspace_id,
        content=request.content,
        actor_id=user.id,
        conversation_id=_parse_optional_uuid(request.conversation_id, "conversation_id"),
        project_id=_parse_optional_uuid(request.project_id, "project_id"),
    )

    return PendingTurnResponse(
        conversation=_conversation_response(turn.conversation),
        user_message=_message_response(turn.user_message),
    )


@router.post(
    "/conversations/{conversation_id}/completion",
    response_model=TurnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Answer a stored question",
    # The only route here that reaches a provider, so the only one with a limit
    # this tight. Generous enough that a person typing never meets it and a
    # script does.
    dependencies=[Depends(limit_by_user("chat-message", limit=20, window_seconds=60))],
)
def complete_turn(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    request: CompletionRequestBody,
    user: CurrentUserDep,
    chat: ChatServiceDep,
    _role: _MemberOfWorkspace,
) -> TurnResponse:
    """Answer a stored question, calling a provider at most once.

    **The second of two requests.** The turn is claimed with a conditional
    UPDATE, committed before the network call, so concurrent completions of the
    same question produce exactly one provider invocation and one charge -- not
    one stored reply after two bills, which is all a unique index would give.

    A provider failure releases the claim and answers 502/503, leaving the
    question stored and the turn immediately retryable. That is the honest
    contract STEP-23 promises, now actually kept.

    409 when the turn is already being answered or has been -- including a turn
    whose process died mid-call, which stays claimed on purpose. Recovering it
    automatically would risk paying twice for one question, so it is surfaced
    rather than retried.
    """
    turn = chat.complete_turn(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        user_message_id=_parse_uuid(request.user_message_id, "user_message_id"),
        actor_id=user.id,
    )

    return TurnResponse(
        conversation=_conversation_response(turn.conversation),
        user_message=_message_response(turn.user_message),
        assistant_message=_message_response(turn.assistant_message),
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
def delete_conversation(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    chat: ChatServiceDep,
    _role: _MemberOfWorkspace,
) -> None:
    """Soft-delete a conversation and, with it, access to its messages.

    Soft, so the row survives with `deleted_at` set -- from the caller's side it
    is gone, which is what `DELETE` means to them. The messages are left
    addressable by their conversation rather than stamped individually: every
    read path filters through a live conversation, so they become unreachable
    together. A workspace *erasure* clears the message rows directly, through
    `MessageStore`.

    404 rather than 204 when nothing was deleted, so a caller learns their id was
    wrong instead of receiving the same answer as a successful delete.
    """
    if not chat.delete_conversation(workspace_id, conversation_id):
        raise ConversationNotFoundError(
            f"Conversation {conversation_id} was not found in this workspace"
        )
