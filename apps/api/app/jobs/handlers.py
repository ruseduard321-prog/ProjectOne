"""The handlers this deployment can run.

[[STEP-30 Async Job Infrastructure]] ships **one**, and that is the step's scope
rather than an omission: it delivers the queue, the worker and the tenant
boundary, and proves them on a trivial handler. Making workflow runs actually
asynchronous is [[STEP-31 Workflow Async Execution]], and writing that handler
here now would be building against a step that has not run
([[CLAUDE|CLAUDE.md]] §35).
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger, log_context
from app.jobs.contract import (
    MAX_JOB_ATTEMPTS,
    JobContext,
    JobHandler,
    JobResult,
    TerminalJobError,
)
from app.repositories.workflows import WorkflowRepository
from app.workflows.runner import WorkflowDefinitionsFactory, WorkflowRunner

logger = get_logger(__name__)


class TenantProbeHandler(JobHandler):
    """Reports what the worker can see of its own workspace, and nothing else.

    **An infrastructure probe, not a product feature.** It exists so the queue,
    the worker loop and the tenant boundary can be exercised end to end against a
    real database without waiting for a real workload -- and so an operator can
    answer "is async execution actually working in this environment" with one
    enqueue rather than by reading logs.

    ## What it proves

    It reads the workspace's own row and counts its live projects **through
    `context.tenant_session()`**, which is an RLS-subject session opened as the
    enqueuing user. A worker that had lost tenant context would read nothing here
    and fail, rather than reading everything and succeeding -- which is the
    failure direction `projectone_api`'s `NOINHERIT` was chosen for and the
    property `test_a_handler_cannot_read_another_workspace` asserts directly.

    ## Why it is duplicate-safe

    **It only reads.** A second delivery re-reads the same two values and
    produces the same result, so at-least-once delivery costs a query and changes
    nothing. That is the cheap end of the obligation every handler carries; a
    handler with an external side effect owes its own durable claim instead --
    see `app/jobs/contract.py`.

    ## Why it does not simply return "ok"

    A probe that asserts nothing about *whose* data it reached would pass just as
    happily in a worker with no tenant scoping at all, which is the one failure
    this step exists to make impossible. Returning the workspace's own name is
    what makes the answer falsifiable.
    """

    @property
    def job_type(self) -> str:
        """Return the stable wire identifier for this handler."""
        return "tenant_probe"

    @property
    def max_attempts(self) -> int:
        """Return the full ceiling: its only plausible failure is transient.

        The probe fails when the database is briefly unreachable, which is
        precisely the shape a retry exists for. A tenant-context failure is
        classified terminal before this handler is ever invoked, so the second
        attempt is never spent re-asking a settled permission question.
        """
        return MAX_JOB_ATTEMPTS

    def execute(self, context: JobContext) -> JobResult:
        """Read the workspace's own name and live project count.

        Two short statements in one short session, which is the shape ADR-005 §4
        prescribes for every handler: the claim has already committed, so this
        holds no lock and no connection while the queue waits.

        Raises:
            TerminalJobError: when the workspace is not visible to the enqueuing
                user's session. Terminal rather than retryable because the
                cause is a permission or a deletion, and neither changes by
                being asked again -- the same reasoning
                `TenantContextUnavailableError` rests on.
        """
        with context.tenant_session() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM public.workspaces WHERE id = %s AND deleted_at IS NULL",
                (context.workspace_id,),
            )
            row = cursor.fetchone()

            if row is None:
                raise TerminalJobError(
                    f"Workspace {context.workspace_id} is not visible to user "
                    f"{context.enqueued_by}",
                    public_message="This workspace is no longer available",
                )

            workspace_name = str(row[0])

            cursor.execute(
                "SELECT count(*) FROM public.projects "
                "WHERE workspace_id = %s AND deleted_at IS NULL",
                (context.workspace_id,),
            )
            counted = cursor.fetchone()

        project_count = 0 if counted is None else int(counted[0])

        logger.info(
            log_context(
                event="job_tenant_probe_completed",
                job_id=context.job_id,
                workspace_id=context.workspace_id,
                attempt=context.attempt,
                projects=project_count,
            )
        )

        output: dict[str, Any] = {
            "workspace_id": str(context.workspace_id),
            "workspace_name": workspace_name,
            "project_count": project_count,
            "attempt": context.attempt,
        }

        return JobResult(output=output, detail="Tenant context verified inside the worker")


class WorkflowExecutionHandler(JobHandler):
    """Drives one workflow run to completion, to its approval gate, or to failure.

    The first handler that does real work, and the reason
    [[STEP-30 Async Job Infrastructure]] built the queue. It decides nothing
    about execution: `WorkflowRunner` still owns step order, the gate, budgets
    and failure, exactly as it did when a run executed inside an HTTP request.
    What changed is *where* that happens and what fences it.

    ## Why this handler is duplicate-safe

    [[ADR-005 Async Job Queue and Worker Execution Model]] §6 requires every
    handler to say **why**, and the honest answer here is four claims, each
    naming a mechanism. `next_step_index` alone is not one of them: it would be
    a true statement about the wrong scenario.

    1. **Sequential redelivery is safe.** `next_step_index` counts only
       `completed` steps, so a later delivery resumes at the first incomplete
       one rather than restarting the run.
    2. **Concurrent redelivery of a non-replayable step is safe.** Entering one
       requires winning a durable claim exactly one execution can hold, and
       persisting its result additionally requires that execution to still hold
       the job's current lease and the run to be non-terminal. A losing or
       superseded execution writes nothing at all.
    3. **Concurrent redelivery of a replayable step is safe by declaration.**
       `replayable = True` asserts the step has no external effect, is verified
       per step, and defaults to `False` for any step that never considered it.
    4. **A gated step cannot restart without a fresh approval.** The grant is
       durable, pinned to the approver, and spent at admission -- so an
       interrupted gated step has already consumed its approval and no later
       delivery can execute it on the strength of a decision made about an
       earlier attempt.

    ## What none of that covers

    **A provider call that completed before its worker lost ownership is not
    re-driven automatically, and is not recorded.** The provider was paid and
    nothing in this platform knows it. No automatic delivery re-enters that
    step -- the claim never expires and is never stolen -- but an explicit
    recovery may repeat the call, and the endpoint that offers it says so.

    **There is no exactly-once provider execution here, and nothing in this
    class should be read as claiming one.** It closes only with provider-side
    idempotency keys, which ADR-005 §Scope Boundaries leaves open and
    [[ADR-006 Workflow Async Execution and Run Reconciliation]] does not reopen.

    ## An interruption is terminal, and never a success

    A replacement worker that finds the step claimed raises `StepInterruptedError`
    and lets the job dead-letter, which reconciles the run to `failed` in the same
    statement. Reporting success instead would leave a job terminally
    `succeeded`, a run still `running`, and nothing able to advance or reconcile
    it -- a stranded run nobody would notice.
    """

    def __init__(self, definitions: WorkflowDefinitionsFactory) -> None:
        """Store the factory this handler builds each run's definition through.

        Injected rather than imported. A definition holds steps, and steps hold
        services bound to a connection, so building one needs configuration this
        handler must not be able to reach -- there is no `Settings` here and no
        way to obtain one (ADR-005 §5 constraint 3).
        """
        self._definitions = definitions

    @property
    def job_type(self) -> str:
        """Return the type the protected commands write on every workflow job.

        A wire value: `ck_jobs_workflow_link_matches_type` ties it to the
        presence of `jobs.workflow_run_id` in both directions, so renaming it
        here without renaming it in a migration makes every workflow job
        impossible to insert rather than merely unregistered.
        """
        return "workflow.execute"

    @property
    def max_attempts(self) -> int:
        """Return the accepted ceiling, declared rather than defaulted.

        `MAX_JOB_ATTEMPTS` is the whole of it: two attempts per enqueue, which
        composes to `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` = 60 upstream provider
        requests as the worst case for one run. The same number is fixed in the
        commands that enqueue, and `test_workflow_commands.py` asserts the two
        agree rather than trusting they were edited together.
        """
        return MAX_JOB_ATTEMPTS

    def execute(self, context: JobContext) -> JobResult:
        """Advance the run this job names, and report where it stopped.

        Raises:
            TerminalJobError: the job carries no run link or no lease token, or
                the run is not visible to its actor. None of the three can be
                fixed by trying again.
            StepInterruptedError: another execution holds a non-replayable step.
            StepOwnershipLostError: this delivery lost the job or its lease.
        """
        run_id = context.workflow_run_id

        if run_id is None or context.lease_token is None:
            # Unreachable through the commands, which set both. Refused loudly
            # rather than defensively defaulted, because a workflow job without
            # its relational link is a job nothing could safely drive.
            raise TerminalJobError(
                f"Job {context.job_id} carries no workflow run link or no lease token",
                public_message="This job is missing the information needed to run it",
            )

        with context.tenant_session() as connection:
            run = WorkflowRepository(connection).get_run(context.workspace_id, run_id)

        if run is None:
            raise TerminalJobError(
                f"Workflow run {run_id} is not visible to user {context.enqueued_by}",
                public_message="This workflow run is no longer available",
            )

        final = WorkflowRunner(context.tenant_session).execute(
            workspace_id=context.workspace_id,
            run_id=run_id,
            definitions=self._definitions,
            job_id=context.job_id,
            lease_token=context.lease_token,
        )

        logger.info(
            log_context(
                event="job_workflow_run_advanced",
                job_id=context.job_id,
                workspace_id=context.workspace_id,
                run_id=run_id,
                workflow_type=final.workflow_type,
                status=final.status,
                attempt=context.attempt,
            )
        )

        return JobResult(
            # The run id and its status, and nothing else. A job result is
            # tenant-readable, and the run itself is the authoritative record
            # of what happened (ADR-006 D3) -- duplicating its detail here would
            # be a second answer able to disagree with the first.
            output={"run_id": str(run_id), "status": final.status},
            detail=f"Workflow run {final.status}",
        )
