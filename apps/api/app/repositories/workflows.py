"""Reads and writes `workflow_runs` and `workflow_step_runs`.

**Every method here runs over the tenant connection** (`TenantConnectionDep`), so
RLS enforces the workspace boundary rather than a `WHERE workspace_id = ...`
clause this code could forget. The workspace id still appears in queries, but as
a *filter*, never as the security control.

## Every query states `deleted_at IS NULL` itself

Neither table's SELECT policy filters liveness, because a SELECT policy that does
makes soft-deleting the table impossible ([[RLS Policy Pattern]]). Liveness is
therefore this layer's job on **every** read, and a query that forgets it returns
soft-deleted rows rather than failing -- a silent wrong answer, which is why it
is stated in each query rather than centralized in a helper a future query could
bypass.

## This layer decides nothing about execution

It writes the status it is given. Whether a run may move from `awaiting_approval`
to `running` is `WorkflowRunner`'s decision, made before this is called. A
repository that also enforced run rules would be a second place the state machine
lives -- the same split `ProjectRepository` and `ProjectService` use.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import psycopg
from psycopg.types.json import Json

from app.core.security import AuthorizationError
from app.services.project_service import ProjectNotFoundError
from app.workflows.models import (
    RunNotFoundError,
    RunStatus,
    StepApprovalRequiredError,
    StepInterruptedError,
    StepOwnershipLostError,
    StepStatus,
    WorkflowError,
    WorkflowStateConflictError,
)

#: Refusals the five protected commands raise, mirrored from migration
#: `09a247684df7`. A SQLSTATE is a contract; a message is prose and drifts, so
#: nothing here matches on message text -- and nothing here *forwards* the
#: database's message either. Every refusal is re-stated as a fixed public
#: sentence written in Python, which is how ADR-006 D7's "no internal error text
#: reaches any response body" is kept true by construction rather than by care.
SQLSTATE_NOT_FOUND = "WF001"
SQLSTATE_WRONG_STATE = "WF002"
SQLSTATE_APPROVAL_REQUIRED = "WF003"
SQLSTATE_STEP_CLAIMED = "WF004"
SQLSTATE_OWNERSHIP_LOST = "WF005"
SQLSTATE_INSUFFICIENT_PRIVILEGE = "42501"
SQLSTATE_INVALID_PARAMETER = "22023"


def _translate(error: psycopg.Error) -> Exception | None:
    """Return the domain error a command's SQLSTATE means, or None if it is not ours.

    Returning `None` rather than swallowing is the point: a `psycopg.Error` this
    does not recognise is a real database failure and must keep propagating.
    """
    mapped: dict[str, Exception] = {
        SQLSTATE_NOT_FOUND: RunNotFoundError(),
        SQLSTATE_WRONG_STATE: WorkflowStateConflictError(str(error)),
        SQLSTATE_APPROVAL_REQUIRED: StepApprovalRequiredError(str(error)),
        SQLSTATE_STEP_CLAIMED: StepInterruptedError(str(error)),
        SQLSTATE_OWNERSHIP_LOST: StepOwnershipLostError(str(error)),
        # The caller boundary, a lost membership, or the wrong role. All three
        # are "identity is known and the answer is still no", which is the one
        # thing a 403 means.
        SQLSTATE_INSUFFICIENT_PRIVILEGE: AuthorizationError(str(error)),
        SQLSTATE_INVALID_PARAMETER: WorkflowError(str(error)),
    }

    return mapped.get(error.sqlstate or "")


@dataclass(frozen=True)
class WorkflowRun:
    """One run, as stored.

    Frozen because a repository result is a snapshot of what was read. A mutable
    row invites a caller to edit it and expect the database to notice.
    """

    id: uuid.UUID
    workspace_id: uuid.UUID
    workflow_type: str
    definition_version: int
    status: str
    project_id: uuid.UUID | None
    detail: str | None
    triggered_by: uuid.UUID
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True)
class WorkflowStepRun:
    """One step of one run, as stored."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    run_id: uuid.UUID
    step_index: int
    step_name: str
    status: str
    detail: str | None
    tokens_used: int

    #: What the step produced, as stored. Read back on resume so a later step
    #: can see its predecessor's result -- see the migration's docstring for why
    #: holding these only in memory makes resumption incorrect.
    output: object
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    #: Non-null means "approved and unspent". Admission clears it, so a step
    #: that has run carries no grant and cannot be re-entered on the strength of
    #: a decision made about an earlier attempt (ADR-006 D9).
    #:
    #: Readable by a client, unlike the three fencing columns beside it in the
    #: table: it names a workspace member the reader can already see, and
    #: knowing that a step was approved is not a capability to approve one.
    approved_by: uuid.UUID | None


# Stated once rather than repeated in five queries, so a column added to the
# dataclass and forgotten in one of them is impossible. Column order matches
# `_run_from_row` positionally.
_RUN_COLUMNS = (
    "id, workspace_id, workflow_type, definition_version, status, project_id, "
    "detail, triggered_by, started_at, finished_at, created_at, updated_at, version"
)

#: Never `claim_token`, `claimed_by_job_id` or `claimed_by_lease_token`:
#: `authenticated` holds no `SELECT` grant on them, so naming one here would
#: make every read of this table fail with a permission error. That is the
#: intended design rather than an obstacle -- a fencing token a client can read
#: is a capability, not a fence (ADR-006 D11).
_STEP_COLUMNS = (
    "id, workspace_id, run_id, step_index, step_name, status, detail, "
    "tokens_used, output, started_at, finished_at, created_at, approved_by"
)


def _run_from_row(row: tuple[object, ...]) -> WorkflowRun:
    """Build a `WorkflowRun` from a row selected with `_RUN_COLUMNS`."""
    return WorkflowRun(
        id=row[0],  # type: ignore[arg-type]
        workspace_id=row[1],  # type: ignore[arg-type]
        workflow_type=row[2],  # type: ignore[arg-type]
        definition_version=row[3],  # type: ignore[arg-type]
        status=row[4],  # type: ignore[arg-type]
        project_id=row[5],  # type: ignore[arg-type]
        detail=row[6],  # type: ignore[arg-type]
        triggered_by=row[7],  # type: ignore[arg-type]
        started_at=row[8],  # type: ignore[arg-type]
        finished_at=row[9],  # type: ignore[arg-type]
        created_at=row[10],  # type: ignore[arg-type]
        updated_at=row[11],  # type: ignore[arg-type]
        version=row[12],  # type: ignore[arg-type]
    )


def _step_from_row(row: tuple[object, ...]) -> WorkflowStepRun:
    """Build a `WorkflowStepRun` from a row selected with `_STEP_COLUMNS`."""
    return WorkflowStepRun(
        id=row[0],  # type: ignore[arg-type]
        workspace_id=row[1],  # type: ignore[arg-type]
        run_id=row[2],  # type: ignore[arg-type]
        step_index=row[3],  # type: ignore[arg-type]
        step_name=row[4],  # type: ignore[arg-type]
        status=row[5],  # type: ignore[arg-type]
        detail=row[6],  # type: ignore[arg-type]
        tokens_used=row[7],  # type: ignore[arg-type]
        output=row[8],
        started_at=row[9],  # type: ignore[arg-type]
        finished_at=row[10],  # type: ignore[arg-type]
        created_at=row[11],  # type: ignore[arg-type]
        approved_by=row[12],  # type: ignore[arg-type]
    )


class WorkflowRepository:
    """Reaches `workflow_runs` and `workflow_step_runs` over an RLS-subject connection."""

    def __init__(self, connection: psycopg.Connection) -> None:
        """Store the tenant-scoped connection every query runs on."""
        self._connection = connection

    # --------------------------------------------------------------- runs --

    # --------------------------------------------------- protected commands --
    #
    # Five `SECURITY DEFINER` commands, and these thin wrappers around them.
    #
    # **Why the rule is not here.** The application runner and a direct
    # Supabase/PostgREST client are the same database principal: both reach
    # `current_user = authenticated`. No policy, trigger or column grant can
    # separate "the runner writing a claim" from "a member writing a claim",
    # because there is nothing to separate. So the rule moved into the database,
    # `authenticated` lost the direct write, and what is left here is a call and
    # a translation (ADR-006 D11).
    #
    # Each wrapper therefore decides nothing. It passes the caller's domain
    # values, and turns a SQLSTATE into a domain error. Duplicating any of the
    # commands' checks here would create a second answer able to disagree with
    # the first.

    def start_run(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        definition_version: int,
        project_id: uuid.UUID | None = None,
        payload: dict[str, object] | None = None,
        correlation_id: str | None = None,
    ) -> uuid.UUID:
        """Create a run and its execution job, atomically, and return the run id.

        Both inserts happen inside the caller's transaction, so the transactional
        enqueue ADR-005 §1 chose a database-backed queue for is preserved: a run
        with no job, or a job with no run, is not a state this can produce.

        Raises:
            ProjectNotFoundError: when `project_id` names a project that is not
                live in this workspace. The composite foreign key is what
                answers, so a cross-workspace project id fails here rather than
                creating a run pointed at someone else's project.
            AuthorizationError: when the actor holds no live membership.
            WorkflowError: when a domain value is unusable.
        """
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT public.app_start_workflow_run(
                        %s::uuid, %s::text, %s::integer, %s::uuid, %s::jsonb, %s::text
                    )
                    """,
                    (
                        workspace_id,
                        workflow_type,
                        definition_version,
                        project_id,
                        Json(payload or {}),
                        correlation_id,
                    ),
                )
                row = cursor.fetchone()
        except psycopg.errors.ForeignKeyViolation as error:
            raise ProjectNotFoundError(
                f"Project {project_id} is not in workspace {workspace_id}"
            ) from error
        except psycopg.Error as error:
            raise _translate(error) or error from error

        if row is None or row[0] is None:  # pragma: no cover - defensive
            raise RuntimeError("Starting a workflow run returned no id")

        return row[0]  # type: ignore[no-any-return]

    def approve_step(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        step_index: int,
        correlation_id: str | None = None,
    ) -> uuid.UUID:
        """Record the approval grant and enqueue the job that spends it.

        **One transition, never half of one.** A grant written without its job
        would leave a run carrying a live entitlement that some later,
        differently authorized path could spend; the command refuses to produce
        that state, so this cannot either.

        Raises:
            RunNotFoundError: no such run in this workspace.
            WorkflowStateConflictError: the run is not waiting, the step index is
                not the one it is waiting on, or the grant is already spent.
            AuthorizationError: the actor is not an owner or admin here.
        """
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "SELECT public.app_approve_workflow_step("
                    "%s::uuid, %s::uuid, %s::integer, %s::text)",
                    (workspace_id, run_id, step_index, correlation_id),
                )
                row = cursor.fetchone()
        except psycopg.errors.UniqueViolation as error:
            # `uq_jobs_one_live_job_per_workflow_run`. Two approvals raced and
            # this one lost; its grant rolls back with it, so exactly one grant
            # was consumed and exactly one job exists.
            raise WorkflowStateConflictError(f"A job is already live for run {run_id}") from error
        except psycopg.Error as error:
            raise _translate(error) or error from error

        if row is None or row[0] is None:  # pragma: no cover - defensive
            raise RuntimeError("Approving a workflow step returned no job id")

        return row[0]  # type: ignore[no-any-return]

    def recover_run(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        step_index: int,
        step_requires_approval: bool,
        correlation_id: str | None = None,
    ) -> uuid.UUID | None:
        """Supersede a stale claim and put the run back on a path forward.

        Returns the id of the replacement job, or `None` when the interrupted
        step is gated -- in which case the gate is re-armed, nothing is
        enqueued, and continuing needs a fresh approval from an owner or admin.
        **Never neither**: the command completes one of those two transitions or
        changes nothing at all.

        `step_requires_approval` is read from the definition by the caller,
        because whether a step is gated is a property of code rather than of any
        row. The command re-derives *which* step is interrupted under its own
        lock and refuses if that is not the step named, so a stale read cannot
        make it apply the wrong branch.

        Raises:
            RunNotFoundError: no such run in this workspace.
            WorkflowStateConflictError: the run is not `failed`, has no
                incomplete step, or stopped on a different step.
            AuthorizationError: the actor holds no live membership.
        """
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "SELECT public.app_recover_workflow_run("
                    "%s::uuid, %s::uuid, %s::integer, %s::boolean, %s::text)",
                    (workspace_id, run_id, step_index, step_requires_approval, correlation_id),
                )
                row = cursor.fetchone()
        except psycopg.errors.UniqueViolation as error:
            raise WorkflowStateConflictError(f"A job is already live for run {run_id}") from error
        except psycopg.Error as error:
            raise _translate(error) or error from error

        return None if row is None else row[0]

    def admit_step(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str,
        requires_approval: bool,
        replayable: bool,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
    ) -> uuid.UUID | None:
        """Enter a step, and return the claim token protecting it.

        Returns `None` for a replayable step, which is admitted without a claim
        because there is no external effect for one to protect.

        **This commits before the provider is called.** The claim is durable
        state, not a held lock, which is what lets the long work run with no row
        locked underneath it.

        Raises:
            StepApprovalRequiredError: the step is gated and carries no unspent
                grant. The runner turns this into a pause rather than a failure.
            StepInterruptedError: a non-replayable step is already claimed by
                another execution. Terminal -- never reported as success.
            StepOwnershipLostError: this execution no longer holds the job or
                its lease.
        """
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT public.app_admit_workflow_step(
                        %s::uuid, %s::uuid, %s::integer, %s::text,
                        %s::boolean, %s::boolean, %s::uuid, %s::uuid
                    )
                    """,
                    (
                        workspace_id,
                        run_id,
                        step_index,
                        step_name,
                        requires_approval,
                        replayable,
                        job_id,
                        lease_token,
                    ),
                )
                row = cursor.fetchone()
        except psycopg.Error as error:
            raise _translate(error) or error from error

        return None if row is None else row[0]

    def settle_step(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str,
        status: StepStatus,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        claim_token: uuid.UUID | None = None,
        detail: str | None = None,
        output: object = None,
        tokens_used: int = 0,
    ) -> bool:
        """Persist a step's outcome, if this execution still owns the right to.

        Three predicates, all evaluated with the run, the step and the job
        already locked: the claim is ours, our job's lease has not rotated, and
        the run is not already terminally reconciled.

        Returns:
            False when ownership was lost. **Nothing was written.** The caller
            stops, logs why, and does not retry -- it does not fail the run and
            does not touch the step row, because the claim is the record of what
            was in flight and erasing it would re-open the duplicate call.
        """
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT public.app_settle_workflow_step(
                        %s::uuid, %s::uuid, %s::integer, %s::text, %s::text, %s::text,
                        %s::jsonb, %s::integer, %s::uuid, %s::uuid, %s::uuid
                    )
                    """,
                    (
                        workspace_id,
                        run_id,
                        step_index,
                        step_name,
                        status,
                        detail,
                        Json(output) if output is not None else None,
                        tokens_used,
                        job_id,
                        lease_token,
                        claim_token,
                    ),
                )
                row = cursor.fetchone()
        except psycopg.Error as error:
            raise _translate(error) or error from error

        return bool(row is not None and row[0])

    # ------------------------------------------------------------- reading --

    def get_run(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> WorkflowRun | None:
        """Return one live run, or None.

        Returns None both when no run exists and when RLS hid it. The two are
        indistinguishable here by design.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_RUN_COLUMNS}
                FROM public.workflow_runs
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """,  # noqa: S608 - _RUN_COLUMNS is a module constant, not input
                (run_id, workspace_id),
            )
            row = cursor.fetchone()

        return None if row is None else _run_from_row(row)

    def list_runs_for_workspace(
        self, workspace_id: uuid.UUID, limit: int = 50
    ) -> tuple[WorkflowRun, ...]:
        """Return recent runs in a workspace, newest first.

        Bounded by `limit` rather than unbounded: unlike a workspace's projects,
        run count grows with *automation* rather than with human effort, so this
        is a collection that genuinely runs away. `created_at DESC, id DESC`
        gives a stable order, so adding keyset pagination later is a change to
        one query.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_RUN_COLUMNS}
                FROM public.workflow_runs
                WHERE workspace_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,  # noqa: S608 - _RUN_COLUMNS is a module constant, not input
                (workspace_id, limit),
            )
            rows = cursor.fetchall()

        return tuple(_run_from_row(row) for row in rows)

    def update_run_status(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        status: RunStatus,
        detail: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> WorkflowRun | None:
        """Write a run's status, optionally stamping its start or finish.

        Writes whatever it is given: whether the transition is coherent is
        `WorkflowRunner`'s decision, made before this is called.

        `started_at` uses `coalesce(started_at, now())` so a resumed run keeps
        its **original** start time. Overwriting it would make a run that paused
        for a day's approval look like it took seconds, which is exactly the
        observability question the column exists to answer.

        **A terminal run is never moved, and that is a fence rather than a
        nicety.** Once reconciliation has marked a run `failed` (ADR-006 D5), or
        the runner has completed it, a straggling execution finishing its work
        minutes later must not put it back to `running`. The step-level
        settlement is fenced three ways; this is the same guarantee for the row
        that fencing does not otherwise reach. Recovery moves a `failed` run
        again, and it does so through `app_recover_workflow_run`, which is
        authorized and audited rather than incidental.

        Returns:
            The updated run, or None when no live, non-terminal run matched.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE public.workflow_runs
                SET status = %s,
                    detail = %s,
                    started_at = CASE WHEN %s THEN coalesce(started_at, now()) ELSE started_at END,
                    finished_at = CASE WHEN %s THEN now() ELSE finished_at END
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                  AND status NOT IN (%s, %s)
                RETURNING {_RUN_COLUMNS}
                """,  # noqa: S608 - _RUN_COLUMNS is a module constant, not input
                (
                    status,
                    detail,
                    started,
                    finished,
                    run_id,
                    workspace_id,
                    RunStatus.COMPLETED,
                    RunStatus.FAILED,
                ),
            )
            row = cursor.fetchone()

        return None if row is None else _run_from_row(row)

    # -------------------------------------------------------------- steps --

    def get_step(
        self, workspace_id: uuid.UUID, run_id: uuid.UUID, step_index: int
    ) -> WorkflowStepRun | None:
        """Return one step of a run, or None when it has not been recorded yet."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_STEP_COLUMNS}
                FROM public.workflow_step_runs
                WHERE run_id = %s AND workspace_id = %s AND step_index = %s
                  AND deleted_at IS NULL
                """,  # noqa: S608 - _STEP_COLUMNS is a module constant, not input
                (run_id, workspace_id, step_index),
            )
            row = cursor.fetchone()

        return None if row is None else _step_from_row(row)

    def first_incomplete_step(
        self, workspace_id: uuid.UUID, run_id: uuid.UUID
    ) -> WorkflowStepRun | None:
        """Return the lowest-indexed step this run has not completed.

        The step a recovery would re-enter, and the step an approval would be
        about. Read here so the route can ask the definition whether that step
        is gated; the commands re-derive it under their own locks and refuse if
        the answer moved, so this read is never load-bearing on its own.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_STEP_COLUMNS}
                FROM public.workflow_step_runs
                WHERE run_id = %s AND workspace_id = %s AND deleted_at IS NULL
                  AND status <> %s
                ORDER BY step_index
                LIMIT 1
                """,  # noqa: S608 - _STEP_COLUMNS is a module constant, not input
                (run_id, workspace_id, StepStatus.COMPLETED),
            )
            row = cursor.fetchone()

        return None if row is None else _step_from_row(row)

    def list_steps(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> tuple[WorkflowStepRun, ...]:
        """Return a run's steps in execution order.

        Ordered by `step_index` rather than by time: two steps completing inside
        one transaction share a timestamp, and the index is the definition's own
        ordering rather than an approximation of it.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_STEP_COLUMNS}
                FROM public.workflow_step_runs
                WHERE run_id = %s AND workspace_id = %s AND deleted_at IS NULL
                ORDER BY step_index
                """,  # noqa: S608 - _STEP_COLUMNS is a module constant, not input
                (run_id, workspace_id),
            )
            rows = cursor.fetchall()

        return tuple(_step_from_row(row) for row in rows)

    def next_step_index(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> int:
        """Return the index of the first step this run has not completed.

        **This is the resumability query**, and it reads persisted state rather
        than any in-memory record -- which is what makes a run resumable after
        the process that started it is gone.

        Counts only `completed` steps. A step left `running` by a crash, or
        `awaiting_approval` by a gate, is therefore the next one to execute:
        re-running an interrupted step is correct because a step that did not
        record completion did not commit its result either.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM public.workflow_step_runs
                WHERE run_id = %s
                  AND workspace_id = %s
                  AND deleted_at IS NULL
                  AND status = %s
                """,
                (run_id, workspace_id, StepStatus.COMPLETED),
            )
            row = cursor.fetchone()

        return 0 if row is None else int(row[0])
