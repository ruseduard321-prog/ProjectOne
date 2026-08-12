"""Give a chat turn durable state, so a provider is invoked at most once.

[[STEP-23 AI Chat End to End]] originally ran a turn as one HTTP request:
persist the question, call the provider, persist the reply. Manual testing found
that a provider failure lost the question entirely -- the request runs inside one
transaction (`RequestSessionFactory.authenticated_as`), so the error rolled back
the conversation and the user's message along with it. The screen said "your
message was saved" while nothing had been.

The transaction boundary cannot simply be moved. `SET LOCAL ROLE` and the
`set_config(..., true)` claim are **discarded by a commit** -- verified against
the live database -- so committing mid-request would drop the RLS identity and
continue as the privileged owner. That is a tenant-isolation breach, and a far
worse defect than the one being fixed.

So the turn is split across two requests, and this migration gives it the
durable state that split requires.

## The claim is a state transition, not a lock

    pending ──claim──> in_progress ──settle──> completed
       ▲                    │
       └───release──────────┘   (ordinary provider failure)

Claiming is a conditional UPDATE:

    UPDATE public.messages
    SET turn_status = 'in_progress', claim_token = %s, claimed_at = now()
    WHERE id = %s AND turn_status = 'pending'
    RETURNING claim_token

PostgreSQL serialises that, so exactly one concurrent caller gets a row back.
**The claim commits before the provider is called**, which is what lets the
network request run with no transaction open and no row locked -- the property
CLAUDE.md §15a's cost governance depends on, since a budget row locked for the
duration of an upstream HTTP call is how one becomes a bottleneck.

Verified with four concurrent callers against real PostgreSQL: one claimed and
invoked, three observed `in_progress` and did not. A unique index alone was
tried first and **rejected**: it deduplicates the stored reply *after* every
caller has already invoked and been charged by the provider. It prevents a
duplicate row, never a duplicate bill.

## What this deliberately does not do

**There is no lease and no automatic recovery**, and that is a decision rather
than an omission. A process that crashes *after* the provider accepted the
request has already incurred the cost; returning the turn to `pending` on a
timer would re-invoke and charge a second time. Exactly-once execution across a
crash is unachievable without provider-side idempotency keys, so this migration
leaves such a turn visibly stuck in `in_progress` rather than silently retrying.

Stuck is honest. Silently double-charging is not. Reconciliation, lease policy
and provider idempotency are a separate ADR-backed step covering every AI
feature, not just chat.

## `reply_to` is defence in depth, not the mechanism

`UNIQUE (reply_to)` is **total**, with no `WHERE deleted_at IS NULL` predicate.
A partial index was tested and permits a second reply once the first is
soft-deleted -- so deleting a reply would license a fresh provider call. A turn
is consumed permanently, whatever later happens to the row it produced.

The claim is what prevents a second invocation. This constraint only catches a
bug in the claim logic, which is exactly what defence in depth is for.

Revision ID: c8f1a3d54e29
Revises: b4e8c02d71fa
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c8f1a3d54e29"
down_revision: str | Sequence[str] | None = "b4e8c02d71fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Added to `messages` rather than a side table: the state belongs to the user
# message it describes, and a separate table would need its own RLS policies,
# its own workspace column and its own join on every read -- machinery for a
# relationship that is strictly one-to-one.
#
# Nullable with no default on purpose. `turn_status` is meaningful only for a
# user message; an assistant reply is not a turn awaiting execution, and a NULL
# says that more honestly than a status value that never changes.
_COLUMNS = """
ALTER TABLE public.messages
    ADD COLUMN turn_status text
        CONSTRAINT ck_messages_turn_status_valid
        CHECK (turn_status IN ('pending', 'in_progress', 'completed')),

    -- Who holds the claim. Rotated on every claim so a stale holder cannot
    -- settle a turn it no longer owns -- every settle names the token it
    -- claimed with, and a release clears it.
    ADD COLUMN claim_token uuid,

    -- When the current claim was taken. Recorded for the operator diagnosing a
    -- stuck turn; nothing in STEP-23 reads it to make a decision, because a
    -- time-based decision is precisely the automatic recovery this step
    -- deliberately excludes.
    ADD COLUMN claimed_at timestamptz,

    -- The user message this reply answers. NULL on a user message.
    ADD COLUMN reply_to uuid,

    -- A message's workspace must match the message it replies to. The same
    -- composite-FK protection the conversation relationship already uses, and
    -- for the same reason: RLS sees one row at a time and cannot check a
    -- relationship between two of them.
    ADD CONSTRAINT fk_messages_reply_to_messages
        FOREIGN KEY (reply_to, workspace_id)
        REFERENCES public.messages (id, workspace_id) ON DELETE RESTRICT,

    -- Only a user message carries turn state; only an assistant message answers
    -- one. Stated as a constraint rather than a convention because both halves
    -- are load-bearing: a user message with a `reply_to` would be a turn
    -- answering another turn, and an assistant message with a `turn_status`
    -- would be claimable.
    ADD CONSTRAINT ck_messages_turn_state_matches_role
        CHECK (
            (role = 'user' AND reply_to IS NULL)
            OR (role = 'assistant' AND turn_status IS NULL AND claim_token IS NULL)
        );
"""

# Required by the composite FK above: PostgreSQL needs a unique constraint on
# exactly the referenced pair. `id` alone is already the primary key, so this
# constrains no data -- the same bookkeeping `conversations` already carries.
_REFERENCED_PAIR = """
ALTER TABLE public.messages
    ADD CONSTRAINT uq_messages_id_workspace_id UNIQUE (id, workspace_id);
"""

# **Total, not partial.** A partial index (`WHERE deleted_at IS NULL`) was tested
# against a real database and allows a second reply once the first is
# soft-deleted -- which would let deleting a reply license a fresh provider call
# and a fresh charge. A turn is consumed permanently.
_UNIQUE_REPLY = """
CREATE UNIQUE INDEX uq_messages_reply_to
    ON public.messages (reply_to)
    WHERE reply_to IS NOT NULL;
"""

# Finding pending work for one conversation, and finding stuck turns during an
# incident. Partial on the states that are actually queried: a `completed` turn
# is read through the transcript, never through this index.
_STATE_INDEX = """
CREATE INDEX ix_messages_turn_status
    ON public.messages (turn_status, claimed_at)
    WHERE turn_status IN ('pending', 'in_progress');
"""

# What `reply_to` may point at, beyond same-workspace.
#
# The composite FK proves co-tenancy and nothing more: it would happily accept a
# reply pointing at a *different conversation's* message, or at another
# assistant reply. Both are expressible only by comparing two rows, which is
# neither an FK nor an RLS policy's job -- so it is a trigger, in the same shape
# as `app_messages_immutable`.
_ELIGIBILITY = """
CREATE OR REPLACE FUNCTION public.app_messages_reply_eligible()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    target_role text;
    target_conversation uuid;
BEGIN
    IF NEW.reply_to IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT m.role, m.conversation_id
      INTO target_role, target_conversation
      FROM public.messages m
     WHERE m.id = NEW.reply_to;

    IF target_role IS NULL THEN
        RAISE EXCEPTION 'message % does not exist', NEW.reply_to
            USING ERRCODE = '23503';
    END IF;

    IF target_role <> 'user' THEN
        RAISE EXCEPTION 'a reply may only answer a user message'
            USING ERRCODE = '23514',
                  HINT = 'reply_to must name a message whose role is user.';
    END IF;

    IF target_conversation <> NEW.conversation_id THEN
        RAISE EXCEPTION 'a reply must stay in its own conversation'
            USING ERRCODE = '23514',
                  HINT = 'reply_to must name a message in the same conversation.';
    END IF;

    RETURN NEW;
END;
$$;
"""

# BEFORE INSERT only, and the reason is worth stating because it corrects an
# assumption made while writing this migration.
#
# `app_messages_immutable` (b4e8c02d71fa) was described there as a *whitelist* of
# columns that may change. It is not, quite: it enumerates the nine columns it
# *refuses*, so any column added afterwards is mutable by default -- the exact
# rot that comment claimed to prevent. Verified against the live database: the
# claim UPDATE below runs untouched by that trigger.
#
# For the turn-state columns that is the behaviour required -- a claim must be
# able to move `turn_status` -- so this migration does not change the guard. But
# it does mean `reply_to` would be editable through an ordinary UPDATE, which is
# why the eligibility check runs BEFORE INSERT *and* why `uq_messages_reply_to`
# is total: between them, a turn cannot be re-pointed at a different question or
# freed to be answered twice.
#
# Widening the immutability guard to genuinely whitelist is the right fix and is
# **deliberately not made here**: it would change the semantics of an already-
# applied migration's trigger for every column, which is the follow-up step's
# business, not a side effect of adding turn state.
_ELIGIBILITY_TRIGGER = """
CREATE TRIGGER app_messages_reply_eligible
BEFORE INSERT ON public.messages
FOR EACH ROW
EXECUTE FUNCTION public.app_messages_reply_eligible();
"""

# Every message that already exists is a completed exchange: it was written by
# the single-request flow, which only ever persisted a reply after the provider
# returned. Marking them `completed` keeps the invariant "a user message with no
# turn_status does not exist" true from this revision onward.
_BACKFILL = """
UPDATE public.messages
SET turn_status = 'completed'
WHERE role = 'user' AND turn_status IS NULL;
"""


def upgrade() -> None:
    """Add turn state, reply linkage and their guards."""
    op.execute(_REFERENCED_PAIR)
    op.execute(_COLUMNS)
    op.execute(_UNIQUE_REPLY)
    op.execute(_STATE_INDEX)
    op.execute(_ELIGIBILITY)
    op.execute(_ELIGIBILITY_TRIGGER)
    op.execute(_BACKFILL)


def downgrade() -> None:
    """Remove turn state, returning `messages` to a plain transcript.

    Rolling back discards which turns were pending or in progress. Any turn
    mid-flight at that moment becomes unrecoverable -- there is nowhere left to
    record that it was claimed -- so this is not a routine operation on a
    database serving traffic.
    """
    op.execute("DROP TRIGGER IF EXISTS app_messages_reply_eligible ON public.messages;")
    op.execute("DROP FUNCTION IF EXISTS public.app_messages_reply_eligible();")
    op.execute("DROP INDEX IF EXISTS public.ix_messages_turn_status;")
    op.execute("DROP INDEX IF EXISTS public.uq_messages_reply_to;")
    op.execute(
        "ALTER TABLE public.messages "
        "DROP CONSTRAINT IF EXISTS ck_messages_turn_state_matches_role, "
        "DROP CONSTRAINT IF EXISTS fk_messages_reply_to_messages, "
        "DROP COLUMN IF EXISTS reply_to, "
        "DROP COLUMN IF EXISTS claimed_at, "
        "DROP COLUMN IF EXISTS claim_token, "
        "DROP COLUMN IF EXISTS turn_status;"
    )
    op.execute("ALTER TABLE public.messages DROP CONSTRAINT IF EXISTS uq_messages_id_workspace_id;")
