"""Reads a caller's membership of a workspace.

One query, but it belongs in a repository rather than inline in the service: it
is the only place the API asks the database "what is this person's role here",
and a second copy of that query appearing elsewhere is how two subtly different
definitions of membership start to exist.

**It runs over the tenant connection, deliberately.** The lookup is subject to
the same RLS policies as everything else, so the row is only visible when the
caller genuinely holds it. Reading roles over the privileged connection would
work, and would mean the authorization layer itself was the one component in the
system not subject to the isolation it enforces.
"""

import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass

import psycopg

from app.core.permissions import WorkspaceRole


@dataclass(frozen=True)
class WorkspaceMember:
    """One live member of a workspace, with the profile fields a list needs."""

    user_id: uuid.UUID
    role: WorkspaceRole
    email: str
    display_name: str | None


class MembershipRepository:
    """Resolves workspace membership for the current request."""

    def __init__(self, connection: psycopg.Connection) -> None:
        """Store the RLS-subject connection this request runs on."""
        self._connection = connection

    def role_in(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceRole | None:
        """Return the caller's role in a workspace, or None when not a member.

        `deleted_at IS NULL` on both rows, matching every RLS policy: a removed
        member's row still exists (removal is a soft delete), and a query that
        omits the filter keeps serving them their old role indefinitely. The
        workspace join carries the same filter so a soft-deleted workspace
        confers no permissions on anyone.

        Args:
            workspace_id: The workspace being acted on.
            user_id: The verified caller. Must come from the authenticated
                identity, never from a request body.

        Returns:
            The role held, or None when there is no live membership.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT wm.role FROM public.workspace_members wm "
                "JOIN public.workspaces w ON w.id = wm.workspace_id "
                "WHERE wm.workspace_id = %s "
                "  AND wm.user_id = %s "
                "  AND wm.deleted_at IS NULL "
                "  AND w.deleted_at IS NULL",
                (workspace_id, user_id),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        # The check constraint guarantees the value is one of the three, so an
        # unknown value here means the constraint was changed without this
        # module. Raising is correct: silently treating an unrecognised role as
        # "no permissions" would hide a schema/code divergence, and treating it
        # as any known role would grant access on the strength of a typo.
        return WorkspaceRole(row[0])

    def transaction(self) -> AbstractContextManager[psycopg.Transaction]:
        """Return a transaction over this request's connection.

        Exposed so a service can make several writes atomic without reaching for
        the connection itself. Ownership transfer is the case that needs it: two
        role changes that must not be observable apart.

        Typed as the context manager `psycopg.Connection.transaction()` actually
        returns, rather than as `Transaction` -- the latter is what the `with`
        block binds, not what the call produces.
        """
        return self._connection.transaction()

    def live_owner_count(self, workspace_id: uuid.UUID) -> int:
        """Return how many live owners a workspace has.

        Read *before* a removal or demotion so the service can refuse with a
        clear 409 rather than letting the caller hit the database trigger and
        surface a raw constraint violation. The trigger remains the authority --
        this is the same two-layer split as everywhere else in
        [[Authorization Model]]: the database makes it impossible, the
        application makes the answer legible.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.workspace_members "
                "WHERE workspace_id = %s AND role = 'owner' AND deleted_at IS NULL",
                (workspace_id,),
            )
            row = cursor.fetchone()

        return int(row[0]) if row is not None else 0

    def soft_delete(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Soft-delete one membership row, returning whether it existed.

        An `UPDATE`, never a `DELETE`: no table has a DELETE policy and
        `authenticated` holds no DELETE grant, both deliberately
        ([[RLS Policy Pattern]]). Removal is `deleted_at`.

        Returns False when nothing matched, which after an authorization check
        means the row was already removed -- not that permission was lacking.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND user_id = %s AND deleted_at IS NULL",
                (workspace_id, user_id),
            )

            return cursor.rowcount > 0

    def add(self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole) -> None:
        """Insert a membership row over the tenant connection.

        Permitted by `workspace_members_insert_same_workspace` because the
        policy tests the *caller's* membership of the workspace, which an
        existing member has. This is not the bootstrap case -- see
        `WorkspaceService` for why the two differ.

        A previously-removed member is **revived** rather than duplicated. Their
        old row still exists -- removal is a soft delete -- and
        `uq_workspace_members_active` is a *partial* unique index
        (`WHERE deleted_at IS NULL`), so a plain INSERT succeeds and leaves two
        rows for the same person: one dead, one live. That passes the constraint
        and corrupts every count and listing that follows.

        The revive is therefore an explicit UPDATE of any dead row first. It
        cannot be `ON CONFLICT`: an inference clause must match the index's
        predicate as well as its columns, and re-adding conflicts with nothing
        while the old row is still soft-deleted.

        Both statements run in one transaction so a revive can never half-apply.
        """
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.workspace_members
                SET deleted_at = NULL, role = %s
                WHERE workspace_id = %s AND user_id = %s AND deleted_at IS NOT NULL
                """,
                (role.value, workspace_id, user_id),
            )

            if cursor.rowcount > 0:
                return

            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, %s)",
                (workspace_id, user_id, role.value),
            )

    def list_members(self, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
        """Return a workspace's live members, with their profiles.

        **`deleted_at IS NULL` is stated explicitly, and must stay that way.**
        The SELECT policy stopped filtering it in migration `b8e1d94c50a7` --
        that is what made removal possible at all -- so a listing that omits the
        filter shows people who have been removed, indistinguishable from those
        who have not. Guarded by a test.

        The join to `users` is subject to `users_select_self_or_co_member`,
        which admits exactly the co-members this query wants, so a member whose
        profile the caller may not see cannot appear here anyway.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT wm.user_id, wm.role, u.email, u.display_name
                FROM public.workspace_members wm
                JOIN public.users u ON u.id = wm.user_id
                WHERE wm.workspace_id = %s
                  AND wm.deleted_at IS NULL
                ORDER BY u.email
                """,
                (workspace_id,),
            )

            return [
                WorkspaceMember(
                    user_id=row[0],
                    role=WorkspaceRole(row[1]),
                    email=row[2],
                    display_name=row[3],
                )
                for row in cursor
            ]

    def set_role(self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole) -> bool:
        """Change one member's role, returning whether the row existed."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workspace_members SET role = %s "
                "WHERE workspace_id = %s AND user_id = %s AND deleted_at IS NULL",
                (role.value, workspace_id, user_id),
            )

            return cursor.rowcount > 0
