"""Executes workflow runs, persists their state, and enforces the approval gate.

This is the class [[Workflow Engine]]'s five execution principles actually live
in, so each is worth naming against the code that provides it:

- **Deterministic** -- steps run in definition order, one at a time. No
  branching, no scheduling, no parallelism; all explicitly out of scope.
- **Observable** -- every run and every step is logged with the correlation id,
  and every outcome is a persisted row.
- **Resumable** -- state is written after *each* step, and `next_step_index`
  reads it back. A run survives the process that started it.
- **Versioned** -- the definition's version is stamped on the run at creation
  and never re-read.
- **Independently executable** -- a run is identified by its id alone, so
  resuming needs no in-memory context.

## Persist after every step, not at the end

`_execute_from` writes each step's outcome before starting the next one. That is
the whole resumability mechanism: the last committed row is always an honest
answer to "where did this run get to", including when the answer is "it crashed
during step 3".

The cost is one round trip per step, which is the correct trade. An engine
batching its writes to save them would lose exactly the runs worth investigating.

## The approval gate stops the run, it does not skip the step

Reaching a step with `requires_approval` and no approval marks the **run**
`awaiting_approval`, marks the **step** the same, and returns. Nothing is
executed. Resuming later re-enters at that same index, because
`next_step_index` counts only `completed` steps.

That shape matters: a gate that let the run continue and merely flagged the step
would be a gate in name only, and a gate that marked the step `skipped` would
silently drop the work a user was asked to approve.

## Approval is per run, not per step

Approving a run clears the gate for **the step it is currently waiting on**, and
the run continues until it finishes or reaches the next gated step -- where it
stops again. There is no "approve everything from here", deliberately: that is
autonomous execution, which CLAUDE.md §15 requires to be an explicitly
configured, documented opt-in rather than a side effect of clicking approve.

## Errors fail the run loudly

A step raising anything marks the run `failed` with a public message and stops.
Nothing is retried here -- `AIRouter` owns retries for AI calls, and a runner
retrying on top of that would multiply a ceiling nobody wrote down
(CLAUDE.md §15a). An execution ceiling tripping is the same path, which is what
"fails loudly rather than silently continuing" means in practice.
"""

from __future__ import annotations

import uuid

from app.ai.governance import ExecutionBudget, GovernanceError
from app.core.logging import get_logger, log_context
from app.repositories.workflows import WorkflowRepository, WorkflowRun
from app.workflows.models import (
    RunNotFoundError,
    RunNotResumableError,
    RunStatus,
    StepContext,
    StepStatus,
    WorkflowDefinition,
    WorkflowError,
)

logger = get_logger(__name__)


class WorkflowRunner:
    """Starts, resumes and approves workflow runs."""

    def __init__(self, repository: WorkflowRepository) -> None:
        """Store the repository every run is persisted through."""
        self._repository = repository

    # -------------------------------------------------------------- start --

    def start(
        self,
        workspace_id: uuid.UUID,
        definition: WorkflowDefinition,
        triggered_by: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> WorkflowRun:
        """Create a run and execute it until it finishes, pauses or fails.

        The **Trigger** phase. The run row is written before any step executes,
        so a crash during the first step still leaves a record.

        Returns:
            The run in whatever state execution left it: `completed`,
            `awaiting_approval`, or `failed`.
        """
        run = self._repository.create_run(
            workspace_id=workspace_id,
            workflow_type=definition.workflow_type,
            definition_version=definition.version,
            triggered_by=triggered_by,
            project_id=project_id,
        )

        logger.info(
            log_context(
                event="workflow_run_started",
                workspace_id=workspace_id,
                run_id=run.id,
                workflow_type=definition.workflow_type,
                definition_version=definition.version,
            )
        )

        return self._execute_from(run, definition, start_index=0)

    # ------------------------------------------------------------- resume --

    def resume(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        definition: WorkflowDefinition,
    ) -> WorkflowRun:
        """Continue a run from its last completed step.

        **Reads persisted state, never memory**, which is what makes a run
        resumable in a process that did not start it.

        A run interrupted mid-step re-executes that step, because a step that did
        not record completion did not commit its result either. That makes step
        execution effectively at-least-once, which every step here is safe under:
        validation and quality checks are pure reads, and planning produces a new
        outline rather than mutating anything.

        ## `failed` is resumable; `completed` is not

        **A failed run is the main thing this method exists for.** [[Workflow
        Engine]]'s Failure Recovery says failed workflows may "pause, retry,
        resume from checkpoints or terminate safely while preserving execution
        history", and a `resume` that refused them would leave every transient
        provider outage as a run the user must recreate from scratch, losing the
        steps that already succeeded.

        Retrying picks up at the failed step, not at the beginning, because
        `next_step_index` counts completed steps and the failed one never
        recorded completion.

        `completed` is refused because there is nothing to continue: resuming it
        would re-execute the whole workflow while reporting itself as a
        continuation.

        Raises:
            RunNotFoundError: no live run matched.
            RunNotResumableError: the run has already completed, or is waiting
                for an approval that resuming does not grant.
        """
        run = self._require_run(workspace_id, run_id)
        status = RunStatus(run.status)

        if status is RunStatus.COMPLETED:
            raise RunNotResumableError(status, "resumed")

        if status is RunStatus.AWAITING_APPROVAL:
            # Resuming is not approving. Letting `resume` clear a gate would mean
            # the gate could be bypassed by anyone who could restart a run --
            # including an automated retry -- which is precisely the control
            # CLAUDE.md §15 puts a human behind.
            raise RunNotResumableError(status, "resumed without approval")

        return self._continue(run, definition)

    # ------------------------------------------------------------ approve --

    def approve(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        definition: WorkflowDefinition,
        approved_by: uuid.UUID,
    ) -> WorkflowRun:
        """Approve the step a run is waiting on and continue executing.

        Authorization is **not** decided here -- `requires(UPDATE_WORKSPACE)` on
        the route has already refused anyone who may not approve. This records
        who approved and proceeds, the same division `ProjectService` keeps
        between the state machine and `AuthorizationService`.

        Raises:
            RunNotFoundError: no live run matched.
            RunNotResumableError: the run is not waiting for approval. Approving
                a running or finished run is a client acting on stale state, and
                answering 409 says so rather than silently doing nothing.
        """
        run = self._require_run(workspace_id, run_id)
        status = RunStatus(run.status)

        if status is not RunStatus.AWAITING_APPROVAL:
            raise RunNotResumableError(status, "approved")

        logger.info(
            log_context(
                event="workflow_run_approved",
                workspace_id=workspace_id,
                run_id=run_id,
                approved_by=approved_by,
            )
        )

        # `approved=True` applies to exactly one step -- the one the run is
        # waiting on. The next gated step stops the run again.
        return self._continue(run, definition, approved=True)

    # ------------------------------------------------------------- shared --

    def _require_run(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> WorkflowRun:
        """Return a live run or raise.

        Raises:
            RunNotFoundError: absent, or hidden by RLS -- deliberately one error.
        """
        run = self._repository.get_run(workspace_id, run_id)

        if run is None:
            raise RunNotFoundError()

        return run

    def _continue(
        self,
        run: WorkflowRun,
        definition: WorkflowDefinition,
        approved: bool = False,
    ) -> WorkflowRun:
        """Resume execution at the first step this run has not completed."""
        start_index = self._repository.next_step_index(run.workspace_id, run.id)

        return self._execute_from(run, definition, start_index, approved=approved, resuming=True)

    def _rebuild_outputs(
        self, run: WorkflowRun, definition: WorkflowDefinition
    ) -> dict[str, object]:
        """Return what earlier steps produced, read back from storage.

        **This is what makes resumption correct rather than merely possible.** A
        run pauses for approval and resumes in a *different request*, so outputs
        held in memory are gone by then -- and a later step reading
        `StepContext.outputs` would find it empty.

        Found by running the real workflow rather than by reasoning about it: the
        planning agent resumed after approval, could not see the validation
        step's result, and failed the run. An earlier version of this method
        returned `{}` and documented that as a harmless limitation. It was not
        harmless; it broke the only workflow that exists.

        Only **completed** steps contribute. A step that failed or is awaiting
        approval produced nothing to read, and including a partial result would
        hand a later step an output its predecessor never actually returned.
        """
        return {
            step.step_name: step.output
            for step in self._repository.list_steps(run.workspace_id, run.id)
            if step.status == StepStatus.COMPLETED
        }

    def _execute_from(
        self,
        run: WorkflowRun,
        definition: WorkflowDefinition,
        start_index: int,
        approved: bool = False,
        resuming: bool = False,
    ) -> WorkflowRun:
        """Run steps from `start_index` until the run finishes, pauses or fails.

        One `ExecutionBudget` for this execution, passed to every step through
        `StepContext`. A budget per step would reset the tally each time and give
        a ten-step workflow ten times the allowance -- the runaway §15a's
        chained-invocation cap exists to prevent.

        A resumed run gets a **fresh** budget, which is deliberate and worth
        stating: the ceiling bounds one *execution*, not the run's whole lifetime.
        A run paused overnight for approval should not fail on wall-clock time
        that elapsed while a human was deciding.
        """
        workspace_id = run.workspace_id
        budget = ExecutionBudget()

        # **A continuing run must have a step left to run**, and the loop below
        # cannot tell that it does not: `range(n, n)` is empty, so execution
        # would fall straight through to the completion path and report a
        # truncated run as `completed` -- claiming work that never happened.
        #
        # Reachable whenever a definition loses steps while a run is paused or
        # failed, which is a real hazard rather than a defensive one: a
        # definition edited without a version bump does exactly this.
        #
        # Scoped to `resuming` deliberately. A fresh run legitimately arrives
        # here with `start_index == 0`, and a run that genuinely finished its
        # last step is `completed` by this same method -- neither is continuing.
        # `step_at` covers an index inside a shorter definition; this covers the
        # boundary it structurally cannot see.
        if resuming and start_index >= len(definition.steps):
            raise WorkflowError(
                f"Run recorded {start_index} completed steps but definition "
                f"'{definition.workflow_type}' v{definition.version} has "
                f"{len(definition.steps)}",
                public_message="This workflow definition has changed and the run cannot continue",
            )

        context_outputs = self._rebuild_outputs(run, definition)

        current = self._repository.update_run_status(
            workspace_id, run.id, RunStatus.RUNNING, started=True
        )

        if current is None:  # pragma: no cover - defensive
            raise RunNotFoundError()

        for index in range(start_index, len(definition.steps)):
            step = definition.step_at(index)

            # The approval gate. Checked before the step runs, so a gated step
            # never executes on the strength of an approval it did not receive.
            if step.requires_approval and not approved:
                self._repository.record_step(
                    workspace_id=workspace_id,
                    run_id=run.id,
                    step_index=index,
                    step_name=step.name,
                    status=StepStatus.AWAITING_APPROVAL,
                    detail="Waiting for approval before this step runs",
                )

                logger.info(
                    log_context(
                        event="workflow_run_awaiting_approval",
                        workspace_id=workspace_id,
                        run_id=run.id,
                        step=step.name,
                        step_index=index,
                    )
                )

                paused = self._repository.update_run_status(
                    workspace_id,
                    run.id,
                    RunStatus.AWAITING_APPROVAL,
                    detail=f"Waiting for approval of '{step.name}'",
                )

                return paused if paused is not None else current

            # An approval covers exactly one step. Cleared immediately so the
            # next gated step stops the run again -- see the module docstring.
            approved = False

            self._repository.record_step(
                workspace_id=workspace_id,
                run_id=run.id,
                step_index=index,
                step_name=step.name,
                status=StepStatus.RUNNING,
                started=True,
            )

            context = StepContext(
                workspace_id=workspace_id,
                run_id=run.id,
                project_id=run.project_id,
                triggered_by=run.triggered_by,
                execution_budget=budget,
                outputs=dict(context_outputs),
            )

            try:
                result = step.execute(context)
            except (WorkflowError, GovernanceError) as error:
                # Expected refusals: a validation failure, a failed quality
                # check, a tripped ceiling, a budget refusal. Each carries a
                # message written to be shown, so it reaches the run row.
                return self._fail(run, index, step.name, error, str(error))
            except Exception as error:
                # Everything else. The run records a generic message and the
                # traceback goes to the log -- an unexpected exception's message
                # is written for an engineer and may carry internal detail
                # (CLAUDE.md §24).
                logger.exception(
                    log_context(
                        event="workflow_step_crashed",
                        workspace_id=workspace_id,
                        run_id=run.id,
                        step=step.name,
                        step_index=index,
                    )
                )
                return self._fail(run, index, step.name, error, "This step failed unexpectedly")

            context_outputs[step.name] = result.output

            self._repository.record_step(
                workspace_id=workspace_id,
                run_id=run.id,
                step_index=index,
                step_name=step.name,
                status=StepStatus.COMPLETED,
                detail=result.detail,
                tokens_used=result.tokens_used,
                # Persisted here, so a resumed run can hand it to a later step.
                output=result.output,
                finished=True,
            )

            logger.info(
                log_context(
                    event="workflow_step_completed",
                    workspace_id=workspace_id,
                    run_id=run.id,
                    step=step.name,
                    step_index=index,
                    tokens=result.tokens_used,
                )
            )

        # The Completion phase.
        logger.info(
            log_context(
                event="workflow_run_completed",
                workspace_id=workspace_id,
                run_id=run.id,
                workflow_type=definition.workflow_type,
            )
        )

        completed = self._repository.update_run_status(
            workspace_id, run.id, RunStatus.COMPLETED, finished=True
        )

        return completed if completed is not None else current

    def _fail(
        self,
        run: WorkflowRun,
        index: int,
        step_name: str,
        error: Exception,
        internal_detail: str,
    ) -> WorkflowRun:
        """Mark a step and its run failed, and return the run.

        The message stored is `public_message` when the error carries one --
        every `WorkflowError` and every `GovernanceError` does -- and a fixed
        string otherwise. An unexpected exception's own message never reaches
        the row, because a run's detail is shown to users.
        """
        message = getattr(error, "public_message", "This step failed unexpectedly")

        logger.warning(
            log_context(
                event="workflow_run_failed",
                workspace_id=run.workspace_id,
                run_id=run.id,
                step=step_name,
                step_index=index,
                cause=type(error).__name__,
            )
        )

        self._repository.record_step(
            workspace_id=run.workspace_id,
            run_id=run.id,
            step_index=index,
            step_name=step_name,
            status=StepStatus.FAILED,
            detail=message,
            finished=True,
        )

        failed = self._repository.update_run_status(
            run.workspace_id, run.id, RunStatus.FAILED, detail=message, finished=True
        )

        if failed is None:  # pragma: no cover - defensive
            raise RunNotFoundError()

        return failed
