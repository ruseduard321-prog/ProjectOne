"""Workspace creation and membership addition.

Two operations that look similar and are not, and the difference is the whole
reason this service exists.

## Creating a workspace is the bootstrap case

It needs two rows -- the `workspaces` row and the creator's first
`workspace_members` row -- and the second cannot be written by a client. The
`workspace_members_insert_same_workspace` policy requires the caller to already
belong to the workspace being written to, and the creator does not, because the
workspace did not exist a statement ago. Verified against a live database during
STEP-13 rather than assumed: the `workspaces` INSERT succeeds and the membership
INSERT is refused with *"new row violates row-level security policy"*.

That is deliberate ([[RLS Policy Pattern]]): it forces workspace creation
through an audited service path instead of letting a client assemble a tenant
boundary row by row. This module is that path, following
`UserRepository.ensure_profile`'s established shape -- privileged connection,
one narrow purpose, documented reasoning -- and adding the audit record that
provisioning deliberately lacks, because creating a tenant boundary is a more
consequential event than a profile row appearing.

## Adding a member is *not* the bootstrap case

The same probe found that a live member **can** insert a membership row for
someone else into their own workspace over the ordinary tenant connection -- the
policy's test is the *caller's* membership, which they have. Earlier build-plan
notes recorded invitation as "still unsolved, needs the privileged path"; that
conflated the two cases. Adding a member runs over `TenantConnectionDep` like
every other tenant write, and reaching for the privileged connection here would
discard RLS for an operation that never needed it.

The authorization gate is `MANAGE_MEMBERS`, checked in the service rather than
only at the route, so a future non-HTTP caller cannot skip it.
"""

import uuid

import psycopg

from app.core.permissions import WorkspacePermission, WorkspaceRole
from app.core.security import AuthorizationError
from app.repositories.memberships import MembershipRepository
from app.schemas.workspace import WorkspaceRecord
from app.services.audit_service import AuditAction, AuditService
from app.services.authorization_service import AuthorizationService
from app.services.token_service import AuthenticatedUser


class WorkspaceService:
    """Creates workspaces and adds members to them."""

    def __init__(
        self,
        connection: psycopg.Connection,
        memberships: MembershipRepository,
        authorization: AuthorizationService,
        audit: AuditService,
        privileged_dsn: str,
        connect_timeout: int,
    ) -> None:
        """Store the request's tenant connection and the bootstrap credentials.

        The privileged DSN is passed as a string rather than as `Settings` so
        that what this service can reach is visible at the wiring layer. A
        service holding the whole settings object could open any connection it
        liked; this one can open exactly the one it was handed.
        """
        self._connection = connection
        self._memberships = memberships
        self._authorization = authorization
        self._audit = audit
        self._privileged_dsn = privileged_dsn
        self._connect_timeout = connect_timeout

    def create_workspace(self, name: str, creator: AuthenticatedUser) -> WorkspaceRecord:
        """Create a workspace and make the caller its owner.

        Both rows in **one transaction**. A workspace with no membership row is
        invisible to its own creator -- every policy routes through
        `app_current_user_workspaces()`, which reads memberships -- so a partial
        success here produces an orphaned row that nobody can see, administer or
        delete. One transaction means there is no between.

        No authorization check, deliberately: any authenticated user may create
        a workspace. There is no existing workspace to hold a permission in, and
        requiring one would make the first workspace uncreatable.

        Returns:
            The workspace as created.
        """
        workspace_id = uuid.uuid4()

        # The privileged connection, and the only operation in this module that
        # uses it. `autocommit=False` so the two statements commit together.
        with psycopg.connect(
            self._privileged_dsn,
            connect_timeout=self._connect_timeout,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.workspaces (id, name, owner_id) VALUES (%s, %s, %s)",
                    (workspace_id, name, creator.id),
                )
                cursor.execute(
                    "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                    "VALUES (%s, %s, %s)",
                    (workspace_id, creator.id, WorkspaceRole.OWNER.value),
                )

        # Recorded after the transaction commits, never inside it -- an audit
        # row claiming a workspace exists that then rolled back is worse than a
        # missing one.
        self._audit.record(
            AuditAction.WORKSPACE_CREATED,
            workspace_id=workspace_id,
            actor=creator,
            name=name,
        )

        return WorkspaceRecord(id=workspace_id, name=name, owner_id=creator.id)

    def add_member(
        self,
        workspace_id: uuid.UUID,
        actor: AuthenticatedUser,
        user_id: uuid.UUID,
        role: WorkspaceRole,
    ) -> None:
        """Add an existing user to a workspace.

        **By user id, not by email** -- the project owner's decision on
        2026-08-01. Resolving an email to an account would make this endpoint an
        account-enumeration oracle unless the response were identical whether or
        not the address exists, and a full invitation flow (pending state,
        tokens, delivery) is a larger scope than this step. Adding someone who
        has no ProjectOne account is therefore not possible yet, and that is a
        stated limitation rather than an omission.

        Runs over the **tenant connection**: the INSERT policy tests the
        caller's own membership, which an existing member has. See the module
        docstring for why this is not the bootstrap case.

        A caller may not grant a role they do not themselves hold the standing
        to grant: only an owner may create another owner. Without that rule
        `MANAGE_MEMBERS` would be a self-promotion path -- an admin could add a
        second account of their own as `owner` and then act through it.

        Raises:
            WorkspaceAccessError: The actor is not a live member.
            AuthorizationError: The actor lacks MANAGE_MEMBERS, may not grant
                that role, or the target is already a member.
        """
        actor_role = self._authorization.require(
            workspace_id, actor.id, WorkspacePermission.MANAGE_MEMBERS
        )

        if role is WorkspaceRole.OWNER and actor_role is not WorkspaceRole.OWNER:
            raise AuthorizationError(
                f"Role {actor_role} may not grant owner in workspace {workspace_id}"
            )

        if self._memberships.role_in(workspace_id, user_id) is not None:
            # An authorization error rather than a 409, matching
            # `MembershipService.remove_member`: whether a given user belongs to
            # this workspace is a fact about someone else's membership, and a
            # distinct status code for it answers that question for anyone who
            # asks.
            raise AuthorizationError(
                f"User {user_id} already holds a live membership of workspace {workspace_id}"
            )

        self._memberships.add(workspace_id, user_id, role)

        self._audit.record(
            AuditAction.MEMBER_ADDED,
            workspace_id=workspace_id,
            actor=actor,
            target_id=user_id,
            role=role.value,
        )
