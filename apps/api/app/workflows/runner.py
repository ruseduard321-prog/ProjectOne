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

## What [[STEP-31 Workflow Async Execution]] changed here, and what it did not

**Execution semantics are unchanged.** Steps still run in order, the gate still
stops the run rather than skipping the step, approval is still per run, and a
failure still fails the run loudly.

**Entry and settlement are not.** A run now executes inside a worker, where
delivery is at-least-once: a job's lease can lapse under a worker that is still
running it, so two executions of one run can be alive at once
([[ADR-005 Async Job Queue and Worker Execution Model]] §6). `next_step_index`
makes a *sequential* redelivery resume rather than restart and says nothing about
that case. So a step is now **admitted** before it runs and **settled** after,
through two protected commands that hold the fences
([[ADR-006 Workflow Async Execution and Run Reconciliation]] D8).

## Why the runner holds no connection, and neither does a step

It is given a session *factory* and opens one short session per unit of database
work. Admission commits before a step executes, so the claim protecting that step
is durable state rather than a held lock -- which is what lets a multi-minute
provider call run with no row locked underneath it (ADR-005 §4).

**The step's own execution holds nothing either**, and that is a stronger
statement than "no row is locked". `RequestSessionFactory` keeps a transaction
open for the life of a session, because `SET LOCAL ROLE` and the local JWT claim
only survive inside one -- so a step handed a connection would leave a
`projectone_api` backend `idle in transaction` for the whole provider call. Steps
are therefore given *readers* that open a session per call and close it
(`app/workflows/execution.py`), and the definition is built before any session is
opened rather than inside one.

What that buys is not tidiness: an open transaction across an external call pins
the vacuum horizon, and `idle_in_transaction_session_timeout` would kill it
*after* the provider had been paid and before the step could settle.
`TestTheProviderCallHoldsNoTenantConnection` in `tests/test_workflows_api.py`
asserts it against `pg_stat_activity` while a real call is in flight.

## Persist after every step, not at the end

Each step's outcome is written before the next one starts. That is the whole
resumability mechanism: the last committed row is always an honest answer to
"where did this run get to", including when the answer is "it stopped during
step 3".

## A step outcome and the run transition it causes are one transaction

**The last committed row must be an honest answer, and two transactions could
not guarantee that.** Settling a step and then moving the run in a second
transaction leaves a gap, and the gap is reachable because a lease can rotate
inside it:

- the final step commits `completed` while its run is still `running`, and a
  replacement seeing every step complete can reconcile that run to `failed`;
- a non-replayable step commits `failed` with its claim cleared, and a
  replacement arriving before the run turns `failed` can admit and **re-execute
  a step that has already been paid for**;
- any observer -- a poll, the UI, a support query -- can read a step and a run
  that contradict each other.

So `_settle` performs both writes in one session, which is one transaction.
`app_settle_workflow_step` locks the run, the step and the job, and PostgreSQL
holds those locks until the *transaction* ends rather than until the function
returns -- so both writes happen with every relevant row still locked. If the run
transition cannot be written, the step settlement rolls back with it.

An intermediate successful step moves no run state and passes none: the run is
`running` and stays `running`.

## A redelivery of a run that already completed is a success

Delivery is at-least-once, so a job whose earlier delivery finished the run can
arrive again. That is not a failure and is not dead-lettered: no provider is
called, no row is touched, and the job settles `succeeded`.

## The approval gate stops the run, it does not skip the step

Reaching a step with `requires_approval` and no **unspent, durable** grant marks
the step and the run `awaiting_approval` and returns. Nothing is executed.

The grant is now a persisted column rather than an in-memory flag, because the
approving request and the executing process are no longer the same process
(ADR-006 D9). It is spent at admission, so an interrupted gated step has already
consumed its approval and cannot restart without a fresh one. **Approval is never
inferred** -- there is nothing left to infer it from.

## Losing ownership writes nothing at all

A settlement that returns false means this execution no longer owns what it was
doing: another worker holds the job, or the run has already been reconciled. The
runner stops, logs, and **writes nothing** -- it does not fail the run and does
not touch the step row, because the claim is the record of what was in flight and
erasing it would re-open the double call it exists to prevent.

## Errors fail the run loudly

A step raising anything marks the run `failed` with a public message and stops.
Nothing is retried here -- `AIRouter` owns retries for AI calls and the job owns
retries for the job, and a third loop in between would multiply a ceiling nobody
wrote down (CLAUDE.md §15a).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

import psycopg

from app.ai.governance import ExecutionBudget, GovernanceError
from app.core.logging import get_logger, log_context
from app.repositories.session import TenantSessionFactory
from app.repositories.workflows import WorkflowRepository, WorkflowRun
from app.workflows.models import (
    RunNotFoundError,
    RunStatus,
    StepApprovalRequiredError,
    StepContext,
    StepOwnershipLostError,
    StepStatus,
    WorkflowDefinition,
    WorkflowError,
    ensure_definition_matches,
)

logger = get_logger(__name__)

#: How the runner obtains a definition scoped to one tenant.
#:
#: A factory rather than a definition, because a definition holds steps and steps
#: hold tenant-scoped services -- see `app/workflows/definitions.py`, which
#: explains why a module-level definition would be a cross-tenant leak.
#:
#: It takes a **session factory, not a connection**. A definition that held a
#: connection would hold it across the provider call, and the runner would have to
#: choose between rebuilding one per step and leaving a transaction open through a
#: network round trip. Taking the factory removes the choice: one definition is
#: built per execution, before any session exists, and each read inside it opens
#: and closes its own.
WorkflowDefinitionFactory = Callable[[TenantSessionFactory], WorkflowDefinition]

#: Given a workflow type, return the factory that builds it.
#:
#: Two levels because a run's type is a fact about the run, readable only once
#: there is a session to read it in -- so it cannot be bound when a handler is
#: constructed at process start. `app/workflows/execution.py` supplies the one
#: implementation; the alias lives here so that module can import it without
#: this one importing that one.
WorkflowDefinitionsFactory = Callable[[str], WorkflowDefinitionFactory]


@dataclass(frozen=True)
class _Settlement:
    """What one settlement transaction did.

    `settled` is False only when a fence refused the write -- another execution
    holds the job, or the run is already terminal. `run` carries the run as it
    stands afterwards, and is None where the outcome moved no run state.
    """

    settled: bool
    run: WorkflowRun | None


class WorkflowRunner:
    """Drives one workflow run from where it is to where it can next stop."""

    def __init__(
        self,
        sessions: TenantSessionFactory,
        repositories: Callable[[psycopg.Connection], WorkflowRepository] = WorkflowRepository,
    ) -> None:
        """Store how this runner opens sessions and builds repositories over them.

        `repositories` defaults to the real class and exists as a seam: the
        engine's rules -- step order, the gate, budgets, failure -- are decidable
        without SQL, and a suite needing PostgreSQL to prove "a gated step does
        not execute without approval" is a suite nobody runs locally. The
        fencing itself is not decidable without a database and is proven against
        one in `test_workflow_commands.py`.
        """
        self._sessions = sessions
        self._repositories = repositories

    # ------------------------------------------------------------ executing --

    def execute(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        definitions: WorkflowDefinitionsFactory,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
    ) -> WorkflowRun:
        """Advance a run until it completes, pauses for approval, or fails.

        The single entry point. There is no `start`, `resume` or `approve` here
        any more: creating a run, granting an approval and recovering an
        interrupted one are complete domain transitions that must be atomic with
        the job they enqueue, so they live in the protected commands the routes
        call (ADR-006 D11). What is left for the runner is execution.

        Args:
            workspace_id: the run's workspace, already proven to the worker.
            run_id: taken from `jobs.workflow_run_id`, never from a payload.
            definitions: resolves a workflow type to a factory that builds its
                definition against a live tenant connection.
            job_id: the job this execution is delivering.
            lease_token: proof that this execution currently holds that job.

        Returns:
            The run as persisted when execution stopped.

        Raises:
            RunNotFoundError: the run is not visible to this actor.
            StepInterruptedError: a non-replayable step is held by another
                execution. Terminal, and never reported as success.
            StepOwnershipLostError: this execution lost the job or its lease, so
                nothing it did will land.
            WorkflowError: the definition no longer matches the run.
        """
        with self._sessions() as connection:
            repository = self._repositories(connection)
            run = repository.get_run(workspace_id, run_id)

            if run is None:
                raise RunNotFoundError()

            if RunStatus(run.status) is RunStatus.COMPLETED:
                # **An idempotent success, not a failure.** Delivery is
                # at-least-once, so the ordinary way to arrive here is a
                # redelivery of a job whose earlier delivery already finished the
                # run -- the lease lapsed after the work was done rather than
                # before. Nothing is left to do and nothing is wrong: no provider
                # is called, no row is touched, and the job settles `succeeded`.
                #
                # Dead-lettering instead would be worse than noise. It would mark
                # a run that genuinely completed as having a failed job against
                # it, and D5's reconciliation would then be the only thing
                # standing between that and a `completed` run being rewritten to
                # `failed`.
                logger.info(
                    log_context(
                        event="workflow_run_already_completed",
                        workspace_id=workspace_id,
                        run_id=run_id,
                        job_id=job_id,
                    )
                )

                return run

            start_index = repository.next_step_index(workspace_id, run_id)
            outputs = self._rebuild_outputs(repository, run)

        # Built after the session closes, deliberately. A definition holds no
        # connection now, so there is nothing to bind it to one for -- and
        # building it out here is what makes "no step holds a connection" a
        # property of the code rather than of every step's good behaviour.
        definition = definitions(run.workflow_type)(self._sessions)

        # Before anything is admitted, claimed or spent. A run that outlived its
        # definition stops here with its state untouched, for a person to decide
        # about (`ensure_definition_matches`).
        ensure_definition_matches(definition, run.workflow_type, run.definition_version)

        if start_index >= len(definition.steps):
            raise WorkflowError(
                f"Run recorded {start_index} completed steps but definition "
                f"'{definition.workflow_type}' v{definition.version} has "
                f"{len(definition.steps)}",
                public_message="This workflow definition has changed and the run cannot continue",
            )

        return self._execute_from(
            run=run,
            definition=definition,
            start_index=start_index,
            outputs=outputs,
            job_id=job_id,
            lease_token=lease_token,
        )

    # ------------------------------------------------------------ internals --

    def _rebuild_outputs(
        self, repository: WorkflowRepository, run: WorkflowRun
    ) -> dict[str, object]:
        """Return every completed step's stored output, keyed by step name.

        A run resuming in a different process has no in-memory outputs, and a
        later step reading `StepContext.outputs` would find it empty -- the
        defect `workflow_step_runs.output` exists to have fixed.
        """
        return {
            step.step_name: step.output
            for step in repository.list_steps(run.workspace_id, run.id)
            if step.status == StepStatus.COMPLETED
        }

    def _execute_from(
        self,
        run: WorkflowRun,
        definition: WorkflowDefinition,
        start_index: int,
        outputs: dict[str, object],
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
    ) -> WorkflowRun:
        """Run every step from `start_index`, stopping at the first that cannot proceed."""
        workspace_id = run.workspace_id

        # One budget per execution, and a redelivery gets a fresh one by design:
        # it bounds a single execution's wall clock and tokens, not a run's
        # lifetime cost. The workspace spend ceiling is what bounds that, and the
        # two are deliberately not the same control (CLAUDE.md §15a).
        budget = ExecutionBudget()

        with self._sessions() as connection:
            current = self._repositories(connection).update_run_status(
                workspace_id, run.id, RunStatus.RUNNING, started=True
            )

        if current is None:
            # The run is terminal, soft-deleted, or no longer visible. All three
            # mean this execution has nothing left to advance.
            raise StepOwnershipLostError(
                f"Run {run.id} could not be moved to running; it is terminal or gone"
            )

        for index in range(start_index, len(definition.steps)):
            step = definition.step_at(index)

            try:
                claim = self._admit(
                    run=run,
                    index=index,
                    step_name=step.name,
                    requires_approval=step.requires_approval,
                    replayable=step.replayable,
                    job_id=job_id,
                    lease_token=lease_token,
                )
            except StepApprovalRequiredError:
                return self._pause_for_approval(
                    run=run,
                    index=index,
                    step_name=step.name,
                    job_id=job_id,
                    lease_token=lease_token,
                    current=current,
                )

            context = StepContext(
                workspace_id=workspace_id,
                run_id=run.id,
                project_id=run.project_id,
                triggered_by=run.triggered_by,
                execution_budget=budget,
                outputs=dict(outputs),
            )

            try:
                # No session wrapper, and that is the point. Whatever this step
                # reads, it reads through a reader that opens and closes its own
                # -- so the provider call inside it holds no connection and no
                # transaction (ADR-005 §4).
                result = step.execute(context)
            except (WorkflowError, GovernanceError) as error:
                # The engine's own refusals and the governance ceilings. Both are
                # settled facts, and both carry a public message already written
                # for a user.
                return self._fail(run, index, step.name, error, job_id, lease_token, claim)
            except Exception as error:  # noqa: BLE001 - failed below, never swallowed
                logger.exception(
                    log_context(
                        event="workflow_step_crashed",
                        workspace_id=workspace_id,
                        run_id=run.id,
                        step=step.name,
                        step_index=index,
                    )
                )
                return self._fail(run, index, step.name, error, job_id, lease_token, claim)

            outputs[step.name] = result.output

            # The last step's success and the run's completion are one write.
            # An intermediate step moves no run state -- the run is `running`
            # and stays there -- so it passes no run status at all.
            final = index == len(definition.steps) - 1

            settlement = self._settle(
                run=run,
                index=index,
                step_name=step.name,
                status=StepStatus.COMPLETED,
                job_id=job_id,
                lease_token=lease_token,
                claim_token=claim,
                detail=result.detail,
                output=result.output,
                tokens_used=result.tokens_used,
                run_status=RunStatus.COMPLETED if final else None,
                run_finished=final,
            )

            if not settlement.settled:
                raise StepOwnershipLostError(
                    f"Step {index} of run {run.id} could not be settled; "
                    "this execution no longer owns it"
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

        logger.info(
            log_context(
                event="workflow_run_completed",
                workspace_id=workspace_id,
                run_id=run.id,
                workflow_type=definition.workflow_type,
            )
        )

        # No write here. The run reached `completed` in the same transaction as
        # its final step, which is what stops a replacement from ever seeing
        # every step complete under a run that is still `running`.
        return settlement.run if settlement.run is not None else current

    def _admit(
        self,
        run: WorkflowRun,
        index: int,
        step_name: str,
        requires_approval: bool,
        replayable: bool,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
    ) -> uuid.UUID | None:
        """Enter a step, returning the claim token protecting it, or None.

        Raises:
            StepApprovalRequiredError: the gate is unmet; the caller pauses.
            StepInterruptedError: another execution holds this step.
            StepOwnershipLostError: this execution lost its job or lease.
        """
        with self._sessions() as connection:
            claim = self._repositories(connection).admit_step(
                workspace_id=run.workspace_id,
                run_id=run.id,
                step_index=index,
                step_name=step_name,
                requires_approval=requires_approval,
                replayable=replayable,
                job_id=job_id,
                lease_token=lease_token,
            )

        logger.info(
            log_context(
                event="workflow_step_claimed" if claim is not None else "workflow_step_admitted",
                workspace_id=run.workspace_id,
                run_id=run.id,
                step=step_name,
                step_index=index,
                job_id=job_id,
                replayable=claim is None,
            )
        )

        return claim

    def _settle(
        self,
        run: WorkflowRun,
        index: int,
        step_name: str,
        status: StepStatus,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        claim_token: uuid.UUID | None,
        detail: str | None = None,
        output: object = None,
        tokens_used: int = 0,
        run_status: RunStatus | None = None,
        run_detail: str | None = None,
        run_finished: bool = False,
    ) -> _Settlement:
        """Persist a step's outcome, and the run transition it causes, together.

        **One transaction, and that is the whole point of this method.** A step
        outcome and the run state it implies used to be two transactions with a
        commit between them, and the gap was reachable: the lease can rotate
        inside it. Three concrete losses followed.

        The final step committed `completed` while its run was still `running`,
        so a replacement seeing every step complete could reconcile that run to
        `failed`. A non-replayable step committed `failed` with its claim
        cleared, and a replacement arriving before the run turned `failed` could
        admit and **re-execute a step that had already been paid for**. And any
        observer -- a poll, a UI, a support query -- could read a step and a run
        that contradicted each other.

        `app_settle_workflow_step` takes its locks on the run, the step and the
        job, and PostgreSQL holds them to the end of the *transaction*, not the
        end of the function. Doing the run transition in the same transaction
        therefore keeps every one of those rows locked across both writes, so
        there is no instant at which another execution can observe or act on the
        half-applied outcome.

        `run_status` is None for an intermediate successful step, which moves no
        run state: the run is already `running` and stays there.

        Raises:
            StepOwnershipLostError: the step settled but the run transition could
                not be written, because the run went terminal or vanished under
                us. Raised **inside** the transaction, so the step settlement
                rolls back with it and this execution has changed nothing.
        """
        with self._sessions() as connection:
            repository = self._repositories(connection)
            settled = repository.settle_step(
                workspace_id=run.workspace_id,
                run_id=run.id,
                step_index=index,
                step_name=step_name,
                status=status,
                job_id=job_id,
                lease_token=lease_token,
                claim_token=claim_token,
                detail=detail,
                output=output,
                tokens_used=tokens_used,
            )

            if settled and run_status is not None:
                moved = repository.update_run_status(
                    run.workspace_id,
                    run.id,
                    run_status,
                    detail=run_detail,
                    finished=run_finished,
                )

                if moved is None:
                    # Raised here rather than returned, because returning would
                    # commit the step. The step outcome and the run transition
                    # are one decision, so a run that cannot take its half means
                    # the step does not take its half either.
                    raise StepOwnershipLostError(
                        f"Step {index} of run {run.id} settled {status}, but the run "
                        "could not be moved; it is terminal or gone"
                    )

                return _Settlement(settled=True, run=moved)

        if not settled:
            # Carries no token: a fencing value in a log line is a value a log
            # reader holds (ADR-006 I17).
            logger.warning(
                log_context(
                    event="workflow_step_settle_fenced",
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                    step=step_name,
                    step_index=index,
                    job_id=job_id,
                    attempted_status=status,
                    detail="this execution no longer owns the step, the job or the run",
                )
            )

        return _Settlement(settled=settled, run=None)

    def _pause_for_approval(
        self,
        run: WorkflowRun,
        index: int,
        step_name: str,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        current: WorkflowRun,
    ) -> WorkflowRun:
        """Record the run and its step as waiting, and stop.

        Reached when admission refuses under the step's row lock because the gate
        carries no unspent grant. The step is recorded through the same fenced
        settlement every other write uses, so a worker that has lost its job
        cannot park a run it no longer owns.
        """
        settlement = self._settle(
            run=run,
            index=index,
            step_name=step_name,
            status=StepStatus.AWAITING_APPROVAL,
            job_id=job_id,
            lease_token=lease_token,
            claim_token=None,
            detail="Waiting for approval before this step runs",
            run_status=RunStatus.AWAITING_APPROVAL,
            run_detail=f"Waiting for approval of '{step_name}'",
        )

        if not settlement.settled:
            raise StepOwnershipLostError(
                f"Run {run.id} could not be paused at step {index}; "
                "this execution no longer owns it"
            )

        logger.info(
            log_context(
                event="workflow_run_awaiting_approval",
                workspace_id=run.workspace_id,
                run_id=run.id,
                step=step_name,
                step_index=index,
            )
        )

        return settlement.run if settlement.run is not None else current

    def _fail(
        self,
        run: WorkflowRun,
        index: int,
        step_name: str,
        error: Exception,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        claim_token: uuid.UUID | None = None,
    ) -> WorkflowRun:
        """Record a step's failure and fail the run, with a message safe to show.

        `public_message` where the error has one, a fixed sentence where it does
        not. An unexpected exception's own text is written for an engineer and
        this message reaches a user (CLAUDE.md §24).

        The failure is settled through the same three fences as a success: an
        execution that has lost its job does not get to fail a run another worker
        is legitimately advancing.
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

        settlement = self._settle(
            run=run,
            index=index,
            step_name=step_name,
            status=StepStatus.FAILED,
            job_id=job_id,
            lease_token=lease_token,
            claim_token=claim_token,
            detail=message,
            run_status=RunStatus.FAILED,
            run_detail=message,
            run_finished=True,
        )

        if not settlement.settled:
            raise StepOwnershipLostError(
                f"Step {index} of run {run.id} failed, and this execution no longer owns it"
            ) from error

        if settlement.run is None:  # pragma: no cover - settling proved it was live
            raise RunNotFoundError()

        return settlement.run
