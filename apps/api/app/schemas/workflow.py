"""Request and response contracts for the workflow endpoints.

[[STEP-22 Minimum Workflow Engine]] puts the first HTTP surface on automated
execution. Two properties are enforced here rather than in a route body:

1. **`status` is never accepted as input.** A run's state is the engine's
   decision at every point, so there is no field through which a client could
   set one. Starting, approving and resuming are separate routes that *ask* for
   a transition rather than assert one -- the same reasoning that made a project
   transition a `POST` to a sub-resource rather than a `PATCH` of `status`.
2. **Every request model forbids extra fields.** `extra="forbid"` throughout, so
   an unexpected field is a 422 naming it rather than a silent discard.

`workspace_id` appears in no request model: it is always the verified path
parameter that `requires(...)` authorized against.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.workflows.models import RunStatus, StepStatus


class WorkflowRunStartRequest(BaseModel):
    """A run being started.

    `workflow_type` is a body field rather than a path segment because it names
    *what to run*, not which tenant -- and an unknown value is a 422 listing the
    available workflows, which reveals nothing about any tenant.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_type: str

    #: The project this run acts on. Optional at the schema level because not
    #: every workflow is project-scoped; the workflow's own validation step
    #: refuses a run that needs one and did not get it, which keeps the
    #: requirement with the workflow that has it rather than in this shared model.
    project_id: uuid.UUID | None = None


class WorkflowStepRunResponse(BaseModel):
    """One step of one run, as a client may see it."""

    step_index: int
    step_name: str
    status: StepStatus

    #: What happened, in words safe to show. Null for a step that has not run.
    detail: str | None

    #: What this step consumed. Zero for a step that made no AI call, which is
    #: honest rather than null: the step ran and spent nothing.
    tokens_used: int

    started_at: str | None
    finished_at: str | None


class WorkflowRunResponse(BaseModel):
    """One run and its step history.

    Timestamps and ids are serialized as strings, matching every other response
    model in this codebase.
    """

    id: str
    workspace_id: str
    workflow_type: str

    #: The definition version this run **executed**, not the current one. A run
    #: keeps reporting what actually ran even after the definition changes --
    #: see migration `f3c82b19d4a7`.
    definition_version: int

    status: RunStatus
    project_id: str | None

    #: Why the run failed, or which step it is waiting on. Null on a healthy run.
    detail: str | None

    triggered_by: str
    started_at: str | None
    finished_at: str | None
    created_at: str

    #: The run's steps, in execution order. Carried on the run rather than served
    #: from a separate endpoint: a run's state is only interpretable alongside
    #: the steps that produced it, and two round trips to answer one question is
    #: a contract that invites clients to render a run without its history.
    steps: list[WorkflowStepRunResponse]


class WorkflowCatalogResponse(BaseModel):
    """Which workflows this deployment can run.

    Exists so a client can populate a picker without hardcoding names that only
    the server actually knows -- the same reasoning as `legal_transitions` on a
    project: the server owns the vocabulary, and a client copy of it drifts.
    """

    workflows: list[str]
