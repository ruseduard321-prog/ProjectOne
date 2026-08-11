"""Request and response contracts for the chat endpoints.

[[STEP-23 AI Chat End to End]] puts ProjectOne's first user-facing AI surface on
the HTTP layer. The properties enforced here rather than in a route body, for the
reason [[STEP-21 Projects UI]] gives -- a schema is the one place a rule cannot
be forgotten by the next endpoint added:

1. **`role` is a closed vocabulary matching the database.** `MessageRole`
   enumerates exactly what `ck_messages_role_valid` permits. This is the rule
   STEP-21 paid for on `assets.kind`, where bounded free text at the edge turned
   a client's malformed request into a 500 carrying a constraint name. A test
   compares this enum against `pg_constraint` in both directions.
2. **`content` is bounded at the edge.** The ceiling matches the column's, so an
   over-long message is a 422 naming the field rather than a `CheckViolation`
   surfacing as a 500. It is also a spend bound: this text is replayed into the
   conversation's context on every later turn.
3. **Every request model forbids extra fields**, as STEP-19 established.

`workspace_id` appears in no request model -- it is always the verified path
parameter `requires(...)` authorized against. Nor does `role`: a client may only
ever send a *user* message, and the assistant role is written by the server from
what a provider actually returned. A body-supplied role would let a caller forge
a reply into their own transcript and have it replayed as though the model had
said it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

#: What a user may say in one message.
#:
#: Stripped before the bound is applied, so a whitespace-only submission is a 422
#: at the edge rather than reaching the `ck_messages_content_not_blank`
#: constraint. The 20000 ceiling mirrors `ck_messages_content_length` exactly.
MessageContent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20000),
]


class MessageRole(StrEnum):
    """Who authored a stored message.

    Two values, mirroring `ck_messages_role_valid`. `system` is absent because a
    system instruction is assembled at call time and never persisted -- see the
    migration's module docstring.
    """

    USER = "user"
    ASSISTANT = "assistant"


class MessageSendRequest(BaseModel):
    """One user message, optionally continuing an existing conversation."""

    model_config = ConfigDict(extra="forbid")

    content: MessageContent

    #: The conversation to continue. Omitted to start a new one.
    #:
    #: A path parameter would force the client to create a conversation before
    #: saying anything, which is a round trip and an empty conversation left
    #: behind whenever the user changes their mind.
    conversation_id: str | None = None

    #: The project a *new* conversation is about.
    #:
    #: Ignored when `conversation_id` is supplied: an existing conversation's
    #: project is fixed, because earlier turns were already answered against it
    #: and changing it would silently rewrite what they meant.
    project_id: str | None = None


class MessageResponse(BaseModel):
    """One stored message."""

    id: str
    conversation_id: str
    role: MessageRole
    content: str

    #: Which provider and model produced this, when one did.
    #:
    #: Carried rather than omitted because a reply served after a fallback came
    #: from a provider the caller did not choose, and a response that does not
    #: say which is one the caller cannot honestly attribute (CLAUDE.md §15).
    #: Null on a user message, which no provider produced.
    provider: str | None
    model: str | None
    token_count: int
    created_at: str


class ConversationResponse(BaseModel):
    """One conversation, without its messages."""

    id: str
    workspace_id: str
    title: str
    project_id: str | None
    created_by: str
    created_at: str
    updated_at: str
    version: int


class ConversationDetailResponse(BaseModel):
    """One conversation together with its full transcript.

    A single response rather than two calls: a client opening a conversation
    always needs both, and splitting them would make the screen render in two
    stages with no benefit.
    """

    conversation: ConversationResponse
    messages: list[MessageResponse]


class TurnResponse(BaseModel):
    """The outcome of one completed exchange.

    Carries the conversation because a turn that *created* one is the only place
    the client learns its id -- without it, starting a conversation would need a
    second request to discover what was made.
    """

    conversation: ConversationResponse
    user_message: MessageResponse
    assistant_message: MessageResponse
