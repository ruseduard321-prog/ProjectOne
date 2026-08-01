"""Request and response contracts for workspace endpoints."""

import uuid
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

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


@dataclass(frozen=True)
class WorkspaceRecord:
    """A workspace as the service layer returns it.

    A dataclass rather than the response model, so the service does not depend
    on the HTTP schema. The router converts; the service does not know HTTP
    exists (CLAUDE.md §12).
    """

    id: uuid.UUID
    name: str
    owner_id: uuid.UUID


class WorkspaceResponse(BaseModel):
    """A workspace the caller belongs to."""

    id: str
    name: str
    owner_id: str


class WorkspaceCreateRequest(BaseModel):
    """A new workspace.

    Only a name. The owner is the verified caller and is never accepted from a
    body -- an `owner_id` field here would let a caller plant a workspace in
    someone else's account, which is exactly what the
    `workspaces_insert_self_owned` policy refuses at the database layer.
    """

    name: WorkspaceName


class MemberAddRequest(BaseModel):
    """An existing user being added to a workspace.

    **By `user_id`, not by email** — the project owner's decision on 2026-08-01.
    An email-keyed endpoint would reveal whether an address has a ProjectOne
    account unless every response were identical either way, and a full
    invitation flow is a larger scope than this step. Stated as a limitation in
    [[API Conventions]] rather than left to be discovered.
    """

    user_id: uuid.UUID

    # Defaults to the least privileged role. A default of `admin` would make the
    # careless call the dangerous one.
    role: WorkspaceRole = WorkspaceRole.MEMBER


class WorkspaceMemberResponse(BaseModel):
    """One live member of a workspace."""

    user_id: str
    role: WorkspaceRole
    email: str
    display_name: str | None


class OwnershipTransferRequest(BaseModel):
    """The member ownership is being handed to."""

    successor_id: uuid.UUID


class AuditRecordResponse(BaseModel):
    """One entry from a workspace's audit trail."""

    id: str
    created_at: str
    action: str
    actor_id: str
    actor_email: str | None
    target_id: str | None
    detail: dict[str, Any]


#: Bounds on how much audit history one request may ask for.
#:
#: An unbounded `limit` is an invitation to ask for everything at once, which is
#: a slow query and a large response for a table that only grows.
AuditLimit = Annotated[int, Field(ge=1, le=200)]


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
