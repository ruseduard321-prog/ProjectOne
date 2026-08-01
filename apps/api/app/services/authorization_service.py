"""Decides whether a caller may perform an action in a workspace.

The decision is business logic and lives here, not in a router (CLAUDE.md §12).
A router's only job is to turn the refusal into a 403.

**This is the second of two gates, and it is not the authoritative one.** The
RLS policies decide what the database will actually do; this service decides
what the API will *say*. They are enforced together on purpose (CLAUDE.md §16 --
defence in depth), with the division of labour stated explicitly:

| Layer | Answers | Failure mode |
|---|---|---|
| RLS policy | Which rows the command may touch | Silently affects zero rows |
| This service | Whether the caller may attempt it at all | Raises, becomes a 403 |

Relying on RLS alone would be *safe* and would behave badly: a member updating a
workspace they may not update gets `UPDATE 0` and a cheerful 200 back. Relying
on this service alone would behave well and be unsafe: one endpoint forgetting
the dependency would be an unguarded write path.
"""

import uuid

from app.core.permissions import WorkspacePermission, WorkspaceRole, role_allows
from app.core.security import AuthorizationError, WorkspaceAccessError
from app.repositories.memberships import MembershipRepository


class AuthorizationService:
    """Resolves a caller's role and checks it against a required permission."""

    def __init__(self, memberships: MembershipRepository) -> None:
        """Store the membership repository this request reads roles through."""
        self._memberships = memberships

    def require(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        permission: WorkspacePermission,
    ) -> WorkspaceRole:
        """Return the caller's role, or raise if it does not hold the permission.

        Returning the role rather than None is what lets a caller both authorize
        and then use the role (an endpoint whose response shape differs by role)
        without querying twice.

        **The role is resolved from the database on every call.** It is not read
        from the token, and that is a deliberate trade recorded here because the
        alternative is superficially cheaper: a role carried as a JWT claim stays
        stale until the token expires, so demoting an admin would leave them
        fully privileged for the remaining lifetime of their access token. A
        per-request lookup costs one indexed query and makes a demotion effective
        on the caller's very next request.

        Args:
            workspace_id: The workspace being acted on.
            user_id: The verified caller.
            permission: The capability the action requires.

        Returns:
            The role the caller holds in that workspace.

        Raises:
            WorkspaceAccessError: No live membership. Surfaces identically to
                the error below -- see its docstring for why.
            AuthorizationError: A live membership whose role is insufficient.
        """
        role = self._memberships.role_in(workspace_id, user_id)

        if role is None:
            raise WorkspaceAccessError(
                f"User {user_id} holds no live membership of workspace {workspace_id}"
            )

        if not role_allows(role, permission):
            raise AuthorizationError(
                f"Role {role} in workspace {workspace_id} does not hold {permission}"
            )

        return role
