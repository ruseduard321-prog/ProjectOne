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

import psycopg

from app.core.permissions import WorkspaceRole


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

    def set_role(self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole) -> bool:
        """Change one member's role, returning whether the row existed."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workspace_members SET role = %s "
                "WHERE workspace_id = %s AND user_id = %s AND deleted_at IS NULL",
                (role.value, workspace_id, user_id),
            )

            return cursor.rowcount > 0
