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

1. **Two tables, one of them by exactly one statement shape.** Restated by
   [[ADR-006 Workflow Async Execution and Run Reconciliation]] D6 -- see below.
2. **Three operations, not a connection handed out.** `claim`, `extend_lease`,
   `record_outcome`. Two of them carry the reconciliation leg.
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

## The one widening, and exactly how far it goes

ADR-006 D6 replaces constraint 1 with:

> **Two tables, one of them by exactly one statement shape.** The dispatcher
> reads and updates `public.jobs`. It additionally updates
> `public.workflow_runs` in the single reconciliation leg below -- never in any
> other statement, never as a `SELECT`, never returning any column beyond
> `r.id`, and only where the run is named by `jobs.workflow_run_id` and matched
> on the job's own `workspace_id`. It joins to no other tenant table and returns
> no tenant data. **It never touches `workflow_step_runs`.**

**Why this widening and not a narrower one.** A job that dies carrying a
workflow run leaves that run non-terminal with nothing left to advance it -- a
stranded run nobody would notice, which is the CLAUDE.md §26 failure this exists
to remove. Three narrower options were considered and each fails against the
code: reconciling over the *actor's* session cannot work for the case it exists
for (a revoked member's session cannot see the run at all), a second privileged
repository would land the two writes in different transactions, and a sweeper is
not atomic by definition. Widening a stated bound on a connection that already
holds the access was the smaller change than inventing a principal to avoid it.

**Why a data-modifying CTE rather than two statements.** Both are
durable-atomic, but a CTE is atomic *structurally*: there is no ordering to get
right, no early return that can skip the second write, and no future edit that
separates them without visibly rewriting one statement into two.

**What reconciliation never does.** It never touches `workflow_step_runs`, so a
stale claim survives -- as evidence of what was in flight, as a live fence
against the worker that took it, and as the thing standing between the next
delivery and a provider that has already been paid (ADR-006 D5, I10).

`tests/test_job_boundary.py` asserts the count, the shape and the exclusions, so
a third statement naming `workflow_runs` fails the build.

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


#: What a reconciled run's `detail` says when the platform gave up delivering it.
#:
#: **A fixed sentence, never a copy of `jobs.last_error` and never an
#: exception's message.** This column is tenant-readable, and an internal
#: message written for an engineer reaching a user is the defect CLAUDE.md §24
#: exists to prevent (ADR-006 D7).
#:
#: The revoked-actor case is covered by this generic wording for a second reason
#: beyond §24: "the account that started this job no longer has access" is a
#: statement about another member's status, shown to everyone who can see the
#: run. The cause stays in the dead-letter log line.
RUN_ABANDONED_DETAIL = "This run stopped before it finished and could not be completed"

#: The same, for a run whose step was still held when delivery ended.
#:
#: It names the *situation* rather than the cause -- a run that stopped before
#: its last step completed, and can be continued -- because that is what a user
#: needs in order to act.
RUN_INTERRUPTED_DETAIL = (
    "This run stopped before it finished. Resume it to continue from the last completed step."
)


@dataclass(frozen=True)
class SettledOutcome:
    """What settling a job did.

    Two facts rather than one boolean, because "the job was settled" and "a run
    was reconciled with it" answer different questions and the worker logs both
    (ADR-005 §5 constraint 5). `run_reconciled` is a count of rows, never a run's
    data -- the reconciliation leg returns `r.id` and nothing else, and even that
    does not leave this module.
    """

    #: False when this worker no longer held the lease, so nothing was written.
    held: bool

    #: True when a linked workflow run was moved to `failed` in the same commit.
    run_reconciled: bool


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

    #: The run this job was delivering, or None. Reported so the dead-letter log
    #: line says whether a run was reconciled alongside it, rather than leaving
    #: an operator to join two tables to find out (ADR-005 §5 constraint 5).
    workflow_run_id: uuid.UUID | None = None


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

    #: What a linked run's `detail` should say if this outcome ends delivery.
    #:
    #: Chosen by the worker from the two fixed sentences above, by the *type* of
    #: the failure -- never from its text. Ignored unless this outcome
    #: dead-letters a job carrying a `workflow_run_id`.
    run_detail: str = RUN_ABANDONED_DETAIL


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
            # The reap and its reconciliation, as one statement. A job abandoned
            # by a worker that died is exactly the case that used to strand a
            # run: there is no identity here to reconcile it under, and no
            # later delivery to notice.
            cursor.execute(
                """
                WITH settled AS (
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
                    RETURNING id, workspace_id, job_type, attempts, workflow_run_id
                ),
                reconciled AS (
                    UPDATE public.workflow_runs r
                    SET status = 'failed',
                        detail = %s,
                        finished_at = now()
                    FROM settled s
                    WHERE r.id = s.workflow_run_id
                      AND r.workspace_id = s.workspace_id
                      AND r.deleted_at IS NULL
                      AND r.status NOT IN ('completed', 'failed')
                    RETURNING r.id
                )
                SELECT id, workspace_id, job_type, attempts, workflow_run_id FROM settled
                """,
                (
                    JobStatus.DEAD_LETTERED,
                    JobStatus.PENDING,
                    JobStatus.RUNNING,
                    JobStatus.PENDING,
                    RUN_ABANDONED_DETAIL,
                ),
            )
            reaped = tuple(
                DeadLetteredJob(
                    id=row[0],
                    workspace_id=row[1],
                    job_type=row[2],
                    attempts=row[3],
                    workflow_run_id=row[4],
                )
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
                          attempts, max_attempts, correlation_id, workflow_run_id
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
            # Still one table: this column is on `jobs`, read by the same
            # statement that claimed it. What the handler does with it is
            # bounded by its own tenant session, not by this connection.
            workflow_run_id=row[8],
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
    ) -> SettledOutcome:
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

        **A dead-letter carrying a workflow run reconciles that run in the same
        statement** (ADR-006 D5). Every dead-lettered job with a link, not only
        the ones that failed before a handler ran: this connection cannot know
        where a job failed, only that delivery is over, and a run left
        non-terminal when its job is abandoned was abandoned whatever stage it
        reached.

        **The terminal-state guard is the whole safety of that rule.** A run
        already `completed` or `failed` is never touched -- a job that succeeds
        while its run waits at an approval gate is a healthy pause, and a run the
        runner already failed keeps its own, more specific `detail`.

        Returns:
            Whether this claim still held the job, and whether a run was
            reconciled with it.
        """
        finished = outcome.status in (JobStatus.SUCCEEDED, JobStatus.DEAD_LETTERED)
        dead_lettered = outcome.status is JobStatus.DEAD_LETTERED

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                WITH settled AS (
                    UPDATE public.jobs
                    SET status = %s,
                        -- `::jsonb` explicitly: psycopg sends a `Json` wrapper
                        -- as `json`, and `coalesce` refuses to unify `json`
                        -- with the column's `jsonb`. An INSERT casts on
                        -- assignment and hides this; `coalesce` does not, which
                        -- is where it surfaced.
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
                    RETURNING id, workspace_id, workflow_run_id, status
                ),
                reconciled AS (
                    UPDATE public.workflow_runs r
                    SET status = 'failed',
                        detail = %s,
                        finished_at = now()
                    FROM settled s
                    WHERE s.status = 'dead_lettered'
                      AND r.id = s.workflow_run_id
                      AND r.workspace_id = s.workspace_id
                      AND r.deleted_at IS NULL
                      AND r.status NOT IN ('completed', 'failed')
                    RETURNING r.id
                )
                SELECT s.id, (SELECT count(*) FROM reconciled) > 0 FROM settled s
                """,
                (
                    outcome.status,
                    Json(outcome.result) if outcome.result is not None else None,
                    outcome.last_error,
                    dead_lettered,
                    finished,
                    job_id,
                    lease_token,
                    JobStatus.RUNNING,
                    outcome.run_detail,
                ),
            )
            row = cursor.fetchone()

        if row is None:
            return SettledOutcome(held=False, run_reconciled=False)

        return SettledOutcome(held=True, run_reconciled=bool(row[1]))

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
