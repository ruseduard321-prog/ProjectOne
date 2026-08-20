"""Workflow run endpoints.

The first HTTP surface on automated execution. Four rules govern this module:

## 1. No route decides anything about execution

Every handler validates its input, builds the definition, calls `WorkflowRunner`,
and renders the result. **No route decides whether a run may resume, whether a
step needs approval, or what happens on failure** -- the runner owns all of it,
so a future non-HTTP trigger (a schedule, an event) gets identical behaviour.

## 2. A failed run is a 200, not a 500

This is the least obvious rule here and the most important. A run whose step
fails comes back as **200 with a run in `failed`**, because the request
succeeded: the run was started, executed, and recorded its outcome. Reporting it
as a server error would tell the client its call did not happen when it did, and
would lose the run id they need to inspect what went wrong.

What *is* an error status is a request that could never have produced a run: an
unknown workflow type (422), a run that cannot be seen (404), a run whose state
refuses the action (409).

## 3. Approval is owner/admin; everything else is any live member

`requires(UPDATE_WORKSPACE)` on approval only -- the project owner's decision on
2026-08-08. A gated step is by definition one that spends money, publishes, or
acts externally, which is the same class of consequence already guarding AI keys
and spend ceilings. Starting and reading a run are `VIEW_WORKSPACE`, matching
projects: a member who cannot run a workflow on their own project cannot use the
product.

**No new permission was added.** Introducing `workflow:approve` would change the
role model, which is a decision about authorization rather than a detail of this
step.

## 4. Errors are raised, never mapped

`RunNotFoundError` reaches the client as 404, `RunNotResumableError` as 409 and
`WorkflowError` as 422, all through the handler table in `app.core.errors`. No
route here catches any of them.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.api import current_request_id
from app.core.dependencies import (
    AIServiceDep,
    ProjectRepositoryDep,
    WorkflowRepositoryDep,
    requires,
)
from app.core.permissions import WorkspacePermission, WorkspaceRole
from app.core.user_rate_limit import limit_by_user
from app.repositories.workflows import WorkflowRun, WorkflowStepRun
from app.schemas.workflow import (
    WorkflowCatalogResponse,
    WorkflowRunResponse,
    WorkflowRunStartRequest,
    WorkflowStepRunResponse,
)
from app.workflows.definitions import AVAILABLE_WORKFLOWS, build_definition
from app.workflows.models import (
    RunNotFoundError,
    RunNotResumableError,
    RunStatus,
    StepStatus,
    WorkflowDefinition,
    WorkflowStateConflictError,
    ensure_definition_matches,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/workflows", tags=["workflows"])

#: Admits any live member of the workspace named in the path.
_MemberOfWorkspace = Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.VIEW_WORKSPACE))]

#: Admits only an owner or admin.
#:
#: Used on **approval alone**. See rule 3 in the module docstring.
_MayApprove = Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.UPDATE_WORKSPACE))]


def _run_response(run: WorkflowRun, steps: tuple[WorkflowStepRun, ...]) -> WorkflowRunResponse:
    """Render a run together with its step history."""
    return WorkflowRunResponse(
        id=str(run.id),
        workspace_id=str(run.workspace_id),
        workflow_type=run.workflow_type,
        definition_version=run.definition_version,
        status=RunStatus(run.status),
        project_id=None if run.project_id is None else str(run.project_id),
        detail=run.detail,
        triggered_by=str(run.triggered_by),
        started_at=None if run.started_at is None else run.started_at.isoformat(),
        finished_at=None if run.finished_at is None else run.finished_at.isoformat(),
        created_at=run.created_at.isoformat(),
        steps=[
            WorkflowStepRunResponse(
                step_index=step.step_index,
                step_name=step.step_name,
                status=StepStatus(step.status),
                detail=step.detail,
                tokens_used=step.tokens_used,
                started_at=None if step.started_at is None else step.started_at.isoformat(),
                finished_at=None if step.finished_at is None else step.finished_at.isoformat(),
            )
            for step in steps
        ],
    )


def _definition(
    workflow_type: str,
    projects: ProjectRepositoryDep,
    ai: AIServiceDep,
) -> WorkflowDefinition:
    """Build a definition for this request.

    Per request rather than cached: a definition holds steps, and steps hold the
    request's tenant-scoped repository and AI service. A cached definition would
    hold whichever tenant's connection built it first.
    """
    return build_definition(workflow_type, projects, ai)


@router.get(
    "/catalog",
    response_model=WorkflowCatalogResponse,
    summary="Workflows this deployment can run",
)
def read_catalog(
    workspace_id: uuid.UUID,
    _role: _MemberOfWorkspace,
) -> WorkflowCatalogResponse:
    """Return the available workflow names.

    Served from the registry rather than a literal, so a client picker cannot
    offer a workflow the server does not have -- the same reasoning that puts
    `legal_transitions` on a project response.
    """
    return WorkflowCatalogResponse(workflows=list(AVAILABLE_WORKFLOWS))


@router.get(
    "/runs",
    response_model=list[WorkflowRunResponse],
    summary="Recent workflow runs in a workspace",
)
def list_runs(
    workspace_id: uuid.UUID,
    workflows: WorkflowRepositoryDep,
    _role: _MemberOfWorkspace,
) -> list[WorkflowRunResponse]:
    """Return recent runs, newest first, each with its steps.

    Bounded by the repository's own limit. Unlike a workspace's projects, run
    count grows with automation rather than with human effort, so this is a
    collection that genuinely runs away if left unbounded.
    """
    runs = workflows.list_runs_for_workspace(workspace_id)

    return [_run_response(run, workflows.list_steps(workspace_id, run.id)) for run in runs]


@router.post(
    "/runs",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a workflow run",
    # Unchanged, and now genuinely load-bearing rather than nominally so. Since
    # `app_start_workflow_run` refuses any caller that did not arrive over the
    # application login, this route is the only entrance to starting a run, and
    # this limiter is the only gate anyone passes through (ADR-006 D11).
    dependencies=[Depends(limit_by_user("workflow-run", limit=20, window_seconds=60))],
)
def start_run(
    workspace_id: uuid.UUID,
    request: WorkflowRunStartRequest,
    http_request: Request,
    response: Response,
    projects: ProjectRepositoryDep,
    ai: AIServiceDep,
    workflows: WorkflowRepositoryDep,
    _role: _MemberOfWorkspace,
) -> WorkflowRunResponse:
    """Accept a workflow run and queue it.

    **202, not 201, and the difference is the point.** A run row *is* created, so
    201 would not be false -- but the operation is not complete, and 202 is the
    only code that says so. Three sibling endpoints answering with one code for
    one semantic is what makes the contract legible
    ([[ADR-006 Workflow Async Execution and Run Reconciliation]] D1).

    The definition is built here to validate the workflow type and read the
    version this run will be pinned to. It is **not** executed here: a
    multi-minute render inside an HTTP request is what STEP-31 removed.
    """
    definition = _definition(request.workflow_type, projects, ai)

    run_id = workflows.start_run(
        workspace_id=workspace_id,
        workflow_type=definition.workflow_type,
        definition_version=definition.version,
        project_id=request.project_id,
        correlation_id=current_request_id(),
    )

    return _accepted(http_request, response, workflows, workspace_id, run_id)


@router.get(
    "/runs/{run_id}",
    response_model=WorkflowRunResponse,
    summary="One workflow run and its steps",
)
def read_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    workflows: WorkflowRepositoryDep,
    _role: _MemberOfWorkspace,
) -> WorkflowRunResponse:
    """Return one run with its full step history.

    A run in another workspace answers 404 rather than 403, the same conflation
    `ProjectNotFoundError` makes and for the same reason.
    """
    run = workflows.get_run(workspace_id, run_id)

    if run is None:
        # Raised rather than returned so the 404 body is produced by the same
        # handler every other not-found answer goes through.
        raise RunNotFoundError()

    return _run_response(run, workflows.list_steps(workspace_id, run.id))


@router.post(
    "/runs/{run_id}/approval",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Approve the step a run is waiting on",
    dependencies=[Depends(limit_by_user("workflow-run", limit=20, window_seconds=60))],
)
def approve_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    http_request: Request,
    response: Response,
    projects: ProjectRepositoryDep,
    ai: AIServiceDep,
    workflows: WorkflowRepositoryDep,
    _role: _MayApprove,
) -> WorkflowRunResponse:
    """Record the approval and queue the continuation.

    **The approval is now durable state, and it did not used to be.** Approving
    used to pass `approved=True` in memory to a runner executing in the same
    request. Asynchronously the decision has to reach a different process, so it
    is written to the step as a single-use grant pinned to the approver, in the
    same transaction that enqueues the job which will spend it (ADR-006 D9).

    **The grant and the job are inseparable.** There is no way to obtain one
    without the other, which is what keeps a detached entitlement -- a run
    carrying an approval that some other path could spend -- out of reach.

    `UPDATE_WORKSPACE`, unchanged: approving is the consequential half.
    """
    run = workflows.get_run(workspace_id, run_id)

    if run is None:
        raise RunNotFoundError()

    # Before the grant, not after it. An approval that enqueued a job the worker
    # will refuse would turn an owner's decision into a dead-lettered job and a
    # gate whose grant has already been spent -- so a run that outlived its
    # definition is refused here, with `approved_by` untouched and no job
    # created.
    ensure_definition_matches(
        _definition(run.workflow_type, projects, ai),
        run.workflow_type,
        run.definition_version,
    )

    awaited = workflows.first_incomplete_step(workspace_id, run_id)

    if awaited is None or awaited.status != StepStatus.AWAITING_APPROVAL:
        raise WorkflowStateConflictError(f"Run {run_id} records no step waiting for approval")

    # The index is re-derived under the command's own row locks and the call is
    # refused if the answer moved, so this read decides nothing on its own.
    workflows.approve_step(
        workspace_id=workspace_id,
        run_id=run_id,
        step_index=awaited.step_index,
        correlation_id=current_request_id(),
    )

    return _accepted(http_request, response, workflows, workspace_id, run_id)


@router.post(
    "/runs/{run_id}/resume",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Continue a run that stopped before it finished",
    dependencies=[Depends(limit_by_user("workflow-run", limit=20, window_seconds=60))],
)
def resume_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    http_request: Request,
    response: Response,
    projects: ProjectRepositoryDep,
    ai: AIServiceDep,
    workflows: WorkflowRepositoryDep,
    _role: _MemberOfWorkspace,
) -> WorkflowRunResponse:
    """Supersede a stale claim and put a failed run back on a path forward.

    **This is the recovery endpoint** (ADR-006 D10). A step that reaches a paid
    provider is protected by a claim that never expires and is never stolen, so
    a run interrupted inside one does not resume by itself -- continuing is a
    decision a person makes, because the alternative is a platform that silently
    re-spends a user's money to avoid showing them a failure.

    Two outcomes, and never neither:

    - **The interrupted step is not gated** -> it becomes claimable again, the
      run returns to `pending`, and a replacement job is enqueued. Execution
      follows, from the last completed step rather than from the beginning.
    - **The interrupted step is gated** -> the gate is re-armed with **no job**,
      and continuing needs a fresh approval from an owner or admin. The grant
      was spent at admission, so there is nothing left to infer approval from.

    **This may cause a second provider call for the interrupted step**, and that
    is exactly why it is an explicit act rather than an automatic one.

    `VIEW_WORKSPACE`, unchanged: for a gated step this grants nothing, because
    it only re-arms the gate. The consequential half stays behind
    `UPDATE_WORKSPACE` on the approval route.
    """
    run = workflows.get_run(workspace_id, run_id)

    if run is None:
        raise RunNotFoundError()

    if RunStatus(run.status) is not RunStatus.FAILED:
        raise RunNotResumableError(RunStatus(run.status), "resumed")

    interrupted = workflows.first_incomplete_step(workspace_id, run_id)

    if interrupted is None:
        raise WorkflowStateConflictError(f"Run {run_id} records no incomplete step to continue")

    # Whether a step is gated is a property of the definition rather than of any
    # row, so the route reads it and the command re-derives *which* step is
    # interrupted under its lock, refusing if that is not the one named.
    definition = _definition(run.workflow_type, projects, ai)

    # Checked **before** `requires_approval` is read off it. Whether a step is
    # gated is a property of the definition, so reading it from a definition the
    # run did not start under would re-arm the wrong gate -- or skip one.
    ensure_definition_matches(definition, run.workflow_type, run.definition_version)

    gated = definition.step_at(interrupted.step_index).requires_approval

    workflows.recover_run(
        workspace_id=workspace_id,
        run_id=run_id,
        step_index=interrupted.step_index,
        step_requires_approval=gated,
        correlation_id=current_request_id(),
    )

    return _accepted(http_request, response, workflows, workspace_id, run_id)


def _accepted(
    http_request: Request,
    response: Response,
    workflows: WorkflowRepositoryDep,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowRunResponse:
    """Render an accepted run and point `Location` at the monitor for it.

    A 202 says the work was accepted, not done, and `Location` is how a client
    finds out what became of it. It names `GET .../runs/{run_id}` -- the run
    itself, which is exactly what a status monitor is here: `workflow_runs` is
    the authoritative record of user-facing state, and no client surface derives
    it by reading the queue (ADR-006 D2, D3).

    **No job identifier is exposed anywhere.** Doing so would make the queue a
    public contract and turn ADR-005 §1's broker-migration escape hatch into a
    breaking client change.
    """
    run = workflows.get_run(workspace_id, run_id)

    if run is None:  # pragma: no cover - the command just committed it
        raise RunNotFoundError()

    response.headers["Location"] = str(
        http_request.url_for("read_run", workspace_id=workspace_id, run_id=run_id)
    )

    return _run_response(run, workflows.list_steps(workspace_id, run.id))
