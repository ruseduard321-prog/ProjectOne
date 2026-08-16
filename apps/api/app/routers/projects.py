"""Project and asset endpoints.

The first HTTP surface on the lifecycle [[STEP-20 Projects Schema and
Lifecycle]] built. Four rules govern this module:

## 1. No route decides anything

Every handler validates its input, calls `ProjectService`, and renders the
result. **No route re-decides whether a transition is legal**, because the
service owns the state machine and a second copy of it here would be a copy that
drifts (CLAUDE.md §12). The one thing routes do beyond that is derive
`legal_transitions` for the response -- which is *reading* the machine, not
reimplementing it.

## 2. Errors are raised, never mapped

`ProjectNotFoundError` reaches the client as 404 and `IllegalTransitionError` as
409, both through the handler table in `app.core.errors`. No route here catches
either. A second translation site is how two answers to the same condition drift
apart, and the service raises from paths a route cannot see -- `add_asset` calls
`get` internally, so a route catching only its own call would miss it.

## 3. Every live member may create and edit; the workspace boundary is the gate

`requires(VIEW_WORKSPACE)` on every route, which reads oddly on a `POST` and is
correct. Projects are the workspace's shared work, not an administrative
setting: a member who cannot create a project cannot use the product, so the
owner/admin asymmetry that guards AI keys and budgets does not apply here.

**There is no project-specific permission**, deliberately. Adding one to
`app.core.permissions` is a decision about the role model rather than a detail
of this step, and the permission that would be needed first -- "may delete
someone else's project" -- is a question [[Projects]] does not answer yet.

What `requires(VIEW_WORKSPACE)` does provide is the tenant gate: a caller who is
not a live member of the workspace in the path is refused with a 403 before any
handler body runs. RLS then independently refuses the query itself.

## 4. The 404/403 split is deliberate

A **workspace** the caller does not belong to answers **403** -- that is
`requires(...)`, and it is what stops a workspace id becoming an existence
oracle. A **project** id inside a workspace they do belong to answers **404**,
because an invisible project and an absent one are the same fact from the
caller's side. See `_resource_not_found` in `app.core.errors`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.dependencies import (
    AssetStorageServiceDep,
    CurrentUserDep,
    ProjectServiceDep,
    requires,
)
from app.core.permissions import WorkspacePermission, WorkspaceRole
from app.core.user_rate_limit import limit_by_user
from app.repositories.projects import Asset, Project
from app.schemas.project import (
    AssetCreateRequest,
    AssetDownloadResponse,
    AssetKind,
    AssetResponse,
    ProjectCreateRequest,
    ProjectRenameRequest,
    ProjectResponse,
    ProjectTransitionRequest,
)
from app.services.asset_content import MAX_UPLOAD_BYTES, AssetTooLargeError
from app.services.project_service import ProjectStatus, legal_transitions_from

router = APIRouter(prefix="/workspaces/{workspace_id}/projects", tags=["projects"])

#: Admits any live member of the workspace named in the path.
#:
#: Written once rather than repeated in eight signatures -- eight copies is eight
#: chances for one route to be declared with a different permission by accident,
#: and that route would be the hole.
_MemberOfWorkspace = Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))]


def _project_response(project: Project) -> ProjectResponse:
    """Render a project, including the moves it can legally make next.

    `legal_transitions` is computed here from `legal_transitions_from` rather
    than stored or hardcoded, so the states a client is offered are always the
    states the server will accept. **This function is the reason the UI does not
    need its own copy of the state machine** -- see [[Project Lifecycle]].

    Sorted, so the order is stable across responses. `legal_transitions_from`
    returns a `frozenset`, whose iteration order is a hash-ordering detail: an
    unsorted list here would reorder itself between processes and make a
    response body untestable for no reason.
    """
    status_value = ProjectStatus(project.status)

    return ProjectResponse(
        id=str(project.id),
        workspace_id=str(project.workspace_id),
        name=project.name,
        description=project.description,
        status=status_value,
        legal_transitions=sorted(legal_transitions_from(status_value)),
        created_by=str(project.created_by),
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        version=project.version,
    )


def _asset_response(asset: Asset) -> AssetResponse:
    """Render one asset.

    `workspace_id` is deliberately not carried: the caller already knows it (it
    is in the URL they called), and every field a response repeats from its own
    path is a field a client can begin to trust instead of the path.
    """
    return AssetResponse(
        id=str(asset.id),
        project_id=str(asset.project_id),
        name=asset.name,
        # The repository types `kind` as `str` because it reads a `text` column.
        # Narrowing here rather than there keeps the repository a faithful
        # reflection of the schema; the value came from a row the CHECK
        # constraint already validated, so this cannot fail on stored data.
        kind=AssetKind(asset.kind),
        storage_path=asset.storage_path,
        created_by=str(asset.created_by),
        created_at=asset.created_at.isoformat(),
    )


#: How much of an upload is read at a time while checking it against the ceiling.
#:
#: 1 MiB balances two costs that pull in opposite directions: a smaller chunk
#: means more iterations of the loop below, a larger one means more bytes read
#: past the ceiling before the check catches up. At this size an oversized
#: upload is refused having read at most 1 MiB more than the limit.
_UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_within_limit(file: UploadFile) -> bytes:
    """Read an upload, refusing it the moment it exceeds the ceiling.

    **Streamed rather than read whole**, which is the difference between
    refusing a 4 GB upload and running out of memory receiving one. `file.read()`
    with no argument would materialise the entire body first and check the size
    afterwards -- by which point the damage the check exists to prevent has
    already happened.

    The `Content-Length` header is deliberately *not* trusted as the sole check.
    It is a client-supplied number, absent entirely on a chunked request, and
    believing it would let an attacker declare 1 KB and send a gigabyte. It is
    consulted first only as a cheap early refusal for honest clients; what
    actually enforces the limit is counting the bytes as they arrive.

    Args:
        file: The uploaded file, still unread.

    Returns:
        The complete body, guaranteed to be within the ceiling.

    Raises:
        AssetTooLargeError: the body exceeded `MAX_UPLOAD_BYTES`.
    """
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise AssetTooLargeError()

    chunks: list[bytes] = []
    total = 0

    while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
        total += len(chunk)

        if total > MAX_UPLOAD_BYTES:
            # Refused without keeping what has been read so far. Returning early
            # also stops the loop consuming the rest of the body, so a
            # deliberately huge upload costs the server one chunk past the limit
            # rather than all of it.
            raise AssetTooLargeError()

        chunks.append(chunk)

    return b"".join(chunks)


# ----------------------------------------------------------------------------
# Projects
# ----------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="Every live project in a workspace",
)
def list_projects(
    workspace_id: uuid.UUID,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> list[ProjectResponse]:
    """Return this workspace's projects, newest first.

    Unpaginated, and that is a stated limitation rather than an oversight. A
    workspace's project count is bounded by human effort -- a content business
    does not create ten thousand of them -- so pagination would be machinery
    with no user today. The moment a workspace can generate projects
    programmatically ([[Workflow Engine]]), this needs a limit, and the
    repository's stable `created_at DESC, id DESC` ordering is what makes adding
    keyset pagination later a change to one query rather than a redesign.
    """
    return [_project_response(project) for project in projects.list_for_workspace(workspace_id)]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
    # A per-user limit on its own merits, as `POST /workspaces` carries. This is
    # the step's only resource-creating route, so it is the one an accidental
    # loop -- a retrying client, a mis-wired form -- fills a workspace with. The
    # ceiling is well above what a person creating projects by hand reaches.
    dependencies=[Depends(limit_by_user("project-create", limit=30, window_seconds=60))],
)
def create_project(
    workspace_id: uuid.UUID,
    request: ProjectCreateRequest,
    user: CurrentUserDep,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> ProjectResponse:
    """Create a project in the workspace's initial lifecycle state.

    **No idempotency key**, like `POST /workspaces` before it: a retried request
    after a timeout creates a second project. Recorded rather than forgotten --
    the consequence here is a duplicate a user can delete, not a duplicate
    charge, which is why it is a known limitation rather than a blocker. Making
    creation idempotent across the API is one decision taken once ([[API
    Conventions]]), not a thing to invent per route.

    `created_by` is the verified caller, never a body field.
    """
    project = projects.create(
        workspace_id=workspace_id,
        name=request.name,
        created_by=user.id,
        description=request.description,
    )

    return _project_response(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="One project",
)
def read_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> ProjectResponse:
    """Return one live project.

    A project in another workspace answers 404 here rather than 403 -- see the
    module docstring's rule 4. The service raises; this route does not catch.
    """
    return _project_response(projects.get(workspace_id, project_id))


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Rename a project",
)
def rename_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    request: ProjectRenameRequest,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> ProjectResponse:
    """Change a project's name and description.

    `PATCH` over a model carrying both fields, which is worth stating because it
    looks like a `PUT`. The resource has more fields than these two -- status,
    version, timestamps -- and this route writes only these, which is what makes
    it a partial update. Within that partial edit both values are always
    written, so clearing a description is `null` rather than an omission
    (`ProjectRenameRequest`).

    **Cannot change status.** The schema has no such field and this handler
    never passes one, so the transition route below is the only path.
    """
    return _project_response(
        projects.rename(
            workspace_id=workspace_id,
            project_id=project_id,
            name=request.name,
            description=request.description,
        )
    )


@router.post(
    "/{project_id}/transitions",
    response_model=ProjectResponse,
    summary="Move a project to a new lifecycle state",
)
def transition_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    request: ProjectTransitionRequest,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> ProjectResponse:
    """Advance, loop back, or archive a project.

    **A `POST` to a sub-resource rather than a `PATCH` of `status`**, and the
    difference is honest rather than stylistic: a `PATCH` presents the status as
    a field a client may set, and this one is not -- the server decides whether
    the requested move is coherent and refuses most of them. Naming the
    transition as the thing being created says that in the URL.

    Returns the updated project, whose `legal_transitions` now describe the new
    state -- so a client renders the next set of moves from the same response
    rather than re-fetching.

    An illegal move raises `IllegalTransitionError`, answered as **409** by the
    handler table. A status outside the vocabulary never reaches here at all:
    `ProjectTransitionRequest` types it as `ProjectStatus`, so that is a 422.
    """
    return _project_response(projects.transition(workspace_id, project_id, request.status))


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
def delete_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> None:
    """Soft-delete a project.

    **Distinct from archiving, and the API keeps them distinct.** Archiving is a
    lifecycle transition (`POST /transitions` with `archive`) leaving the project
    in the workspace as a record of finished or abandoned work; this removes it.
    A UI that presented one as the other would be lying about which one the user
    performed -- see [[Project Lifecycle#Archive Is Not Deletion]].

    Soft, so the row survives with `deleted_at` set. From the caller's side it is
    gone, which is what `DELETE` means to them, and this codebase maps the verb
    that way throughout.

    Assets attached to the project are **not** cascaded. The composite foreign
    key is `RESTRICT`, and a project's assets stay reachable through the workspace
    export until an erasure removes them -- a cascade here would be a
    bulk deletion performed as a side effect of a single-resource call.
    """
    projects.delete(workspace_id, project_id)


# ----------------------------------------------------------------------------
# Assets
# ----------------------------------------------------------------------------


@router.get(
    "/{project_id}/assets",
    response_model=list[AssetResponse],
    summary="Every live asset attached to a project",
)
def list_assets(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> list[AssetResponse]:
    """Return a project's assets, oldest first.

    Oldest first because assets accumulate as a project progresses, so creation
    order is the order the work happened in.
    """
    return [_asset_response(asset) for asset in projects.list_assets(workspace_id, project_id)]


@router.post(
    "/{project_id}/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach an asset to a project",
    dependencies=[Depends(limit_by_user("project-asset", limit=60, window_seconds=60))],
)
def add_asset(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    request: AssetCreateRequest,
    user: CurrentUserDep,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> AssetResponse:
    """Record an asset against a project.

    **Records an asset; does not upload one.** No storage backend exists, so
    `storage_path` is null on everything this route creates and no bytes cross
    it. That is a real limitation and the response says so honestly rather than
    implying a file is attached -- choosing a backend is an ADR (CLAUDE.md
    §10/§28), and the step that adds one also owes it a deletion path (§16).

    Permitted in any lifecycle state. Restricting attachment to Generation would
    be a rule [[Projects]] does not state, and a reference image attached while a
    project is still an Idea is the obvious counter-example.
    """
    asset = projects.add_asset(
        workspace_id=workspace_id,
        project_id=project_id,
        name=request.name,
        kind=request.kind,
        created_by=user.id,
    )

    return _asset_response(asset)


@router.post(
    "/{project_id}/assets/upload",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file and attach it to a project",
    # The same per-user ceiling the metadata route carries. Not lower despite
    # this route being far more expensive: a limit tight enough to matter for
    # bandwidth would refuse a user legitimately attaching a batch of images, and
    # what actually bounds cost here is the per-asset size ceiling.
    dependencies=[Depends(limit_by_user("project-asset", limit=60, window_seconds=60))],
)
async def upload_asset(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    user: CurrentUserDep,
    assets: AssetStorageServiceDep,
    _role: _MemberOfWorkspace,
    file: Annotated[UploadFile, File(description="The file to store")],
    name: Annotated[str, Form(description="The asset's display name")],
    kind: Annotated[AssetKind, Form(description="What the file is")],
) -> AssetResponse:
    """Store a file's bytes and record it as an asset.

    **The only route that puts bytes in storage.** The sibling `POST /assets`
    records an asset with no file, and both remain useful -- an asset can be
    planned before it exists.

    `async def`, unlike every other handler in this module. Reading a multipart
    body is genuine I/O, and a synchronous handler would occupy a threadpool
    worker for the whole upload; the routes around it do no I/O of their own and
    are correctly synchronous.

    Authorization is `requires(VIEW_WORKSPACE)`, exactly as `add_asset` uses. **No
    new permission is invented here**: a member who may attach an asset may
    attach one with contents, and deciding otherwise would be a change to the
    role model rather than a detail of this step (see this module's rule 3).

    The body is read against a hard ceiling **before** anything is stored, so an
    oversized upload is refused rather than buffered in full. Validation of the
    bytes themselves -- declared type, extension, and the file's own magic
    bytes -- happens in `app.services.asset_content`, which is where the rules
    are testable without HTTP.

    Raises:
        AssetContentError: the file was refused. Answered 413, 415 or 400 by the
            handler table, according to which rule it broke.
        ProjectNotFoundError: no live project matched. Answered 404.
        StorageError: the backend refused or was unreachable. Answered by the
            handler table, never as a 500 naming a bucket.
    """
    data = await _read_within_limit(file)

    asset = assets.upload(
        workspace_id=workspace_id,
        project_id=project_id,
        name=name,
        kind=kind,
        data=data,
        declared_content_type=file.content_type,
        filename=file.filename,
        created_by=user.id,
    )

    return _asset_response(asset)


@router.get(
    "/{project_id}/assets/{asset_id}/download",
    response_model=AssetDownloadResponse,
    summary="Get a time-limited URL for an asset's bytes",
)
def download_asset(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    projects: ProjectServiceDep,
    assets: AssetStorageServiceDep,
    _role: _MemberOfWorkspace,
) -> AssetDownloadResponse:
    """Return a signed URL for one asset's bytes.

    **A URL, never the bytes.** Proxying them would put every megabyte through
    an API worker, and a public bucket path would be a permanent capability
    handed out for a momentary need. The signed URL is neither: short-lived, and
    generated per request (`AssetStorageService.DOWNLOAD_URL_TTL`).

    **Cross-tenant access fails here, at the route, before anything is signed.**
    `requires(VIEW_WORKSPACE)` refuses a caller who is not a live member of the
    workspace in the path, and the asset row is then resolved through the tenant
    connection where RLS refuses another workspace's row -- so a caller who
    should not see this asset receives a 404 and no URL is ever generated. That
    ordering is the point: a route that signed first and checked afterwards
    would have produced a working capability before deciding it was not allowed.

    The project is resolved first for the same reason `delete_asset` does it: an
    asset id from another project would otherwise be reachable through a URL
    naming a project the caller can see, leaving a path segment decorative.

    Raises:
        HTTPException: 404 when the asset is not attached to this project.
        ProjectNotFoundError: no live asset matched. Answered 404.
        AssetFileNotFoundError: the asset holds no bytes. Answered 404 -- there
            is nothing to sign, and a URL to a nonexistent object would fail
            later and less clearly.
    """
    attached = projects.list_assets(workspace_id, project_id)

    if not any(asset.id == asset_id for asset in attached):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    download = assets.download_url(workspace_id, asset_id)

    return AssetDownloadResponse(
        url=download.url,
        expires_in_seconds=download.expires_in_seconds,
    )


@router.delete(
    "/{project_id}/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an asset from a project",
)
def delete_asset(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    projects: ProjectServiceDep,
    _role: _MemberOfWorkspace,
) -> None:
    """Soft-delete one asset.

    The project is resolved first so an asset id from another project -- or
    another workspace -- cannot be deleted through a URL naming a project the
    caller can see. `ProjectService.delete_asset` keys only on the workspace, so
    without this the path segment would be decorative, and a URL whose segments
    are not all enforced is one a reader reasonably assumes *are*.

    Raises:
        HTTPException: 404 when the asset is not attached to this project. Raised
            here rather than in the service because it is a statement about the
            URL's coherence, which is an HTTP concern.
    """
    attached = projects.list_assets(workspace_id, project_id)

    if not any(asset.id == asset_id for asset in attached):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    projects.delete_asset(workspace_id, asset_id)
