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

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    AIServiceDep,
    CurrentUserDep,
    ProjectRepositoryDep,
    WorkflowRepositoryDep,
    WorkflowRunnerDep,
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
    RunStatus,
    StepStatus,
    WorkflowDefinition,
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
    status_code=status.HTTP_201_CREATED,
    summary="Start a workflow run",
    # Tighter than project creation, and for a different reason: a run makes AI
    # calls, so an accidental loop here spends money rather than merely creating
    # rows. This is the per-user gate; the workspace's spend ceiling and the
    # run's own ExecutionBudget are the two independent ones beneath it.
    dependencies=[Depends(limit_by_user("workflow-run", limit=20, window_seconds=60))],
)
def start_run(
    workspace_id: uuid.UUID,
    request: WorkflowRunStartRequest,
    user: CurrentUserDep,
    projects: ProjectRepositoryDep,
    ai: AIServiceDep,
    runner: WorkflowRunnerDep,
    workflows: WorkflowRepositoryDep,
    _role: _MemberOfWorkspace,
) -> WorkflowRunResponse:
    """Trigger a run and execute it until it finishes, pauses or fails.

    **Synchronous**, and that is a stated limitation rather than an oversight. A
    background queue is real infrastructure needing its own ADR ([[CLAUDE|CLAUDE.md]]
    §10/§28), and the run's wall-clock ceiling (300s) bounds how long a request
    can take in the meantime. The persistence model is already the one a queue
    would need -- state is written after every step and resumed from the
    database -- so moving execution off the request thread later does not change
    this design, only where `_execute_from` is called from.

    Returns **201 with the run in whatever state execution reached**, including
    `failed`. See rule 2 in the module docstring.
    """
    definition = _definition(request.workflow_type, projects, ai)

    run = runner.start(
        workspace_id=workspace_id,
        definition=definition,
        triggered_by=user.id,
        project_id=request.project_id,
    )

    return _run_response(run, workflows.list_steps(workspace_id, run.id))


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
    summary="Approve the step a run is waiting on",
    dependencies=[Depends(limit_by_user("workflow-run", limit=20, window_seconds=60))],
)
def approve_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    user: CurrentUserDep,
    projects: ProjectRepositoryDep,
    ai: AIServiceDep,
    runner: WorkflowRunnerDep,
    workflows: WorkflowRepositoryDep,
    _role: _MayApprove,
) -> WorkflowRunResponse:
    """Approve one gated step and continue the run.

    **Owner and admin only.** A gated step spends money or acts externally, which
    is the same class of consequence guarding AI keys and budgets.

    Approves exactly the step the run is waiting on. The run continues until it
    finishes or reaches the *next* gated step, where it stops again — there is no
    "approve everything from here", because that is autonomous execution and
    CLAUDE.md §15 requires it to be a documented, configured opt-in rather than a
    side effect of clicking approve.

    A run that is not waiting for approval answers **409**: the caller is acting
    on stale state, and saying so is better than silently doing nothing.

    Shares the `workflow-run` rate-limit bucket with starting a run, deliberately
    — both cause AI calls, and separate buckets would let a caller spend twice
    the intended allowance by alternating between them.
    """
    workflow_type = _run_workflow_type(workflows, workspace_id, run_id)
    definition = _definition(workflow_type, projects, ai)

    run = runner.approve(
        workspace_id=workspace_id,
        run_id=run_id,
        definition=definition,
        approved_by=user.id,
    )

    return _run_response(run, workflows.list_steps(workspace_id, run.id))


@router.post(
    "/runs/{run_id}/resume",
    response_model=WorkflowRunResponse,
    summary="Resume an interrupted run",
    dependencies=[Depends(limit_by_user("workflow-run", limit=20, window_seconds=60))],
)
def resume_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    projects: ProjectRepositoryDep,
    ai: AIServiceDep,
    runner: WorkflowRunnerDep,
    workflows: WorkflowRepositoryDep,
    _role: _MemberOfWorkspace,
) -> WorkflowRunResponse:
    """Continue a run from its last completed step.

    For a run interrupted by a process restart or a lost connection. **Resuming
    is not approving**: a run in `awaiting_approval` answers 409 here, because
    letting resume clear a gate would let anyone who can restart a run bypass the
    human CLAUDE.md §15 put behind it.

    `VIEW_WORKSPACE` rather than the approval gate: resuming continues work
    already authorized, and the next gated step will still stop the run.
    """
    workflow_type = _run_workflow_type(workflows, workspace_id, run_id)
    definition = _definition(workflow_type, projects, ai)

    run = runner.resume(workspace_id=workspace_id, run_id=run_id, definition=definition)

    return _run_response(run, workflows.list_steps(workspace_id, run.id))


def _run_workflow_type(
    workflows: WorkflowRepositoryDep,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
) -> str:
    """Return the workflow type a stored run executed.

    Read from the run rather than taken from the request body, which is the
    property that stops a caller resuming run A against workflow B's steps --
    a body-supplied type would let a client substitute a different step sequence
    into a run already in progress.

    Raises:
        RunNotFoundError: no live run matched. Raised here so the definition is
            never built for a run the caller cannot see.
    """
    run = workflows.get_run(workspace_id, run_id)

    if run is None:
        raise RunNotFoundError()

    return run.workflow_type
