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
