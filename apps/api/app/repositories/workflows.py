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

from app.services.project_service import ProjectNotFoundError
from app.workflows.models import RunStatus, StepStatus


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


# Stated once rather than repeated in five queries, so a column added to the
# dataclass and forgotten in one of them is impossible. Column order matches
# `_run_from_row` positionally.
_RUN_COLUMNS = (
    "id, workspace_id, workflow_type, definition_version, status, project_id, "
    "detail, triggered_by, started_at, finished_at, created_at, updated_at, version"
)

_STEP_COLUMNS = (
    "id, workspace_id, run_id, step_index, step_name, status, detail, "
    "tokens_used, output, started_at, finished_at, created_at"
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
    )


class WorkflowRepository:
    """Reaches `workflow_runs` and `workflow_step_runs` over an RLS-subject connection."""

    def __init__(self, connection: psycopg.Connection) -> None:
        """Store the tenant-scoped connection every query runs on."""
        self._connection = connection

    # --------------------------------------------------------------- runs --

    def create_run(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        definition_version: int,
        triggered_by: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> WorkflowRun:
        """Insert a run in `pending` and return it as stored.

        Created *before* execution begins, deliberately: a crash between the
        trigger and the first step then leaves a record of a run that never
        started, rather than leaving nothing at all. An engine that persisted
        only on completion would lose exactly the runs worth investigating.

        Raises:
            ProjectNotFoundError: when `project_id` names a project that is not
                in this workspace. The composite foreign key to
                `(id, workspace_id)` refuses the insert, and translating it here
                is what turns a **500** into the same 404 every other unreachable
                project produces.

                Caught rather than pre-checked with a SELECT: the constraint is
                the actual guarantee, and a check-then-insert would also be a
                race. Found by running a cross-tenant request against a real
                database, where it surfaced as an unhandled `ForeignKeyViolation`.
        """
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO public.workflow_runs
                        (workspace_id, workflow_type, definition_version, status,
                         project_id, triggered_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING {_RUN_COLUMNS}
                    """,  # noqa: S608 - _RUN_COLUMNS is a module constant, not input
                    (
                        workspace_id,
                        workflow_type,
                        definition_version,
                        RunStatus.PENDING,
                        project_id,
                        triggered_by,
                    ),
                )
                row = cursor.fetchone()
        except psycopg.errors.ForeignKeyViolation as error:
            # The composite key to `(id, workspace_id)` refused a project that is
            # not in this workspace -- which is exactly the cross-tenant write it
            # exists to stop. Reported as an unreachable project, the same answer
            # a deleted one gives, so a run id cannot distinguish "another
            # tenant's project" from "no such project".
            raise ProjectNotFoundError(
                f"Project {project_id} is not in workspace {workspace_id}"
            ) from error

        # RLS refusing an INSERT raises rather than returning no row, so this is
        # genuinely defensive.
        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Workflow run insert returned no row")

        return _run_from_row(row)

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
                RETURNING {_RUN_COLUMNS}
                """,  # noqa: S608 - _RUN_COLUMNS is a module constant, not input
                (status, detail, started, finished, run_id, workspace_id),
            )
            row = cursor.fetchone()

        return None if row is None else _run_from_row(row)

    # -------------------------------------------------------------- steps --

    def record_step(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str,
        status: StepStatus,
        detail: str | None = None,
        tokens_used: int = 0,
        output: object = None,
        started: bool = False,
        finished: bool = False,
    ) -> WorkflowStepRun:
        """Insert or update one step's row.

        An upsert on `(run_id, step_index)`, which the unique constraint makes
        possible and which resumability makes necessary: a step that was marked
        `awaiting_approval` and is later executed must *become* completed rather
        than gaining a second row. Two rows for one step would make a run's
        history show the step twice with no indication which one counted.

        `step_name` is deliberately **not** updated on conflict. The stored name
        is what actually ran; if a definition renames a step, the historical row
        keeps describing the run as it happened.

        `output` is serialized as JSON. A step returning something unserializable
        would fail here rather than silently storing nothing -- which is correct:
        a value a later step cannot read back is a value that was never really
        persisted.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO public.workflow_step_runs
                    (workspace_id, run_id, step_index, step_name, status, detail,
                     tokens_used, output, started_at, finished_at)
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s THEN now() ELSE NULL END,
                    CASE WHEN %s THEN now() ELSE NULL END
                )
                ON CONFLICT (run_id, step_index) DO UPDATE
                SET status = EXCLUDED.status,
                    detail = EXCLUDED.detail,
                    tokens_used = EXCLUDED.tokens_used,
                    -- `coalesce` so a later write that carries no output does
                    -- not erase one an earlier write stored. The gate records
                    -- the step before it runs and has nothing to store.
                    output = coalesce(EXCLUDED.output, public.workflow_step_runs.output),
                    started_at = coalesce(
                        public.workflow_step_runs.started_at, EXCLUDED.started_at
                    ),
                    finished_at = coalesce(
                        EXCLUDED.finished_at, public.workflow_step_runs.finished_at
                    )
                RETURNING {_STEP_COLUMNS}
                """,  # noqa: S608 - _STEP_COLUMNS is a module constant, not input
                (
                    workspace_id,
                    run_id,
                    step_index,
                    step_name,
                    status,
                    detail,
                    tokens_used,
                    Json(output) if output is not None else None,
                    started,
                    finished,
                ),
            )
            row = cursor.fetchone()

        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Workflow step upsert returned no row")

        return _step_from_row(row)

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
