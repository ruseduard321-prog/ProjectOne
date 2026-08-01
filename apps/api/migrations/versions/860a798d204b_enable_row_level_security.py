"""Enable Row Level Security on the foundational tables.

Workspace isolation enforced at the database layer (CLAUDE.md §16). This
migration establishes the pattern every future tenant table copies, so the
reasoning is written out here rather than left to be re-derived.

**Identity reaches a policy through `auth.uid()`**, Supabase's `STABLE` function
reading the `request.jwt.claim.sub` session setting. It returns NULL when no JWT
claim is set, so every policy below denies rather than grants in that case -- an
unauthenticated session sees nothing. STEP-10 owns *setting* that claim on a
request; this migration only consumes it.

Three properties this migration must have, each of which has a specific trap:

1. **`workspace_members` cannot reference itself in its own policy.** A policy
   on that table that subqueries that table recurses -- PostgreSQL raises
   "infinite recursion detected in policy for relation". Resolved by
   `app_current_user_workspaces()`, a SECURITY DEFINER function that reads
   memberships *outside* RLS. Verified against a live database before this
   migration was written, not assumed.

2. **A SECURITY DEFINER function is itself a bypass vector**, which is exactly
   what this step exists to prevent. It is locked down accordingly -- see the
   comment above the function.

3. **Soft-deleted membership must not retain access.** Every policy filters
   `deleted_at IS NULL`, matching the partial indexes from `8a6f39b07c12` so the
   predicates stay index-served rather than forcing a sequential scan on every
   authenticated query.

**FORCE ROW LEVEL SECURITY** is set on every table. Without it the table owner
(`postgres`) silently bypasses its own policies, which would make an isolation
test connecting as the owner pass while proving nothing.

What this migration deliberately does NOT do:

- **It does not revoke `service_role`'s bypass.** That role carries
  `rolbypassrls` and is granted by Supabase; no policy can constrain it. The
  control is architectural -- the API must not use `SUPABASE_SECRET_KEY` for
  tenant queries -- and is documented in the vault, not enforceable here.
- **It does not grant table privileges.** `anon` and `authenticated` already
  hold Supabase's default grants on `public`. Before this migration `anon` could
  read every row of `users`; after it, the policies below decide. Tightening the
  grants themselves belongs to STEP-10, which establishes which role the API
  actually connects as.

Revision ID: 860a798d204b
Revises: 8a6f39b07c12
Create Date: 2026-08-01 10:49:22.876503

"""

from collections.abc import Sequence

from alembic import op

revision: str = "860a798d204b"
down_revision: str | Sequence[str] | None = "8a6f39b07c12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = ("users", "workspaces", "workspace_members")

# The function that breaks the recursion described in the module docstring.
#
# SECURITY DEFINER means it runs as its owner (postgres) and therefore reads
# `workspace_members` without RLS applied. That is precisely the power this step
# exists to deny everyone else, so every line below is a containment measure:
#
# - **No parameters.** A `workspaces_for(uuid)` signature would let any caller
#   ask "what can *that* user see" -- an information leak with a friendly API.
#   Taking the identity from `auth.uid()` internally means a caller can only
#   ever ask about themselves.
# - **`SET search_path = ''`** with every name schema-qualified. Without this a
#   caller who can create objects could shadow `workspace_members` with their
#   own table and have this function read it as the owner. This is the classic
#   SECURITY DEFINER privilege-escalation path.
# - **`STABLE`**, not VOLATILE: it only reads, and the planner may cache the
#   result within a statement rather than re-running it per row.
# - **`EXECUTE` revoked from PUBLIC *and* from `anon` and `service_role`
#   by name**, granted only to `authenticated`. Revoking from PUBLIC alone is
#   not sufficient here and the reason is easy to miss: Supabase ships an
#   `ALTER DEFAULT PRIVILEGES ... GRANT EXECUTE ON FUNCTIONS TO anon,
#   authenticated, service_role` on the `public` schema, so a newly created
#   function is granted to those roles *by name* at creation time. A
#   `REVOKE ... FROM PUBLIC` does not remove a grant held explicitly by a named
#   role. Observed on the live database during this step's validation: `anon`
#   still held EXECUTE after the PUBLIC revoke.
# - **Returns only workspace ids the caller already belongs to** -- never rows,
#   never another user's data. The blast radius of the definer's rights is one
#   column of ids the caller is entitled to by definition.
_MEMBERSHIP_FUNCTION = """
CREATE OR REPLACE FUNCTION public.app_current_user_workspaces()
RETURNS setof uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT wm.workspace_id
    FROM public.workspace_members wm
    WHERE wm.user_id = auth.uid()
      AND wm.deleted_at IS NULL
$$;
"""

_FUNCTION_GRANTS = """
REVOKE ALL ON FUNCTION public.app_current_user_workspaces() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_current_user_workspaces() FROM anon;
REVOKE ALL ON FUNCTION public.app_current_user_workspaces() FROM service_role;
GRANT EXECUTE ON FUNCTION public.app_current_user_workspaces() TO authenticated;
"""

# Policies are written per-command rather than as one FOR ALL policy.
#
# FOR ALL applies a single USING expression to SELECT, UPDATE and DELETE and
# reuses it as WITH CHECK for writes. That reads as economical and behaves
# subtly wrong: the condition under which a row may be *read* is not always the
# condition under which it may be *created*. Separating them means each grant is
# stated explicitly and reviewable on its own -- and INSERT, which has no USING
# clause at all, cannot be overlooked.
_POLICIES: tuple[tuple[str, str, str, str], ...] = (
    # ---------------------------------------------------------------- users --
    #
    # `users` is NOT tenant-scoped: a user is not owned by a workspace. The
    # question is therefore not "which workspace" but "which users is this
    # requester entitled to see" -- themselves, plus anyone they share a live
    # workspace with. Without the second clause a member listing shows nobody
    # but the viewer, which is the feature `email` was denormalized for.
    #
    # The co-membership test cannot use app_current_user_workspaces() alone: it
    # must also confirm the *target* user's membership, so it queries
    # workspace_members directly. That is safe here -- this is a policy on
    # `users`, not on `workspace_members`, so no recursion arises.
    (
        "users",
        "users_select_self_or_co_member",
        "SELECT",
        """
        USING (
            deleted_at IS NULL
            AND (
                id = auth.uid()
                OR EXISTS (
                    SELECT 1
                    FROM public.workspace_members wm
                    WHERE wm.user_id = users.id
                      AND wm.deleted_at IS NULL
                      AND wm.workspace_id IN (
                          SELECT public.app_current_user_workspaces()
                      )
                )
            )
        )
        """,
    ),
    # A user may edit their own profile and nobody else's. WITH CHECK repeats
    # the condition so the row cannot be *reassigned* to another identity on the
    # way out -- USING governs which rows are visible to the UPDATE, WITH CHECK
    # governs what they may become. Omitting WITH CHECK would allow
    # `UPDATE users SET id = <someone else>`.
    (
        "users",
        "users_update_self",
        "UPDATE",
        """
        USING (id = auth.uid() AND deleted_at IS NULL)
        WITH CHECK (id = auth.uid())
        """,
    ),
    # ----------------------------------------------------------- workspaces --
    #
    # Visible exactly when the requester holds a live membership row.
    (
        "workspaces",
        "workspaces_select_member",
        "SELECT",
        """
        USING (
            deleted_at IS NULL
            AND id IN (SELECT public.app_current_user_workspaces())
        )
        """,
    ),
    # Updating a workspace requires membership. *Which* members may update it --
    # owner and admin but not member -- is STEP-11's question, not this one:
    # this step fixes the tenant boundary, RBAC refines what happens inside it.
    # Stated here so the absence reads as a deliberate scope line rather than an
    # oversight.
    (
        "workspaces",
        "workspaces_update_member",
        "UPDATE",
        """
        USING (
            deleted_at IS NULL
            AND id IN (SELECT public.app_current_user_workspaces())
        )
        WITH CHECK (id IN (SELECT public.app_current_user_workspaces()))
        """,
    ),
    # Creating a workspace is the bootstrap case and the one genuine asymmetry
    # in this migration: the creator cannot already be a member of a workspace
    # that does not exist yet, so membership cannot be the test. Ownership is:
    # the row must name the creator as its owner. This makes
    # `INSERT INTO workspaces (name, owner_id) VALUES (..., <someone else>)`
    # fail, which is what stops a workspace being planted in another account.
    (
        "workspaces",
        "workspaces_insert_self_owned",
        "INSERT",
        "WITH CHECK (owner_id = auth.uid())",
    ),
    # ---------------------------------------------------- workspace_members --
    #
    # The self-referential table. Every clause below routes through
    # app_current_user_workspaces() rather than querying workspace_members
    # directly -- that is the whole point of the function, and a future policy
    # on this table that forgets it fails loudly with a recursion error rather
    # than silently.
    (
        "workspace_members",
        "workspace_members_select_same_workspace",
        "SELECT",
        """
        USING (
            deleted_at IS NULL
            AND workspace_id IN (SELECT public.app_current_user_workspaces())
        )
        """,
    ),
    # Membership rows are mutable only from inside the workspace they belong to,
    # and cannot be moved to another workspace on update (the WITH CHECK clause
    # re-tests the destination). Role changes and removal rights are STEP-11.
    (
        "workspace_members",
        "workspace_members_update_same_workspace",
        "UPDATE",
        """
        USING (
            deleted_at IS NULL
            AND workspace_id IN (SELECT public.app_current_user_workspaces())
        )
        WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()))
        """,
    ),
    # Inviting someone requires already being in the workspace. The bootstrap
    # membership -- the creator's own first row in a brand-new workspace -- has
    # no membership to test against and so cannot pass this policy. That is
    # deliberate: workspace creation is a two-statement operation belonging in
    # an audited service path (STEP-13), not something a client should be able
    # to assemble row by row. Recorded here because it is the one thing about
    # this policy set that will surprise whoever writes that endpoint.
    (
        "workspace_members",
        "workspace_members_insert_same_workspace",
        "INSERT",
        "WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()))",
    ),
)

# DELETE is granted to no one, on any table, by design.
#
# Soft deletion is the architectural default (CLAUDE.md §13): removal is an
# UPDATE setting `deleted_at`, which the UPDATE policies above already govern.
# A DELETE policy would create a second, unaudited removal path bypassing soft
# deletion entirely -- and with no DELETE policy present, RLS denies the command
# by default. The absence *is* the control, which is worth stating: a reader who
# finds no DELETE policy should not conclude one was forgotten.


def upgrade() -> None:
    """Enable RLS, install the membership helper, and create the policies."""
    op.execute(_MEMBERSHIP_FUNCTION)
    op.execute(_FUNCTION_GRANTS)

    for table in _TABLES:
        # ENABLE turns policies on for everyone except the table owner; FORCE
        # closes that gap. Both are required -- ENABLE alone leaves the owner
        # reading every row, the silent hole that makes an isolation test pass
        # without proving anything.
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;")

    for table, name, command, clauses in _POLICIES:
        op.execute(
            f"CREATE POLICY {name} ON public.{table} FOR {command} TO authenticated {clauses};"
        )


def downgrade() -> None:
    """Remove the policies, the helper, and the RLS flags.

    Policies are dropped explicitly rather than left to fall with the tables:
    this migration did not create the tables and must not assume a later
    downgrade will remove them.
    """
    for table, name, _command, _clauses in _POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON public.{table};")

    for table in _TABLES:
        op.execute(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP FUNCTION IF EXISTS public.app_current_user_workspaces();")
