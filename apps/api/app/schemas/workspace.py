"""Request and response contracts for workspace endpoints."""

from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints

from app.core.permissions import WorkspacePermission, WorkspaceRole

# Trimmed first, then length-checked. The order is what makes it useful: a
# whitespace-only name passes a naive `min_length=1` and renders as a blank
# workspace, so the strip has to happen before the bound is applied --
# `StringConstraints` does exactly that, which `Field(min_length=...)` alone
# does not.
WorkspaceName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class WorkspaceResponse(BaseModel):
    """A workspace the caller belongs to."""

    id: str
    name: str
    owner_id: str


class WorkspaceRenameRequest(BaseModel):
    """A new name for a workspace.

    Length-bounded at the edge, before the value reaches any business logic
    (CLAUDE.md §12/§16 -- every external input is validated by a schema first).
    """

    name: WorkspaceName


class WorkspacePermissionsResponse(BaseModel):
    """The caller's role in a workspace and everything it permits."""

    workspace_id: str
    role: WorkspaceRole
    permissions: list[WorkspacePermission]


class WorkspaceExportResponse(BaseModel):
    """Every record a workspace holds, keyed by store name.

    `dict[str, Any]` for the records because each store defines its own shape and
    an export must carry whatever a store actually holds. This is the one place
    a loose type is correct rather than lazy: narrowing it would mean this
    schema had to change every time a store is added, which is precisely the
    coupling the store registry exists to avoid.
    """

    workspace_id: str
    stores: dict[str, list[dict[str, Any]]]


class WorkspaceErasureResponse(BaseModel):
    """How many records each store erased.

    Per-store counts rather than a success flag: "deleted" is not a useful claim
    about a multi-store erasure, and a store reporting zero is information the
    caller needs rather than noise.
    """

    workspace_id: str
    erased: dict[str, int]
