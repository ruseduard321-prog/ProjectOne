"""Create the `conversations` and `messages` tables with their RLS policies.

[[STEP-23]] gives ProjectOne its first table holding **a user's own words**. Every
table before it stored platform machinery, user-created *artifacts* (a project, an
asset) or a record of what the platform did. A conversation is different in kind:
it is what the user said, and [[CLAUDE|CLAUDE.md]] §16's data-ownership and erasure
obligations are at their most literal here. Both tables are registered for erasure
in the same change that creates them, not a later one.

Both follow [[RLS Policy Pattern]] and [[Table Conventions]] without deviation.
Four decisions are specific to this pair.

## The role vocabulary is `user` and `assistant`, and `system` is excluded

`Role` in `app/ai/provider.py` has three members; this constraint permits two.
The omission is deliberate rather than an oversight: a system prompt is **not a
turn in the conversation**, it is instruction assembled at call time by
`ChatService`. Persisting it as a message would mean a stored row that the user
did not write and cannot meaningfully own, appearing in their exported data as
though they had said it -- and it would be replayed back into the next request's
context, so an edit to the prompt would apply to new conversations but not old
ones.

Storing only what the user and the model actually exchanged keeps the export
honest and the prompt a single source of truth in code. The narrowing is asserted
by a test reading `pg_constraint`, in both directions, exactly as
`ck_assets_kind_valid` is -- the STEP-21 defect this repeats the guard against.

## `messages` carries `workspace_id` as well as `conversation_id`

The same denormalization as `assets` and `workflow_step_runs`, and the same hole
it opens: an INSERT naming the caller's *own* workspace while pointing
`conversation_id` at another tenant's conversation satisfies the RLS policy
perfectly, because the policy only ever sees `workspace_id`. RLS structurally
cannot catch it -- the check it would need is a join.

The composite foreign key to `conversations (id, workspace_id)` refuses that row,
failing with `ForeignKeyViolation` rather than an RLS error. That difference is
the point: the constraint is doing work no policy can do.

## `messages` admits exactly one kind of UPDATE: the soft delete

A conversation is a record of what was said. Editing a past message would make
the transcript disagree with what the model actually received -- the context of
every later turn was assembled from the *original* text, so a rewritten history
describes a conversation that never happened.

The first draft expressed that by giving the table **no UPDATE policy at all**.
That was wrong, and a live database said so: erasure is an UPDATE setting
`deleted_at`, it runs over the **tenant** connection (`DataOwnershipService`
takes the request's connection, not a privileged one), and with no policy it
matched zero rows -- a workspace erasure silently leaving every message in place
while reporting success. That is the `provider_credentials` defect STEP-19 paid
for, reached by a different route.

`messages_soft_delete_member` resolves both requirements at once: its `WITH
CHECK` admits only rows that end up soft-deleted, so erasure works and rewriting
`content` is still refused by the policy rather than by convention.
`token_count` is written at INSERT and never revised.

## Neither table filters `deleted_at` in its SELECT policy

Both are soft-deleted, so a SELECT policy filtering `deleted_at IS NULL` would
make the soft delete impossible -- the defect [[STEP-11a]] and [[STEP-19]] each
paid a step for. Liveness is filtered in the queries. See [[RLS Policy Pattern#A
SELECT policy that filters deleted at makes soft deletion impossible]].

Revision ID: a7d24e91f3b6
Revises: f3c82b19d4a7
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7d24e91f3b6"
down_revision: str | Sequence[str] | None = "f3c82b19d4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREATE_CONVERSATIONS = """
CREATE TABLE public.conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    version integer NOT NULL DEFAULT 1,

    workspace_id uuid NOT NULL
        CONSTRAINT fk_conversations_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    -- Shown in the conversation list. Derived from the first user message rather
    -- than asked for up front: a chat that demands a title before the first
    -- question is a form, not a conversation.
    title text NOT NULL
        CONSTRAINT ck_conversations_title_not_blank CHECK (btrim(title) <> '')
        CONSTRAINT ck_conversations_title_length CHECK (char_length(title) <= 200),

    -- The project this conversation is about, when it is about one. Nullable
    -- because a workspace-level chat is legitimate; the composite FK below is
    -- what keeps a non-null value honest.
    --
    -- This is the "active project" half of the context window: `ChatService`
    -- includes the named project's name and description in the assembled
    -- context, which is the whole of STEP-23's project scope.
    project_id uuid,

    -- Who started it. Not an FK, matching `projects.created_by` and
    -- `workflow_runs.triggered_by`: the record should outlive the account.
    created_by uuid NOT NULL,

    -- Exists solely so `messages` can reference the pair. `id` is already
    -- unique, so this constrains no data.
    CONSTRAINT uq_conversations_id_workspace_id UNIQUE (id, workspace_id),

    CONSTRAINT fk_conversations_project_id_projects
        FOREIGN KEY (project_id, workspace_id)
        REFERENCES public.projects (id, workspace_id) ON DELETE RESTRICT
);
"""

_CREATE_MESSAGES = """
CREATE TABLE public.messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    version integer NOT NULL DEFAULT 1,

    workspace_id uuid NOT NULL
        CONSTRAINT fk_messages_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    conversation_id uuid NOT NULL,

    -- Two values, not the three in `Role` -- see the module docstring. A test
    -- reads this constraint and compares against the persisted vocabulary in
    -- both directions, so the pair cannot drift.
    role text NOT NULL
        CONSTRAINT ck_messages_role_valid CHECK (role IN ('user', 'assistant')),

    -- What was actually said. The length ceiling is a cost control as much as a
    -- storage one: this text is replayed into the next request's context, so an
    -- unbounded message is an unbounded prompt (CLAUDE.md §15a).
    content text NOT NULL
        CONSTRAINT ck_messages_content_not_blank CHECK (btrim(content) <> '')
        CONSTRAINT ck_messages_content_length CHECK (char_length(content) <= 20000),

    -- Which provider and model produced an assistant message, so a reply can be
    -- attributed honestly after a fallback (CLAUDE.md §15). Null on a user
    -- message, which no provider produced.
    provider text
        CONSTRAINT ck_messages_provider_length CHECK (char_length(provider) <= 100),
    model text
        CONSTRAINT ck_messages_model_length CHECK (char_length(model) <= 200),

    -- What this message consumed, so a conversation's cost is answerable from
    -- its own history rather than only from the global ledger -- the same
    -- reasoning as `workflow_step_runs.tokens_used`. Zero on a user message.
    token_count integer NOT NULL DEFAULT 0
        CONSTRAINT ck_messages_token_count_non_negative CHECK (token_count >= 0),

    -- A message's workspace must be its conversation's workspace. The composite
    -- FK protection `assets` and `workflow_step_runs` use, for the reason the
    -- module docstring gives: RLS cannot see this relationship at all.
    CONSTRAINT fk_messages_conversation_id_conversations
        FOREIGN KEY (conversation_id, workspace_id)
        REFERENCES public.conversations (id, workspace_id) ON DELETE RESTRICT
);
"""

# Partial on `deleted_at IS NULL` throughout: every query filters liveness (the
# filter is not in the policies), so an index excluding dead rows serves exactly
# the queries that exist.
#
# `ix_messages_conversation_id_created_at` is the one that matters for cost:
# assembling context reads a conversation's messages in order on every single
# turn, so it is the hottest query this step adds.
_INDEXES = """
CREATE INDEX ix_conversations_workspace_id
    ON public.conversations (workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_conversations_project_id
    ON public.conversations (project_id)
    WHERE deleted_at IS NULL AND project_id IS NOT NULL;

CREATE INDEX ix_messages_conversation_id_created_at
    ON public.messages (conversation_id, created_at)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_messages_workspace_id
    ON public.messages (workspace_id)
    WHERE deleted_at IS NULL;
"""

_ENABLE_RLS = """
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages FORCE ROW LEVEL SECURITY;
"""

# Per-command policies, never one FOR ALL.
#
# **No `deleted_at IS NULL` in either SELECT policy** -- see the module docstring.
#
# Any live member may read and write, matching `projects` and `workflow_runs`: a
# conversation is work done inside the workspace. **`messages` has no UPDATE
# policy at all** -- a transcript is not editable, and erasure runs on the
# privileged path which these policies do not govern. `conversations` keeps its
# UPDATE policy because the title and `updated_at` legitimately change, and
# because deleting a conversation is an UPDATE setting `deleted_at`.
_POLICIES = """
CREATE POLICY conversations_select_same_workspace ON public.conversations
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY conversations_insert_member ON public.conversations
FOR INSERT TO authenticated
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY conversations_update_member ON public.conversations
FOR UPDATE TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY messages_select_same_workspace ON public.messages
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY messages_insert_member ON public.messages
FOR INSERT TO authenticated
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

-- Scoped to the soft delete, and nothing else.
--
-- The first draft of this migration gave `messages` **no** UPDATE policy at all,
-- reasoning that a transcript must be immutable. That was correct about intent
-- and wrong about consequence: erasure runs an UPDATE over the *tenant*
-- connection, and with no policy it matched zero rows -- so a workspace erasure
-- silently left every message in place while reporting success. Found by running
-- it against a real database, not by review; it is the `provider_credentials`
-- defect STEP-19 paid for, arriving by a different route.
--
-- `WITH CHECK (deleted_at IS NOT NULL)` is what keeps immutability real. The
-- only UPDATE this admits is one whose resulting row is soft-deleted, so an
-- attempt to rewrite `content` is still refused by the policy rather than by
-- convention. Erasure is permitted; editing history is not.
CREATE POLICY messages_soft_delete_member ON public.messages
FOR UPDATE TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces())
    AND deleted_at IS NOT NULL
);
"""

# Stated explicitly rather than inherited from Supabase's corrected defaults.
# No DELETE (soft deletion only) and no TRUNCATE (not subject to RLS at all).
#
# `messages` holds the UPDATE grant because erasure needs it -- a soft delete is
# an UPDATE, and it runs over the tenant connection. The *policy* is what bounds
# what that grant can do: `messages_soft_delete_member` admits only an update
# whose row ends up soft-deleted, so immutability survives.
#
# Grant and policy are both required and neither is sufficient. Withholding the
# grant, or omitting the policy, produces the same silent zero-row erase -- the
# second of which this migration actually shipped in its first draft, found by
# running it rather than reviewing it. A test asserts both halves: a member
# cannot edit a message, and erasure still clears one.
_GRANTS = """
REVOKE ALL ON public.conversations FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.conversations TO authenticated;

REVOKE ALL ON public.messages FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.messages TO authenticated;
"""

_TRIGGERS = """
CREATE TRIGGER trg_conversations_touch_row
BEFORE UPDATE ON public.conversations
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();

CREATE TRIGGER trg_messages_touch_row
BEFORE UPDATE ON public.messages
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();
"""


def upgrade() -> None:
    """Create both tables with their RLS policies, grants, indexes and triggers."""
    op.execute(_CREATE_CONVERSATIONS)
    op.execute(_CREATE_MESSAGES)
    op.execute(_INDEXES)
    op.execute(_ENABLE_RLS)
    op.execute(_POLICIES)
    op.execute(_GRANTS)
    op.execute(_TRIGGERS)


def downgrade() -> None:
    """Drop both tables.

    Dropping a table removes its policies, indexes, grants and triggers with it.

    `messages` first: it holds a foreign key to `conversations`, and dropping the
    referenced table while a dependant survives is refused.

    Rolling this back **destroys every conversation in every workspace** -- and
    unlike a workflow run, this is the users' own words rather than a record of
    platform activity. A production rollback of this revision is data loss of the
    most direct kind, not a routine operation.
    """
    op.execute("DROP TABLE IF EXISTS public.messages;")
    op.execute("DROP TABLE IF EXISTS public.conversations;")
