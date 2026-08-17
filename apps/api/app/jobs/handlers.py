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
