"""The dispatcher: the one documented cross-tenant path in ProjectOne.

**Read this before changing anything in it.** Every other repository that reaches
a tenant table does so over an RLS-subject connection, and this one deliberately
does not. [[ADR-005 Async Job Queue and Worker Execution Model]] §5 authorizes
that exception, states why it is irreducible, and bounds it with six constraints
that this module exists to satisfy.

## Why the exception is irreducible

There is exactly one cross-tenant operation in any queue: **a worker must find
the next job before it knows whose job it is.** The dispatch query cannot be
RLS-scoped, because the identity that would scope it is the answer the query
returns. No arrangement of policies removes that; a worker with no identity
matches no policy and reads nothing at all.

## The six constraints, and where each is met

1. **One table.** `public.jobs`, never joined to a tenant table -- every
   statement below.
2. **Three operations, not a connection handed out.** `claim`, `extend_lease`,
   `record_outcome`.
3. **No privileged connection passed to, reachable from, or held open during
   handler code.** `_connect` closes on every exit path, and `ClaimedJob`
   carries no connection.
4. **The user's RLS context is established before execution begins.** In
   `app/jobs/worker.py`, which is the only place a handler is invoked.
5. **Every claim is logged.** In `claim` below.
6. **The `jobs` table still carries RLS.** Migration `a1b7c3e94f6d`.

**Constraints 1, 3 and 4 are proven by test rather than by inspection**
(`tests/test_job_boundary.py`), because ADR-005 §5 requires it: a boundary
asserted only in prose is one the next handler's author can cross without
noticing.

## What leaves this module

A job id, a workspace id, a user id, a job type, an opaque payload and a lease
token -- `ClaimedJob`, and nothing wider. It is deliberately not the `Job`
dataclass: a column added to `jobs` later would then silently widen what crosses
the boundary.

## Why a privileged connection rather than a role of its own

The same reasoning `AISpendRepository` records. A control that must work whether
or not any particular caller can see the row cannot be scoped by that caller, and
inventing a second principal for it would be a new, permanent, highly-privileged
identity in the platform -- which ADR-005 §Alternatives rejected explicitly, for
the workspace-claim design, on exactly those grounds.

## Transaction shape

Each operation is one short unit of work on its own connection, committed and
closed. **The claim commits before the handler runs** (ADR-005 §4 and the
precedent in `c8f1a3d54e29`), so the long work executes with no transaction open
and no row locked -- a row held for the duration of an upstream call is how a
cost control becomes a bottleneck.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Json

from app.core.config import Settings
from app.core.logging import get_logger, log_context
from app.jobs.contract import ClaimedJob, JobStatus

logger = get_logger(__name__)


@dataclass(frozen=True)
class DeadLetteredJob:
    """A job the dispatcher retired without a worker settling it.

    Returned by `claim` so the caller can emit one observability event per
    dead-letter ([[CLAUDE|CLAUDE.md]] §26). These are the jobs whose worker died:
    nothing is left running to report them, so if the reap did not surface them
    they would be a silent state change -- exactly the "system that can fail in a
    way nobody would notice" §26 names.
    """

    id: uuid.UUID
    workspace_id: uuid.UUID
    job_type: str
    attempts: int


@dataclass(frozen=True)
class JobOutcome:
    """The settled result of one attempt, as the dispatcher will record it.

    Built by the worker, which owns the policy decision -- whether a failure is
    retryable, and whether any attempts remain. This repository writes what it is
    given and decides nothing, the same split `WorkflowRepository` keeps from
    `WorkflowRunner`.
    """

    status: JobStatus
    result: Any = None
    last_error: str | None = None


class JobDispatchRepository:
    """Claims jobs, extends leases and records outcomes, on the privileged connection."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding the privileged connection string."""
        self._settings = settings

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection]:
        """Yield a privileged connection, committing on clean exit.

        Closed rather than pooled, and closed on **every** exit path. Constraint
        3 of ADR-005 §5 is about more than not passing a connection to a handler:
        no privileged connection may be *held open during* handler code either,
        and the way to guarantee that is for the connection's lifetime to end
        with the statement rather than with the worker.
        """
        connection = psycopg.connect(
            self._settings.database_url.get_secret_value(),
            connect_timeout=self._settings.database_health_timeout_seconds,
        )

        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def claim(
        self,
        worker_id: str,
        lease_seconds: int,
    ) -> tuple[ClaimedJob | None, tuple[DeadLetteredJob, ...]]:
        """Take exclusive right to run the next job, or return None.

        ## The claim itself

        `SELECT ... FOR UPDATE SKIP LOCKED` followed by a conditional `UPDATE`,
        which is the shape ADR-005 §1 chose and which `c8f1a3d54e29` already
        proved against real PostgreSQL with four concurrent callers. `SKIP
        LOCKED` is what makes concurrency work rather than serialize: two workers
        polling at the same instant each receive a *different* row, and neither
        waits on the other.

        Ordered by `created_at, id` -- oldest first, with `id` breaking ties so
        two jobs enqueued in the same transaction (sharing `now()`) have a
        deterministic order rather than one PostgreSQL is free to vary.

        ## A job is claimable in two states, not one

            status = 'pending'                                  -- never started, or retrying
            status = 'running' AND lease_expires_at < now()     -- its worker stopped extending

        The second is lease recovery, and **it consumes an attempt** because the
        claim increments `attempts` unconditionally. ADR-005 §6 is explicit about
        why: a worker crash-looping on a job that kills the process would
        otherwise be unbounded -- the one shape where "the process died so it does
        not count" produces an infinite loop with no error to observe.

        It is also, unavoidably, the at-least-once case: the job becomes
        claimable while the original worker may still be running it. The
        `lease_token` is what keeps that survivable -- the superseded worker's
        eventual `record_outcome` matches zero rows.

        ## Reaping runs first, inside the same transaction

        A job whose attempts are exhausted is not claimable, so without a reap it
        would sit in `running` with a lapsed lease forever: invisible, unfinished
        and never dead-lettered. Retiring those rows is part of *finding the next
        job* rather than a fourth operation, which is why it lives here and why
        ADR-005 §5's "three statements" still describes this module honestly --
        three operations, one of which needs two statements to be correct.

        Returns:
            The claimed job (or None when the queue is empty) and every job this
            call dead-lettered, so the caller can log each one.
        """
        token = uuid.uuid4()

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.jobs
                SET status = %s,
                    dead_lettered_at = now(),
                    finished_at = now(),
                    last_error = coalesce(
                        last_error,
                        'The worker holding this job stopped without recording an outcome'
                    ),
                    claimed_by = NULL,
                    claimed_at = NULL,
                    lease_expires_at = NULL,
                    lease_token = NULL
                WHERE deleted_at IS NULL
                  AND status IN (%s, %s)
                  AND attempts >= max_attempts
                  AND (status = %s OR lease_expires_at IS NULL OR lease_expires_at < now())
                RETURNING id, workspace_id, job_type, attempts
                """,
                (
                    JobStatus.DEAD_LETTERED,
                    JobStatus.PENDING,
                    JobStatus.RUNNING,
                    JobStatus.PENDING,
                ),
            )
            reaped = tuple(
                DeadLetteredJob(id=row[0], workspace_id=row[1], job_type=row[2], attempts=row[3])
                for row in cursor.fetchall()
            )

            cursor.execute(
                """
                SELECT id
                FROM public.jobs
                WHERE deleted_at IS NULL
                  AND attempts < max_attempts
                  AND (
                      status = %s
                      OR (status = %s AND lease_expires_at IS NOT NULL
                          AND lease_expires_at < now())
                  )
                ORDER BY created_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (JobStatus.PENDING, JobStatus.RUNNING),
            )
            selected = cursor.fetchone()

            if selected is None:
                return None, reaped

            cursor.execute(
                """
                UPDATE public.jobs
                SET status = %s,
                    attempts = attempts + 1,
                    claimed_by = %s,
                    claimed_at = now(),
                    lease_expires_at = now() + make_interval(secs => %s),
                    lease_token = %s
                WHERE id = %s
                RETURNING id, workspace_id, enqueued_by, job_type, payload,
                          attempts, max_attempts, correlation_id
                """,
                (JobStatus.RUNNING, worker_id, lease_seconds, token, selected[0]),
            )
            row = cursor.fetchone()

        if row is None:  # pragma: no cover - the row is locked by this transaction
            raise RuntimeError("Job claim updated no row despite holding its lock")

        claimed = ClaimedJob(
            id=row[0],
            workspace_id=row[1],
            enqueued_by=row[2],
            job_type=row[3],
            payload=row[4] if row[4] is not None else {},
            attempt=row[5],
            max_attempts=row[6],
            correlation_id=row[7],
            lease_token=token,
        )

        # ADR-005 §5 constraint 5: an audited path, not a raw query that skips
        # RLS because it is internal. Every field here is an identifier or a
        # type -- never payload content, which is tenant data and may be
        # anything.
        logger.info(
            log_context(
                event="job_claimed",
                job_id=claimed.id,
                job_type=claimed.job_type,
                workspace_id=claimed.workspace_id,
                worker_id=worker_id,
                attempt=claimed.attempt,
                max_attempts=claimed.max_attempts,
                correlation_id=claimed.correlation_id,
            )
        )

        return claimed, reaped

    def extend_lease(self, job_id: uuid.UUID, lease_token: uuid.UUID, lease_seconds: int) -> bool:
        """Push a held lease further out, or report that it is no longer held.

        Scoped by `lease_token`, so a worker whose lease already lapsed cannot
        extend a job another worker has since claimed -- it would otherwise
        reclaim ownership of work it no longer owns, which is worse than the
        duplicate execution the lease is managing.

        Returns:
            True while this claim still holds the job. False means the lease was
            lost, and the caller should stop: something else owns the job now.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.jobs
                SET lease_expires_at = now() + make_interval(secs => %s)
                WHERE id = %s
                  AND lease_token = %s
                  AND status = %s
                RETURNING id
                """,
                (lease_seconds, job_id, lease_token, JobStatus.RUNNING),
            )

            return cursor.fetchone() is not None

    def record_outcome(
        self,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        outcome: JobOutcome,
    ) -> bool:
        """Settle one attempt, releasing the lease.

        Writes whatever it is given: whether a failure was retryable, and whether
        any attempts remained, is the worker's decision made before this is
        called. A repository that also decided that would be a second place the
        retry policy lives.

        Scoped by `lease_token` for the reason `extend_lease` is, and the
        consequence here is sharper: a superseded worker finishing late must not
        overwrite the state of the worker that now owns the job. It affects zero
        rows and is told so.

        The lease fields are cleared on every outcome, including a retry. A
        `pending` row carrying a stale `claimed_by` reads as owned by a worker
        that is not running it, which is precisely the confusion an operator
        looking at a stuck queue does not need.

        Returns:
            True when this claim still held the job.
        """
        finished = outcome.status in (JobStatus.SUCCEEDED, JobStatus.DEAD_LETTERED)

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.jobs
                SET status = %s,
                    -- `::jsonb` explicitly: psycopg sends a `Json` wrapper as
                    -- `json`, and `coalesce` refuses to unify `json` with the
                    -- column's `jsonb`. An INSERT casts on assignment and hides
                    -- this; `coalesce` does not, which is where it surfaced.
                    result = coalesce(%s::jsonb, result),
                    last_error = %s,
                    dead_lettered_at = CASE WHEN %s THEN now() ELSE dead_lettered_at END,
                    finished_at = CASE WHEN %s THEN now() ELSE finished_at END,
                    claimed_by = NULL,
                    claimed_at = NULL,
                    lease_expires_at = NULL,
                    lease_token = NULL
                WHERE id = %s
                  AND lease_token = %s
                  AND status = %s
                RETURNING id
                """,
                (
                    outcome.status,
                    Json(outcome.result) if outcome.result is not None else None,
                    outcome.last_error,
                    outcome.status is JobStatus.DEAD_LETTERED,
                    finished,
                    job_id,
                    lease_token,
                    JobStatus.RUNNING,
                ),
            )

            return cursor.fetchone() is not None

    def status_of(self, job_id: uuid.UUID) -> str | None:
        """Return a job's current state, for the worker's own logging.

        The only read here that is not part of claiming, and it returns a status
        string -- never a row, never tenant data. It exists so a worker that lost
        its lease can say *what* the job became rather than only that its settle
        affected nothing, which is the difference between a diagnosable log line
        and a puzzling one.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM public.jobs WHERE id = %s",
                (job_id,),
            )
            row = cursor.fetchone()

        return None if row is None else str(row[0])
