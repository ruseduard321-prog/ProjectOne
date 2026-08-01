"""Make the RLS policies role-aware, and add the data-export helper.

STEP-09 fixed the *tenant* boundary: its policies ask "is this requester a live
member of the workspace" and nothing finer. That leaves a real hole inside the
boundary -- an ordinary `member` can rename the workspace, and can rewrite any
other member's role row, exactly as its owner can. `workspace_members.role` has
existed since STEP-08 and no policy has ever read it.

This migration closes that, and the reasoning for *where* it is closed is the
load-bearing decision of STEP-11:

**Both layers enforce it; the database is authoritative.** The API's permission
dependency (`app/core/dependencies.py::requires`) refuses the request, and these
policies refuse the rows. Neither alone is sufficient:

- **Policies alone** are safe but behave badly. A member updating a workspace
  they may not update matches no row, so the statement reports `UPDATE 0` and
  the caller gets a cheerful 200 describing a change that did not happen. A
  policy cannot return 403 -- it has no idea an HTTP request exists.
- **The service layer alone** behaves well and is unsafe. One future endpoint
  that forgets the dependency is an unguarded write path, and nothing about the
  query will look wrong (CLAUDE.md §16: security is a default posture, not a
  check someone remembers).

The duplication is therefore deliberate rather than accidental, and the risk it
carries -- two copies of a rule drifting apart -- is answered by naming which
copy wins: **if these policies and the Python matrix disagree, these policies are
correct and the matrix is a bug.** `app/core/permissions.py` holds the single
statement of the model that both are written from.

## What changes

Two UPDATE policies are replaced, in place:

**`workspaces_update_member` becomes `workspaces_update_privileged`.** Was: any
live member. Now: `owner` or `admin` only.

**`workspace_members_update_same_workspace` becomes
`workspace_members_update_privileged`.** Was: any live member, on any row in the
workspace. Now: `owner`/`admin` on any row, and a `member` on **their own row
only**.

The `member`-editing-their-own-row carve-out lets a member update their own
membership row and nothing else. The `WITH CHECK` pins `user_id` and `role`, so
they cannot hand the row to someone else or promote themselves while doing it.

> **Self-removal does not work today, and this migration does not fix it.**
> Leaving a workspace would be an UPDATE setting one's own `deleted_at` (there
> is no DELETE policy anywhere -- RLS Policy Pattern). That statement is
> rejected, and **not** by this policy: STEP-09's
> `workspace_members_select_same_workspace` filters `deleted_at IS NULL`, so the
> soft-deleted row becomes invisible to the same statement that wrote it and
> PostgreSQL refuses the update. Reproduced against a live database during
> STEP-11 validation, and confirmed by observing the update succeed once that
> `deleted_at` filter was lifted.
>
> Fixing it means changing a STEP-09 SELECT policy, which is a Critical
> multi-tenancy change and its own decision -- not something to fold into an
> RBAC step (CLAUDE.md §21/§29). Recorded here and in the step note rather than
> worked around, because a carve-out that silently cannot do the thing it was
> written for is worse than an acknowledged gap.

SELECT and INSERT policies are untouched. Reading is `VIEW_WORKSPACE`, which
every role holds, and workspace/member creation still has no client-reachable
path (STEP-13 owns the audited service path those INSERT policies were written
for). Widening either here would be scope creep.

## The role predicate

Role membership is tested through `app_current_user_workspaces_as(text[])`, a
second SECURITY DEFINER function alongside STEP-09's. The same containment
measures apply for the same reasons -- see the comment above it -- with one
addition: it takes a *parameter*, which STEP-09's deliberately does not.

That difference is safe here and the distinction matters. The banned shape is a
parameter naming **whose** access to inspect (`workspaces_for(user_id)`), which
would let any caller ask what another user can see. This parameter names which
*roles* to filter the caller's own memberships by; identity still comes from
`auth.uid()` internally, so the answer is still only ever about the caller. The
worst a hostile argument achieves is asking about a role that does not exist,
which returns nothing.

Revision ID: 9f4d2c7a1b83
Revises: d7b95c1f4e08
Create Date: 2026-08-01 16:05:44.312880

"""

from collections.abc import Sequence

from alembic import op

revision: str = "9f4d2c7a1b83"
down_revision: str | Sequence[str] | None = "d7b95c1f4e08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The role-filtered sibling of STEP-09's `app_current_user_workspaces()`.
#
# Every containment measure from that function is repeated here, because each
# one answers a threat that has nothing to do with the other:
#
# - **`SET search_path = ''`** with schema-qualified names -- without it a caller
#   able to create objects could shadow `workspace_members` and have this read
#   their table with the owner's rights. The classic definer escalation path.
# - **`STABLE`** -- read-only, and the planner may cache within a statement.
# - **EXECUTE revoked from PUBLIC *and* from `anon` and `service_role` by name.**
#   Revoking from PUBLIC alone is not sufficient: Supabase's default privileges
#   grant EXECUTE to those roles by name at creation time, and a revoke from
#   PUBLIC does not remove a grant a named role holds explicitly. Observed on the
#   live database during STEP-09, and guarded by
#   `test_definer_function_is_not_executable_by_anon`.
# - **Returns only workspace ids the caller already belongs to** -- never rows,
#   never another user's data.
#
# `STRICT` is added: called with NULL it returns NULL rather than scanning. A
# policy predicate is the last place to want a NULL argument quietly behaving
# like an empty filter.
_ROLE_FUNCTION = """
CREATE OR REPLACE FUNCTION public.app_current_user_workspaces_as(required_roles text[])
RETURNS setof uuid
LANGUAGE sql
STABLE
STRICT
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT wm.workspace_id
    FROM public.workspace_members wm
    WHERE wm.user_id = auth.uid()
      AND wm.deleted_at IS NULL
      AND wm.role = ANY(required_roles)
$$;
"""

_ROLE_FUNCTION_GRANTS = """
REVOKE ALL ON FUNCTION public.app_current_user_workspaces_as(text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_current_user_workspaces_as(text[]) FROM anon;
REVOKE ALL ON FUNCTION public.app_current_user_workspaces_as(text[]) FROM service_role;
GRANT EXECUTE ON FUNCTION public.app_current_user_workspaces_as(text[]) TO authenticated;
"""

# The roles permitted to write. Mirrors `WRITE_ROLES` in
# `app/core/permissions.py` -- the two are the same rule expressed in the two
# languages that have to enforce it.
_WRITE_ROLES = "ARRAY['owner','admin']"

# Replaced policies, as (table, old name, new name, command, clauses).
#
# Dropped and recreated rather than altered: `ALTER POLICY` exists, but a
# rename plus a predicate change reads far more clearly as the pair below, and
# the drop makes the downgrade symmetrical.
_REPLACEMENTS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "workspaces",
        "workspaces_update_member",
        "workspaces_update_privileged",
        "UPDATE",
        f"""
        USING (
            deleted_at IS NULL
            AND id IN (SELECT public.app_current_user_workspaces_as({_WRITE_ROLES}))
        )
        WITH CHECK (
            id IN (SELECT public.app_current_user_workspaces_as({_WRITE_ROLES}))
        )
        """,
    ),
    # A member may edit exactly one membership row: their own.
    #
    # The WITH CHECK is what keeps that narrow. It re-tests the destination row,
    # so a member cannot use their own-row permission to change `user_id` (hand
    # the row to someone else) or their `role` (self-promotion, the obvious
    # attack this whole predicate exists to stop).
    #
    # **The own-row branch deliberately does not re-check membership.** WITH
    # CHECK evaluates the row *after* the update and
    # `app_current_user_workspaces()` filters `deleted_at IS NULL`, so including
    # a membership test would reject any update that soft-deletes the row.
    # Nothing is lost: the USING clause already proved the row was a live
    # membership the caller could see, and `user_id = auth.uid()` proves the
    # destination row is still theirs.
    #
    # Note this branch still cannot express *self-removal* -- see the module
    # docstring. That is blocked upstream by STEP-09's SELECT policy, not here.
    (
        "workspace_members",
        "workspace_members_update_same_workspace",
        "workspace_members_update_privileged",
        "UPDATE",
        f"""
        USING (
            deleted_at IS NULL
            AND (
                workspace_id IN (SELECT public.app_current_user_workspaces_as({_WRITE_ROLES}))
                OR user_id = auth.uid()
            )
        )
        WITH CHECK (
            workspace_id IN (SELECT public.app_current_user_workspaces_as({_WRITE_ROLES}))
            OR (user_id = auth.uid() AND role = 'member')
        )
        """,
    ),
)


def upgrade() -> None:
    """Replace the member-level UPDATE policies with role-aware ones."""
    op.execute(_ROLE_FUNCTION)
    op.execute(_ROLE_FUNCTION_GRANTS)

    for table, old_name, new_name, command, clauses in _REPLACEMENTS:
        # Dropped before the replacement is created. Two UPDATE policies on one
        # table are OR-ed together by PostgreSQL, so leaving the old one in
        # place would keep granting exactly what this migration removes -- a
        # tightening migration that silently changes nothing.
        op.execute(f"DROP POLICY IF EXISTS {old_name} ON public.{table};")
        op.execute(
            f"CREATE POLICY {new_name} ON public.{table} FOR {command} TO authenticated {clauses};"
        )


def downgrade() -> None:
    """Restore the STEP-09 member-level policies verbatim.

    A downgrade restores the previous state; it does not keep the improvement.
    Leaving the tightened policies in place would mean the migration was not
    reversible, and the next upgrade would then be recreating policies that
    already exist.
    """
    op.execute(
        """
        DROP POLICY IF EXISTS workspaces_update_privileged ON public.workspaces;
        CREATE POLICY workspaces_update_member ON public.workspaces
        FOR UPDATE TO authenticated
        USING (
            deleted_at IS NULL
            AND id IN (SELECT public.app_current_user_workspaces())
        )
        WITH CHECK (id IN (SELECT public.app_current_user_workspaces()));
        """
    )
    op.execute(
        """
        DROP POLICY IF EXISTS workspace_members_update_privileged ON public.workspace_members;
        CREATE POLICY workspace_members_update_same_workspace ON public.workspace_members
        FOR UPDATE TO authenticated
        USING (
            deleted_at IS NULL
            AND workspace_id IN (SELECT public.app_current_user_workspaces())
        )
        WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));
        """
    )

    op.execute("DROP FUNCTION IF EXISTS public.app_current_user_workspaces_as(text[]);")
