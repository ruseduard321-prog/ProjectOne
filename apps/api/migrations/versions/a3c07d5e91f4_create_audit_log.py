"""Create the audit log for consequential workspace actions.

[[STEP-13]] builds the first mutations worth auditing -- a workspace being
created, a member added or removed, ownership changing hands -- and
[[API Architecture]] has required audit logging since before any of them
existed. Request logging (STEP-12) records that a request happened; it does not
record *who changed what*, which is the question an audit trail exists to answer
(CLAUDE.md §16, §25).

## Why this table breaks two conventions on purpose

[[Table Conventions]] gives every table five standard columns and a soft-delete
default. This table deliberately departs from that, and the departures are the
security property rather than an oversight:

- **No `deleted_at`, and no soft deletion.** An audit record that its own
  subject can remove is not an audit record. CLAUDE.md §16 states this
  outright: audit logs are retained on their own schedule, independent of user
  deletion requests, "because audit trails exist precisely to survive the events
  they record". A workspace erasure (`DELETE /workspaces/{id}/data`) therefore
  does **not** touch this table -- that is a documented legal exception, not a
  gap in the erasure path.
- **No `version`, and no `touch_row` trigger.** Both exist to track
  modification, and these rows are never modified. Attaching a trigger that
  maintains a version counter on an append-only table would imply an update path
  that must not exist.

`created_at` is kept and is the only timestamp: when the action happened.

## Immutability is enforced, not merely intended

Three independent mechanisms, because a rule this important should not rest on
any single one:

1. **No UPDATE policy and no DELETE policy.** RLS denies by default, so neither
   command has any route for `authenticated`.
2. **No UPDATE, DELETE or TRUNCATE grant.** A grant is an independent gate from
   a policy ([[RLS Policy Pattern]]) and TRUNCATE in particular is *not* subject
   to RLS at all -- a role holding it could empty this table regardless of every
   policy on it.
3. **No INSERT policy either.** Writes come exclusively from the privileged
   connection inside `AuditService`. A client that could write its own audit
   rows could forge them, which is worse than having no audit log: a forged
   trail is trusted.

`authenticated` therefore holds **SELECT only**, and the SELECT policy scopes
reads to workspaces the caller belongs to -- an audit log readable across tenant
boundaries would be a cross-tenant disclosure of exactly the actions most worth
keeping private.

## Why `actor_id` is not a foreign key to `users`

Deliberate. `users.id` is `RESTRICT`-referenced elsewhere, and an FK here would
mean either blocking a user's deletion forever or cascading their audit history
away with them. The trail must outlive the account that generated it, so the
actor is recorded as a bare uuid plus a denormalised email captured at write
time. The email is a **point-in-time snapshot**, not a live join: it records the
address the actor had when they acted, which is what an auditor needs.

`workspace_id` *is* a foreign key, with `RESTRICT`, so the workspace row cannot
be hard-deleted out from under its own history.

Revision ID: a3c07d5e91f4
Revises: b8e1d94c50a7
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3c07d5e91f4"
down_revision: str | Sequence[str] | None = "b8e1d94c50a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREATE_TABLE = """
CREATE TABLE public.audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),

    -- The workspace the action happened in. NOT NULL: every auditable action
    -- this step produces is workspace-scoped, and a nullable tenant column on a
    -- tenant-scoped table is a row that no policy can classify.
    workspace_id uuid NOT NULL
        CONSTRAINT fk_audit_log_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    -- Who acted. Not an FK -- see the module docstring.
    actor_id uuid NOT NULL,
    actor_email text,

    -- What they did. `text` with a CHECK rather than an ENUM, per
    -- Table Conventions: adding an action later is one ALTER statement instead
    -- of a type rewrite that locks the table.
    action text NOT NULL
        CONSTRAINT ck_audit_log_action_valid CHECK (action IN (
            'workspace.created',
            'member.added',
            'member.removed',
            'member.left',
            'ownership.transferred'
        )),

    -- Who or what the action was performed on. Null for actions whose target is
    -- the workspace itself (`workspace.created`).
    target_id uuid,

    -- Anything action-specific worth keeping: the role granted, the previous
    -- owner, the workspace name at creation. `jsonb` rather than a wide sparse
    -- table, because the useful detail differs per action and a column per
    -- action would be mostly NULL.
    --
    -- NOT NULL with a default so a reader never has to distinguish "no detail"
    -- from "detail missing".
    detail jsonb NOT NULL DEFAULT '{}'::jsonb
);
"""

# Reads are the only client-reachable operation, and they are tenant-scoped.
#
# `created_at DESC` is the order any audit view wants, and `workspace_id` is in
# every query's WHERE clause via the policy -- so the composite index serves
# both the filter and the sort.
_INDEXES = """
CREATE INDEX ix_audit_log_workspace_id_created_at
    ON public.audit_log (workspace_id, created_at DESC);
"""

_ENABLE_RLS = """
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log FORCE ROW LEVEL SECURITY;
"""

# One policy, SELECT only.
#
# There is deliberately no INSERT, UPDATE or DELETE policy. RLS denies by
# default, so their absence *is* the control -- a reader who finds only one
# policy here should not conclude the others were forgotten.
#
# No `deleted_at IS NULL` filter, because the column does not exist: these rows
# are never deleted.
_SELECT_POLICY = """
CREATE POLICY audit_log_select_same_workspace ON public.audit_log
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));
"""

# Grants are an independent gate from policies (RLS Policy Pattern), so they are
# stated explicitly rather than inherited. SELECT only: no INSERT (writes are
# privileged-connection only), no UPDATE or DELETE (append-only), and crucially
# no TRUNCATE, which bypasses RLS entirely.
#
# Stated rather than assumed even though `c4f21a86b3de` corrected the schema's
# default privileges -- depending on a default for a security property is how
# the next Supabase change silently reopens it.
_GRANTS = """
REVOKE ALL ON public.audit_log FROM anon, authenticated;
GRANT SELECT ON public.audit_log TO authenticated;
"""


def upgrade() -> None:
    """Create the append-only audit log with its RLS policy and grants."""
    op.execute(_CREATE_TABLE)
    op.execute(_INDEXES)
    op.execute(_ENABLE_RLS)
    op.execute(_SELECT_POLICY)
    op.execute(_GRANTS)


def downgrade() -> None:
    """Drop the audit log.

    Written and verified alongside `upgrade()` per Table Conventions. Dropping
    the table removes its policies, indexes and grants with it; they are not
    dropped individually.

    Worth stating plainly: rolling this back **destroys the audit trail**. That
    is acceptable for a migration rollback during development, and is the reason
    a production rollback of this revision is a decision rather than a routine
    operation.
    """
    op.execute("DROP TABLE IF EXISTS public.audit_log;")
