"""Workspace router.

Every workspace and membership operation the platform needs, as of STEP-13:
creation, member listing and addition, removal, departure, ownership transfer,
the audit trail, plus the permission, export and erasure routes STEP-11 added.

Routers validate input, call a service and return a response -- nothing else
(CLAUDE.md §12). Two patterns recur here and the difference between them is
deliberate:

- **`requires(...)` in the signature** gates a route on a permission, for reads
  whose only rule is "you must be able to see this workspace".
- **Authorization inside the service** for operations whose rules must hold for
  *any* caller, including a future scheduled job or admin path with no HTTP
  route -- adding a member, removing one, export, erasure. A check that lives
  only in a route decoration is a check a non-HTTP caller silently skips.

No route translates an error. `AuthorizationError` becomes 403 and
`LastOwnerError` becomes 409 through the handlers in `app.core.errors`
([[API Conventions]]).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    CurrentUserDep,
    DataOwnershipServiceDep,
    MembershipServiceDep,
    TenantConnectionDep,
    WorkspaceServiceDep,
    requires,
)
from app.core.permissions import (
    WorkspacePermission,
    WorkspaceRole,
    permissions_for,
)
from app.core.user_rate_limit import limit_by_user
from app.repositories.audit import AuditRepository
from app.repositories.memberships import MembershipRepository
from app.schemas.workspace import (
    AuditLimit,
    AuditRecordResponse,
    MemberAddRequest,
    OwnershipTransferRequest,
    WorkspaceCreateRequest,
    WorkspaceErasureResponse,
    WorkspaceExportResponse,
    WorkspaceMemberResponse,
    WorkspacePermissionsResponse,
    WorkspaceRenameRequest,
    WorkspaceResponse,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    summary="Workspaces the caller belongs to",
)
def list_workspaces(connection: TenantConnectionDep) -> list[WorkspaceResponse]:
    """Return every workspace the caller can see.

    There is no `WHERE` clause filtering by user, and that is the point: the
    filtering is done by the `workspaces_select_member` RLS policy, using the
    identity this connection carries. An application-side filter here would be a
    second, weaker copy of a rule the database already enforces -- and the kind
    that silently stops matching when someone edits one of the two.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, owner_id FROM public.workspaces "
            "WHERE deleted_at IS NULL ORDER BY name"
        )

        return [
            WorkspaceResponse(id=str(row[0]), name=row[1], owner_id=str(row[2])) for row in cursor
        ]


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
    # Per user, not per address: this route requires a verified token, so the
    # identity is known and is the honest thing to count against (ADR-002 §1).
    #
    # Generous enough that a person never meets it and a script does. Nothing
    # else bounds workspace creation -- any authenticated caller may create
    # them without limit, and each one bootstraps two rows through the
    # privileged service path.
    dependencies=[Depends(limit_by_user("workspace-create", limit=10, window_seconds=60))],
)
def create_workspace(
    request: WorkspaceCreateRequest,
    user: CurrentUserDep,
    workspaces: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Create a workspace with the caller as its owner.

    No `requires(...)` dependency, deliberately: there is no existing workspace
    to hold a permission in, and any authenticated user may create one. The
    caller cannot name someone else as owner -- the owner is taken from the
    verified token, and the `workspaces_insert_self_owned` policy refuses the
    row if it were not.

    The two-row bootstrap this needs is impossible for a client to perform, so
    it runs through the audited service path. See `WorkspaceService`.
    """
    workspace = workspaces.create_workspace(request.name, user)

    return WorkspaceResponse(
        id=str(workspace.id),
        name=workspace.name,
        owner_id=str(workspace.owner_id),
    )


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
    summary="List a workspace's members",
)
def list_members(
    workspace_id: uuid.UUID,
    connection: TenantConnectionDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))],
) -> list[WorkspaceMemberResponse]:
    """Return every live member of a workspace.

    Removed members are excluded, and the exclusion is explicit in the query
    rather than inherited from the SELECT policy -- migration `b8e1d94c50a7`
    stopped the policy filtering `deleted_at`, which is what made removal
    possible at all. A listing that relied on the policy would show removed
    people as though they were still members.
    """
    members = MembershipRepository(connection).list_members(workspace_id)

    return [
        WorkspaceMemberResponse(
            user_id=str(member.user_id),
            role=member.role,
            email=member.email,
            display_name=member.display_name,
        )
        for member in members
    ]


@router.post(
    "/{workspace_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add an existing user to a workspace",
)
def add_member(
    workspace_id: uuid.UUID,
    request: MemberAddRequest,
    user: CurrentUserDep,
    workspaces: WorkspaceServiceDep,
) -> None:
    """Add an existing ProjectOne user to a workspace.

    Authorization (`MANAGE_MEMBERS`, plus the rule that only an owner may grant
    owner) is enforced **inside the service** rather than by a `requires(...)`
    dependency, matching export and erasure: the role-granting rule must hold
    for any caller, including a future non-HTTP one, and a check that lives only
    in a route decoration is a check a non-HTTP caller silently skips.

    204 rather than 201: the membership has no useful representation of its own
    to return, and the caller already knows both ids they supplied.
    """
    workspaces.add_member(workspace_id, user, request.user_id, request.role)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from a workspace",
)
def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    user: CurrentUserDep,
    memberships: MembershipServiceDep,
) -> None:
    """Remove another member, if the caller outranks them.

    A `DELETE` verb over a soft delete, the honest mapping: from the caller's
    side the membership becomes unreachable, which is what removing means to
    them.

    Removing *oneself* is not this route -- it is `leave`, below. `MembershipService`
    refuses a self-targeted removal explicitly, because routing it here would
    compare a role against itself and quietly permit an owner to remove a
    co-owner.

    The refusals are not translated here: `AuthorizationError` becomes 403 and
    `LastOwnerError` becomes 409 through the handlers in `app.core.errors`.
    """
    memberships.remove_member(workspace_id, user, user_id)


@router.post(
    "/{workspace_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave a workspace",
)
def leave_workspace(
    workspace_id: uuid.UUID,
    user: CurrentUserDep,
    memberships: MembershipServiceDep,
) -> None:
    """Leave a workspace the caller belongs to.

    Every role may leave -- nobody is kept in a workspace against their will.
    The only bar is the last-owner rule, which is about the workspace's state
    rather than the caller's permissions and therefore surfaces as **409**, with
    a message naming ownership transfer as the remedy.

    A `POST` on a sub-resource rather than `DELETE /members/{own id}`: leaving
    and being removed are different acts with different rules, and giving them
    one route would make the distinction depend on comparing ids in a handler.
    """
    memberships.leave_workspace(workspace_id, user)


@router.post(
    "/{workspace_id}/ownership",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Transfer ownership to another member",
)
def transfer_ownership(
    workspace_id: uuid.UUID,
    request: OwnershipTransferRequest,
    user: CurrentUserDep,
    memberships: MembershipServiceDep,
) -> None:
    """Hand ownership to another live member.

    Owner only. The outgoing owner becomes an `admin` rather than being removed
    -- transfer and departure are separate acts, and fusing them would eject
    someone who only meant to hand over the role. They may then leave, which the
    last-owner rule now permits because a second owner exists.

    Both role changes happen in one transaction; see `MembershipService`.
    """
    memberships.transfer_ownership(workspace_id, user, request.successor_id)


@router.get(
    "/{workspace_id}/audit",
    response_model=list[AuditRecordResponse],
    summary="Read a workspace's audit trail",
)
def read_audit_log(
    workspace_id: uuid.UUID,
    connection: TenantConnectionDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))],
    limit: Annotated[AuditLimit, Query()] = 50,
) -> list[AuditRecordResponse]:
    """Return recent auditable actions in a workspace, newest first.

    Readable by every live member rather than admins only: an audit trail whose
    subjects cannot see it protects the workspace's administrators from its
    members rather than the other way round. It records who did what to the
    workspace, which is information the people in it are entitled to.

    Reads run over the tenant connection and are additionally scoped by
    `audit_log_select_same_workspace` -- writes never come through here at all,
    because the table has no INSERT policy (see `AuditRepository`).
    """
    records = AuditRepository.read_for_workspace(connection, workspace_id, limit)

    return [
        AuditRecordResponse(
            id=str(record.id),
            created_at=record.created_at,
            action=record.action,
            actor_id=str(record.actor_id),
            actor_email=record.actor_email,
            target_id=str(record.target_id) if record.target_id else None,
            detail=record.detail,
        )
        for record in records
    ]


@router.get(
    "/{workspace_id}/permissions",
    response_model=WorkspacePermissionsResponse,
    summary="What the caller may do in a workspace",
)
def read_permissions(
    workspace_id: uuid.UUID,
    role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))],
) -> WorkspacePermissionsResponse:
    """Return the caller's role and everything it permits.

    Exists so a client can render an interface that matches what the server will
    actually allow, rather than offering an action and discovering the 403 after
    the user has committed to it. It is a convenience, never the enforcement:
    the checks on the routes below run regardless of what a client believes.

    Requires only `VIEW_WORKSPACE`, so every live member can ask -- and the
    answer only ever describes the caller's own permissions, never another
    member's.
    """
    return WorkspacePermissionsResponse(
        workspace_id=str(workspace_id),
        role=role,
        permissions=sorted(permissions_for(role)),
    )


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Rename a workspace",
)
def rename_workspace(
    workspace_id: uuid.UUID,
    request: WorkspaceRenameRequest,
    connection: TenantConnectionDep,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.UPDATE_WORKSPACE))],
) -> WorkspaceResponse:
    """Rename a workspace the caller administers.

    The `requires(...)` dependency has already refused a `member` with a 403 by
    the time this body runs. The `workspaces_update_privileged` RLS policy would
    also refuse them -- and would do it by matching zero rows, which is why both
    gates exist: the policy makes the write impossible, the dependency makes the
    answer honest.

    The role is bound to `_role` because the permission is required but the value
    is unused here. Naming it explicitly rather than omitting it keeps the check
    visible in the signature; a dependency dropped from a route is not a syntax
    error, it is an unguarded write path.

    Raises:
        HTTPException: 404 when the row is not visible -- which, given the
            dependency above already proved live membership, means the workspace
            was soft-deleted between the two queries.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.workspaces SET name = %s "
            "WHERE id = %s AND deleted_at IS NULL "
            "RETURNING id, name, owner_id",
            (request.name, workspace_id),
        )
        row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    return WorkspaceResponse(id=str(row[0]), name=row[1], owner_id=str(row[2]))


@router.get(
    "/{workspace_id}/export",
    response_model=WorkspaceExportResponse,
    summary="Export everything a workspace holds",
    # The most expensive read the API serves -- every record in every
    # registered store, in one response. It is also the shape a credential
    # thief would reach for, so a low ceiling bounds both the cost and how fast
    # a stolen token drains a workspace.
    #
    # Tight on purpose: exporting is something a person does occasionally, not
    # repeatedly. A legitimate caller never meets five in a minute.
    dependencies=[Depends(limit_by_user("workspace-export", limit=5, window_seconds=60))],
)
def export_workspace(
    workspace_id: uuid.UUID,
    user: CurrentUserDep,
    ownership: DataOwnershipServiceDep,
) -> WorkspaceExportResponse:
    """Return every record the workspace holds, across every registered store.

    Authorization is enforced inside the service rather than by a `requires(...)`
    dependency here, and the difference is deliberate: export and erasure are
    operations the service must never perform unauthorized *whoever* calls it,
    including a future scheduled job or admin path that has no HTTP route. A
    check that lives only in a route decoration is a check that a non-HTTP caller
    silently skips.
    """
    export = ownership.export_workspace(workspace_id, user.id)

    return WorkspaceExportResponse(
        workspace_id=str(export.workspace_id),
        stores=export.stores,
    )


@router.delete(
    "/{workspace_id}/data",
    response_model=WorkspaceErasureResponse,
    summary="Erase everything a workspace holds",
)
def erase_workspace_data(
    workspace_id: uuid.UUID,
    user: CurrentUserDep,
    ownership: DataOwnershipServiceDep,
) -> WorkspaceErasureResponse:
    """Soft-delete every record the workspace holds.

    A `DELETE` verb over a soft delete, which is the honest mapping: from the
    caller's side the data becomes unreachable, which is what deleting means to
    them. What it is not is a hard removal -- see `DataOwnershipService` for
    exactly what this does and does not destroy, stated there rather than
    implied by the verb.

    Owner-only, enforced in the service (`DELETE_WORKSPACE`).
    """
    result = ownership.erase_workspace(workspace_id, user.id)

    return WorkspaceErasureResponse(
        workspace_id=str(result.workspace_id),
        erased=result.erased,
    )
