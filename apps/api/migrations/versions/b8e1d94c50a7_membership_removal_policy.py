"""Make membership removal possible, and govern it by the owner's rules.

[[STEP-11]] found that soft-deleting a `workspace_members` row was impossible
for **every** role, owner included. This migration fixes that and encodes the
removal rules the project owner supplied on 2026-08-01:

1. The last owner may never leave or be removed.
2. An owner may remove admins and members.
3. An owner may transfer ownership before leaving.
4. An admin may remove members only.
5. A member may only leave the workspace themselves.

## Why removal was impossible, and what changes

`workspace_members_select_same_workspace` filtered `deleted_at IS NULL`. An
`UPDATE` that sets `deleted_at` produces a row the SELECT policy no longer
matches, and PostgreSQL rejects it with *"new row violates row-level security
policy"*. Reproduced against a live database during STEP-11 in all three
directions -- a member erasing their own row, a member erasing another's, and an
owner erasing a member's -- and confirmed by observing the update succeed once
that filter was lifted.

**The filter moves out of the policy and into the queries.** This is the
narrowest fix available and it is worth being precise about why it is safe:

- **A policy answers "whose rows may this caller touch".** That is a *tenant*
  question, and `deleted_at` has nothing to do with it.
- **A query answers "which of those rows do I want".** Excluding removed members
  from a listing is a query concern, and it always was -- the policy was doing
  it as a convenience.

The tenant predicate is untouched: `workspace_id IN (SELECT
public.app_current_user_workspaces())`, and that helper still filters
`deleted_at IS NULL` on the *caller's own* membership. A removed member still
loses access to everything, immediately, because the helper stops returning the
workspace for them. That property is what STEP-09's isolation tests assert and
it is deliberately not weakened here.

> **What genuinely widens:** a live member can now SELECT the soft-deleted
> membership rows of their own workspace. That is a list of who used to be in a
> workspace you are in -- not another tenant's data, and information a member
> list showing "removed" states needs anyway. Every application query that must
> exclude them says so explicitly, and
> `test_removed_members_are_excluded_from_listings` guards that they do.

## Rules 2, 4 and 5: ranked removal rights

Removal is strictly ranked -- **owner > admin > member** -- which rule 4 states
by omission and this migration states outright:

| Actor | May soft-delete |
|---|---|
| `owner` | any `admin` or `member` row, and their own once another owner exists |
| `admin` | `member` rows only -- never another admin, never an owner |
| `member` | their own row only |

`app_workspace_role()` returns the caller's role in one workspace, so a policy
can compare the actor's rank against the target row's. It is a third SECURITY
DEFINER function and carries the same containment measures as its two siblings,
for the same reasons -- see the comment above it.

## Rule 1: a trigger, not a policy

**The last-owner rule cannot be an RLS predicate.** It depends on how many live
owners remain after the statement, which means counting rows in
`workspace_members` from inside a policy on `workspace_members` -- the recursion
STEP-09's helper function exists to break, and a `SECURITY DEFINER` count would
be evaluated per-row against a table the statement is still modifying.

A constraint trigger is the right instrument: it runs **after** the statement,
sees the final state, and raises. `trg_workspace_members_protect_last_owner`
denies both routes to an ownerless workspace:

- **Soft-deleting the last owner** (leaving, or being removed).
- **Demoting the last owner** to `admin` or `member` -- the same hole reached by
  a different statement, and the one that is easy to forget.

It is `DEFERRABLE INITIALLY IMMEDIATE`, which is what makes rule 3 work:
ownership transfer can promote the successor and demote the departing owner in
either order within one transaction, deferring the check to commit if it needs
to. Without deferrability, transfer would depend on statement ordering -- a
correctness trap disguised as a performance detail.

Revision ID: b8e1d94c50a7
Revises: 9f4d2c7a1b83
Create Date: 2026-08-01 18:40:12.663104

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8e1d94c50a7"
down_revision: str | Sequence[str] | None = "9f4d2c7a1b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The caller's role in one workspace, for policies that must compare the actor's
# rank against a target row's.
#
# Third SECURITY DEFINER function in this schema, and it repeats every
# containment measure of the first two because each answers a distinct threat
# (RLS Policy Pattern):
#
# - **Identity is never a parameter.** It comes from `auth.uid()` internally, so
#   a caller can only ever ask about themselves. The `workspace_id` parameter
#   names *which workspace*, never *whose access* -- the same distinction that
#   makes `app_current_user_workspaces_as(text[])` safe.
# - **`SET search_path = ''`** with schema-qualified names, or a caller able to
#   create objects could shadow `workspace_members` and have this read their
#   table with the owner's rights.
# - **`STABLE`** -- read-only, cacheable within a statement.
# - **EXECUTE revoked from PUBLIC *and* from `anon` and `service_role` by
#   name.** Supabase's default privileges grant EXECUTE to those roles by name
#   at creation time, and a revoke from PUBLIC does not remove a grant a named
#   role holds explicitly.
# - **Returns one text value about the caller** -- never a row, never another
#   user's data.
_ROLE_IN_FUNCTION = """
CREATE OR REPLACE FUNCTION public.app_workspace_role(target_workspace uuid)
RETURNS text
LANGUAGE sql
STABLE
STRICT
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT wm.role
    FROM public.workspace_members wm
    WHERE wm.user_id = auth.uid()
      AND wm.workspace_id = target_workspace
      AND wm.deleted_at IS NULL
$$;
"""

_ROLE_IN_GRANTS = """
REVOKE ALL ON FUNCTION public.app_workspace_role(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_workspace_role(uuid) FROM anon;
REVOKE ALL ON FUNCTION public.app_workspace_role(uuid) FROM service_role;
GRANT EXECUTE ON FUNCTION public.app_workspace_role(uuid) TO authenticated;
"""

# Rule 1, as a constraint trigger.
#
# AFTER, so it sees the statement's final state rather than a half-applied one.
# Row-level rather than statement-level because it needs OLD/NEW to know which
# workspace to count, and it only fires on the two transitions that can produce
# an ownerless workspace.
#
# `SET search_path = ''` for the same escalation reason as the functions above:
# a trigger function runs with the table owner's rights.
_LAST_OWNER_GUARD = """
CREATE OR REPLACE FUNCTION public.app_protect_last_owner()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    remaining integer;
BEGIN
    -- Only two transitions can remove an owner: soft-deleting an owner's row,
    -- or demoting one. Anything else cannot produce an ownerless workspace, and
    -- counting on every membership write would be pure overhead.
    IF OLD.role <> 'owner' THEN
        RETURN NULL;
    END IF;

    IF NEW.deleted_at IS NULL AND NEW.role = 'owner' THEN
        RETURN NULL;
    END IF;

    SELECT count(*) INTO remaining
    FROM public.workspace_members wm
    WHERE wm.workspace_id = OLD.workspace_id
      AND wm.role = 'owner'
      AND wm.deleted_at IS NULL;

    IF remaining = 0 THEN
        -- A dedicated SQLSTATE so the service layer can translate this into a
        -- specific, actionable message ("transfer ownership first") rather than
        -- a generic failure. Chosen from the user-defined 'P0001' family's
        -- neighbours in class 23 (integrity constraint violation), which is what
        -- this genuinely is.
        RAISE EXCEPTION 'workspace % would be left without an owner', OLD.workspace_id
            USING ERRCODE = '23514',
                  HINT = 'Transfer ownership to another member before leaving.';
    END IF;

    RETURN NULL;
END;
$$;
"""

# DEFERRABLE INITIALLY IMMEDIATE is what makes ownership transfer work in either
# statement order within one transaction -- promote-then-demote, or
# demote-then-promote. Without it the rule would silently depend on the caller
# writing their two statements the right way round.
_LAST_OWNER_TRIGGER = """
CREATE CONSTRAINT TRIGGER trg_workspace_members_protect_last_owner
AFTER UPDATE ON public.workspace_members
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW
EXECUTE FUNCTION public.app_protect_last_owner();
"""

# The tenant predicate, unchanged from STEP-09. `deleted_at IS NULL` is gone --
# see the module docstring for why that is a query concern, not a policy one.
_SELECT_POLICY = """
CREATE POLICY workspace_members_select_same_workspace ON public.workspace_members
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));
"""

# Rules 2, 4 and 5.
#
# USING decides which rows may be touched; WITH CHECK decides what they may
# become. Both are needed and they say different things here:
#
# - **USING** ranks the actor against the target. An owner reaches admins and
#   members; an admin reaches members only; anyone reaches their own row.
# - **WITH CHECK** stops the ranked permission being used to *promote*. Without
#   it, an admin permitted to edit a member's row could set that row's role to
#   `owner` -- privilege escalation through a legitimate removal right.
#
# The own-row branch still omits a membership re-test, for the reason STEP-11
# established: WITH CHECK evaluates the post-update row, and a membership helper
# filtering `deleted_at IS NULL` would reject the very soft delete this exists to
# permit.
_UPDATE_POLICY = """
CREATE POLICY workspace_members_update_privileged ON public.workspace_members
FOR UPDATE TO authenticated
USING (
    workspace_id IN (SELECT public.app_current_user_workspaces())
    AND (
        -- Rule 2: an owner reaches any admin or member row, plus their own.
        (
            public.app_workspace_role(workspace_id) = 'owner'
            AND (role <> 'owner' OR user_id = auth.uid())
        )
        -- Rule 4: an admin reaches member rows only, plus their own.
        OR (
            public.app_workspace_role(workspace_id) = 'admin'
            AND (role = 'member' OR user_id = auth.uid())
        )
        -- Rule 5: anyone reaches their own row.
        OR user_id = auth.uid()
    )
)
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces())
    AND (
        -- Only an owner may create another owner. This is what makes ownership
        -- transfer an owner-only act (rule 3) rather than something an admin
        -- can arrange for themselves.
        public.app_workspace_role(workspace_id) = 'owner'
        OR (
            public.app_workspace_role(workspace_id) = 'admin'
            AND role IN ('admin', 'member')
        )
        -- A member may write their own row but never change what it grants them.
        OR (user_id = auth.uid() AND role = 'member')
    )
);
"""


def upgrade() -> None:
    """Unblock removal and govern it by the owner's rules."""
    op.execute(_ROLE_IN_FUNCTION)
    op.execute(_ROLE_IN_GRANTS)

    # Dropped before recreation: two permissive policies for the same command
    # are OR-ed together, so leaving the old one in place would keep granting
    # exactly what this migration re-scopes.
    op.execute(
        "DROP POLICY IF EXISTS workspace_members_select_same_workspace ON public.workspace_members;"
    )
    op.execute(_SELECT_POLICY)

    op.execute(
        "DROP POLICY IF EXISTS workspace_members_update_privileged ON public.workspace_members;"
    )
    op.execute(_UPDATE_POLICY)

    op.execute(_LAST_OWNER_GUARD)
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workspace_members_protect_last_owner "
        "ON public.workspace_members;"
    )
    op.execute(_LAST_OWNER_TRIGGER)


def downgrade() -> None:
    """Restore the STEP-11 policies, including the removal blocker they carried.

    A downgrade restores the previous state rather than keeping the improvement.
    That deliberately reinstates the defect this migration fixes -- removal
    becomes impossible again -- because a migration that only partly reverses is
    not reversible.
    """
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workspace_members_protect_last_owner "
        "ON public.workspace_members;"
    )
    op.execute("DROP FUNCTION IF EXISTS public.app_protect_last_owner();")

    op.execute(
        "DROP POLICY IF EXISTS workspace_members_select_same_workspace ON public.workspace_members;"
    )
    op.execute(
        """
        CREATE POLICY workspace_members_select_same_workspace ON public.workspace_members
        FOR SELECT TO authenticated
        USING (
            deleted_at IS NULL
            AND workspace_id IN (SELECT public.app_current_user_workspaces())
        );
        """
    )

    op.execute(
        "DROP POLICY IF EXISTS workspace_members_update_privileged ON public.workspace_members;"
    )
    op.execute(
        """
        CREATE POLICY workspace_members_update_privileged ON public.workspace_members
        FOR UPDATE TO authenticated
        USING (
            deleted_at IS NULL
            AND (
                workspace_id IN (
                    SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin'])
                )
                OR user_id = auth.uid()
            )
        )
        WITH CHECK (
            workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
            OR (user_id = auth.uid() AND role = 'member')
        );
        """
    )

    op.execute("DROP FUNCTION IF EXISTS public.app_workspace_role(uuid);")
