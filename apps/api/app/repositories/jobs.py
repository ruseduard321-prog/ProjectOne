"""Enqueues and reads jobs, over the tenant connection.

**Every method here runs on `TenantConnectionDep`**, so RLS enforces the
workspace boundary rather than a `WHERE workspace_id = ...` clause this code
could forget. The workspace id still appears in queries, but as a *filter*, never
as the security control.

This is deliberately **not** where a job's queue state is written. Claiming,
extending a lease and recording an outcome all happen in
`app/repositories/job_dispatch.py`, on the privileged connection, because a
worker must find the next job before it knows whose job it is
([[ADR-005 Async Job Queue and Worker Execution Model]] §5). Keeping the two in
separate modules is what makes that boundary reviewable: the cross-tenant path is
a file, not a method somebody has to notice.

## Enqueueing on the tenant connection is the whole point of a database queue

A job is written in the **same transaction** as the row that motivates it. A
workflow run and its job commit together or neither exists. ADR-005 §1 makes this
the first of the three properties that decided against a broker: every external
queue breaks it, leaving either a run stranded with nothing to advance it or a
job pointing at a run that was rolled back.

## Every query states `deleted_at IS NULL` itself

The SELECT policy does not filter liveness, because a SELECT policy that does
makes soft-deleting the table impossible ([[RLS Policy Pattern]]). Liveness is
therefore this layer's job on every read, and a query that forgets it returns
soft-deleted rows rather than failing -- a silent wrong answer, which is why it
is written into each query rather than centralized in a helper a future query
could bypass.
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg
from psycopg.types.json import Json

from app.jobs.contract import Job, JobStatus

# Stated once rather than repeated in three queries, so a column added to the
# dataclass and forgotten in one of them is impossible. Column order matches
# `_job_from_row` positionally.
#
# `lease_expires_at` is deliberately absent. `authenticated` has no column
# grant for it (ADR-006 §D11), because nothing on this path consumed it --
# it was selected into a field no caller read. Lease arithmetic belongs to
# `job_dispatch.py` on the privileged connection. Adding it back here means
# granting it back first, which is the decision that should be visible.
_JOB_COLUMNS = (
    "id, workspace_id, enqueued_by, job_type, payload, status, attempts, max_attempts, "
    "claimed_by, claimed_at, result, last_error, dead_lettered_at, "
    "correlation_id, created_at, finished_at"
)


def _job_from_row(row: tuple[Any, ...]) -> Job:
    """Build a `Job` from a row selected with `_JOB_COLUMNS`."""
    return Job(
        id=row[0],
        workspace_id=row[1],
        enqueued_by=row[2],
        job_type=row[3],
        payload=row[4] if row[4] is not None else {},
        status=row[5],
        attempts=row[6],
        max_attempts=row[7],
        claimed_by=row[8],
        claimed_at=row[9],
        result=row[10],
        last_error=row[11],
        dead_lettered_at=row[12],
        correlation_id=row[13],
        created_at=row[14],
        finished_at=row[15],
    )


class JobRepository:
    """Reaches `jobs` over an RLS-subject connection."""

    def __init__(self, connection: psycopg.Connection) -> None:
        """Store the tenant-scoped connection every query runs on."""
        self._connection = connection

    def enqueue(
        self,
        workspace_id: uuid.UUID,
        enqueued_by: uuid.UUID,
        job_type: str,
        payload: dict[str, Any],
        max_attempts: int,
        correlation_id: str | None = None,
    ) -> Job:
        """Insert a job in `pending` and return it as stored.

        **`enqueued_by` is not merely recorded, it is the identity the worker
        will later replay** (ADR-005 §4). The INSERT policy pins it to
        `auth.uid()`, so this cannot enqueue work that runs as anybody else --
        including another member of the same workspace, which the workspace
        predicate alone would happily allow.

        `correlation_id` carries the enqueuing request's `X-Request-ID` into the
        worker's logs. Without it an asynchronous failure cannot be traced back
        to what caused it, which [[CLAUDE|CLAUDE.md]] §26 treats as an
        observability gap rather than a missing nicety.

        Raises:
            psycopg.errors.CheckViolation: when `max_attempts` exceeds the
                composed ceiling. Deliberately not caught: the registry refuses
                the same thing at import, so reaching here means the two
                disagree, and that is a defect to surface rather than translate.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO public.jobs
                    (workspace_id, enqueued_by, job_type, payload, status,
                     max_attempts, correlation_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING {_JOB_COLUMNS}
                """,  # noqa: S608 - _JOB_COLUMNS is a module constant, not input
                (
                    workspace_id,
                    enqueued_by,
                    job_type,
                    Json(payload),
                    JobStatus.PENDING,
                    max_attempts,
                    correlation_id,
                ),
            )
            row = cursor.fetchone()

        # RLS refusing an INSERT raises rather than returning no row, so this is
        # genuinely defensive.
        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Job insert returned no row")

        return _job_from_row(row)

    def get(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
        """Return one live job, or None.

        Returns None both when no job exists and when RLS hid it. The two are
        indistinguishable here by design, for the reason `RunNotFoundError`
        gives: a caller must not be able to learn that a job id exists in a
        workspace they cannot see.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_JOB_COLUMNS}
                FROM public.jobs
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """,  # noqa: S608 - _JOB_COLUMNS is a module constant, not input
                (job_id, workspace_id),
            )
            row = cursor.fetchone()

        return None if row is None else _job_from_row(row)

    def list_for_workspace(self, workspace_id: uuid.UUID, limit: int = 50) -> tuple[Job, ...]:
        """Return recent jobs in a workspace, newest first.

        Bounded by `limit` for the same reason `list_runs_for_workspace` is: job
        count grows with *automation* rather than with human effort, so this is a
        collection that genuinely runs away. `created_at DESC, id DESC` gives a
        stable order, so adding keyset pagination later is a change to one query.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_JOB_COLUMNS}
                FROM public.jobs
                WHERE workspace_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,  # noqa: S608 - _JOB_COLUMNS is a module constant, not input
                (workspace_id, limit),
            )
            rows = cursor.fetchall()

        return tuple(_job_from_row(row) for row in rows)
