"""Workspace router.

Deliberately minimal. Full workspace management -- creation, invitations,
membership -- belongs to STEP-13, which owns the audited service path the INSERT
policies require. Widening this router would be scope creep (CLAUDE.md §29/§35).

What STEP-11 adds is the two routes that make authorization *observable through
the API* rather than only in the database: a role-gated write, and the data
ownership surface. Both declare their required permission in the signature; the
decision itself lives in `AuthorizationService`, never in a handler
(CLAUDE.md §12).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import (
    CurrentUserDep,
    DataOwnershipServiceDep,
    TenantConnectionDep,
    requires,
)
from app.core.permissions import (
    WorkspacePermission,
    WorkspaceRole,
    permissions_for,
)
from app.schemas.workspace import (
    WorkspaceErasureResponse,
    WorkspaceExportResponse,
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
