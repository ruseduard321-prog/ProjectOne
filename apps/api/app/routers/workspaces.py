"""Workspace router.

Read-only, and deliberately minimal. Full workspace management — creation,
membership, roles — belongs to STEP-13, which owns the audited service path the
INSERT policies require. Widening this router would be scope creep
(CLAUDE.md §29/§35).

It exists now because STEP-10's Validation demands proof that a request reads
only its own workspace's rows **through the API**, not merely through a psql
session. That proof needs a real endpoint reaching a real tenant table over the
request-path connection, which is exactly what this is.
"""

from fastapi import APIRouter

from app.core.dependencies import TenantConnectionDep
from app.schemas.workspace import WorkspaceResponse

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
    second, weaker copy of a rule the database already enforces — and the kind
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
