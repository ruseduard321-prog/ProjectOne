"""Removal, departure and ownership transfer.

The owner's membership rules, decided here and enforced in the database
(migration `b8e1d94c50a7`). The split is the one [[Authorization Model]]
establishes throughout: **the policies and the trigger make a violation
impossible; this service makes the answer legible.**

1. **The last owner may never leave or be removed** --
   `trg_workspace_members_protect_last_owner`, answered as **409 Conflict**.
2. **An owner may remove admins and members** -- the UPDATE policy's ranked
   USING clause, answered as 403.
3. **An owner may transfer ownership before leaving** -- the policy's WITH
   CHECK, answered as 403.
4. **An admin may remove members only** -- the same ranked USING clause, 403.
5. **A member may only leave themselves** -- the policy's own-row branch, 403.

Without this layer every one of those is still enforced -- and every violation
surfaces as either a silently-zero-row `UPDATE` or a raw PostgreSQL constraint
error, neither of which a client can act on.
"""

import uuid

from app.core.permissions import WorkspacePermission, WorkspaceRole, may_remove
from app.core.security import AuthorizationError, LastOwnerError
from app.repositories.memberships import MembershipRepository
from app.services.authorization_service import AuthorizationService


class MembershipService:
    """Applies the workspace membership rules."""

    def __init__(
        self,
        memberships: MembershipRepository,
        authorization: AuthorizationService,
    ) -> None:
        """Store the repository and the authorization gate."""
        self._memberships = memberships
        self._authorization = authorization

    def remove_member(
        self,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
    ) -> None:
        """Remove another member, if the actor outranks them (rules 2 and 4).

        Removing *oneself* is not this operation -- it is `leave`, and routing it
        here would compare a role against itself and be refused by the strict
        rank comparison. That refusal is correct: an owner is not permitted to
        remove a co-owner, and self-removal must not become the exception that
        quietly allows it.

        Raises:
            WorkspaceAccessError: The actor is not a live member.
            AuthorizationError: The actor lacks REMOVE_MEMBER, or does not
                outrank the target, or the target is not a member.
            LastOwnerError: The removal would leave the workspace ownerless.
        """
        if actor_id == target_id:
            raise AuthorizationError(
                f"User {actor_id} attempted to remove themselves; use leave_workspace"
            )

        actor_role = self._authorization.require(
            workspace_id, actor_id, WorkspacePermission.REMOVE_MEMBER
        )

        target_role = self._memberships.role_in(workspace_id, target_id)

        if target_role is None:
            # Deliberately an authorization error rather than a 404. Telling a
            # caller "that user is not in this workspace" answers a question
            # about someone else's membership, which is exactly what the
            # workspace boundary exists to keep private.
            raise AuthorizationError(
                f"User {target_id} holds no live membership of workspace {workspace_id}"
            )

        if not may_remove(actor_role, target_role):
            raise AuthorizationError(
                f"Role {actor_role} may not remove role {target_role} in workspace {workspace_id}"
            )

        self._guard_last_owner(workspace_id, target_role)
        self._memberships.soft_delete(workspace_id, target_id)

    def leave_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Leave a workspace (rule 5), unless doing so orphans it (rule 1).

        Every role holds `LEAVE_WORKSPACE` -- nobody is kept in a workspace
        against their will. The only bar is the last-owner rule, which is about
        the workspace's state rather than the caller's permissions, and is
        therefore a 409 rather than a 403.

        Raises:
            WorkspaceAccessError: The caller is not a live member.
            LastOwnerError: The caller is the last owner.
        """
        role = self._authorization.require(
            workspace_id, user_id, WorkspacePermission.LEAVE_WORKSPACE
        )

        self._guard_last_owner(workspace_id, role)
        self._memberships.soft_delete(workspace_id, user_id)

    def transfer_ownership(
        self,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        successor_id: uuid.UUID,
    ) -> None:
        """Hand ownership to another member (rule 3).

        **Atomic, and the atomicity is the point.** Promoting the successor and
        demoting the outgoing owner are two statements, and a workspace that is
        ownerless or double-owned between them is a state no reader of this
        code should have to reason about. One transaction, so there is no
        between.

        The outgoing owner becomes an `admin` rather than being removed:
        transfer and departure are separate acts, and fusing them would mean a
        transfer silently ejecting someone who only meant to hand over the role.
        They can then leave, which rule 1 now permits because a second owner
        exists.

        Ordering within the transaction does not matter -- the last-owner
        trigger is `DEFERRABLE INITIALLY IMMEDIATE`, so a momentary
        double-owner state is fine and a momentary ownerless one would still be
        caught at commit.

        Raises:
            WorkspaceAccessError: The actor is not a live member.
            AuthorizationError: The actor is not an owner, or the successor is
                not a live member of the workspace.
        """
        self._authorization.require(workspace_id, actor_id, WorkspacePermission.TRANSFER_OWNERSHIP)

        if successor_id == actor_id:
            raise AuthorizationError(
                f"User {actor_id} attempted to transfer ownership to themselves"
            )

        if self._memberships.role_in(workspace_id, successor_id) is None:
            raise AuthorizationError(
                f"User {successor_id} holds no live membership of workspace {workspace_id}"
            )

        with self._memberships.transaction():
            self._memberships.set_role(workspace_id, successor_id, WorkspaceRole.OWNER)
            self._memberships.set_role(workspace_id, actor_id, WorkspaceRole.ADMIN)

    def _guard_last_owner(self, workspace_id: uuid.UUID, role: WorkspaceRole) -> None:
        """Refuse to remove the final owner (rule 1).

        Checked here so the caller receives an actionable 409 naming ownership
        transfer as the remedy. The database enforces the same rule regardless,
        so a future path that forgets this call still cannot orphan a workspace
        -- it simply produces a worse error message.
        """
        if role is not WorkspaceRole.OWNER:
            return

        if self._memberships.live_owner_count(workspace_id) <= 1:
            raise LastOwnerError(f"Workspace {workspace_id} would be left without an owner")
