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


class TurnStatus(StrEnum):
    """Where a question is in being answered.

    Three values, mirroring `ck_messages_turn_status_valid` exactly -- the same
    closed-vocabulary rule `MessageRole` follows, and for the same reason: the
    database constrains this set, so the outermost schema enumerates the same
    set rather than passing bounded free text to the client.

    Only a *user* message carries one. An assistant reply is not a turn awaiting
    execution, so its status is null -- `ck_messages_turn_state_matches_role`
    enforces that pairing in the schema itself.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class MessageSendRequest(BaseModel):
    """One user message, optionally continuing an existing conversation."""

    model_config = ConfigDict(extra="forbid")

    content: MessageContent

    #: The conversation this message belongs to. Omitted to let the server pick.
    #:
    #: A path parameter would force the client to create a conversation before
    #: saying anything, which is a round trip and an empty conversation left
    #: behind whenever the user changes their mind.
    #:
    #: **A client may name an id that does not exist yet**, and the conversation
    #: is created with it. That is what makes a first turn recoverable: without
    #: it, the id of a new conversation exists only inside a successful response,
    #: so a provider failure on the first message saves the question to a
    #: conversation the client can never name again -- and the retry starts a
    #: second one, duplicating the question. Choosing the id up front makes the
    #: retry continue the same conversation instead.
    #:
    #: This is safe because the id is only ever *created* or *matched within the
    #: caller's own workspace*: an id belonging to another tenant is invisible to
    #: the caller's RLS, so it is treated as new and refused by the primary key
    #: rather than adopted. Asserted by
    #: `test_a_client_supplied_id_cannot_adopt_another_tenants_conversation`.
    conversation_id: str | None = None

    #: The project a *new* conversation is about.
    #:
    #: Ignored when `conversation_id` is supplied: an existing conversation's
    #: project is fixed, because earlier turns were already answered against it
    #: and changing it would silently rewrite what they meant.
    project_id: str | None = None


class CompletionRequestBody(BaseModel):
    """Which stored question to answer.

    The turn key is the *user message* id, not the conversation id: a
    conversation holds many turns, and naming the conversation would make a
    second question in the same conversation look like a retry of the first.
    """

    model_config = ConfigDict(extra="forbid")

    user_message_id: str


class PendingTurnResponse(BaseModel):
    """A stored question awaiting its answer.

    What `POST /chat/conversations` returns. The client needs both ids: the
    conversation to navigate to, and the message id that names this turn for
    the completion call that follows.
    """

    conversation: ConversationResponse
    user_message: MessageResponse


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

    #: Where this question is in being answered, or null on a reply.
    #:
    #: **Carried because a question the client cannot see is unanswered is a
    #: question nothing will ever answer.** STEP-23 stored `turn_status` from the
    #: start but stopped it at the repository, so a turn whose provider call
    #: failed sat `pending` in the database while the transcript rendered it
    #: identically to an answered one. Manual testing found three such rows
    #: accumulated with no way to reach them -- the turn was retryable by
    #: contract and unreachable in practice.
    #:
    #: `pending` means claimable: no provider holds it, and the completion
    #: endpoint will answer it. `in_progress` means one is in flight, or a
    #: process died holding the claim -- the two are indistinguishable without a
    #: lease, which STEP-23 excludes. `completed` means a reply exists.
    turn_status: TurnStatus | None


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
