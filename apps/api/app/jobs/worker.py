"""The worker process: claim, establish tenant context, execute, settle.

Run as `python -m app.jobs.worker`, from the **same image, same package and same
`Settings`** as the API ([[ADR-005 Async Job Queue and Worker Execution Model]]
§3). It is a second process, not a second application: `apps/worker/` was
rejected because a worker needs the services, repositories and session factory
the API already has, and [[CLAUDE|CLAUDE.md]] §8 forbids one app depending on
another.

## The order of operations is the security design

    claim (privileged, commits)
      -> establish the enqueuing user's identity (RLS-subject, proven)
        -> invoke the handler (RLS-subject sessions only)
          -> record the outcome (privileged, commits)

**Nothing between the second and third steps is optional.** ADR-005 §5 constraint
4 requires the user's RLS context to be established *before execution begins*,
and states it as an ordering guarantee rather than an available mechanism: a
handler is never invoked outside a tenant-scoped identity. A job whose identity
cannot be established -- a revoked membership, a deleted user -- fails terminally
here and never reaches its handler at all.

`_establish_identity` is that step, and it *proves* the identity rather than
assuming it: it opens an RLS-subject session and asks the database for the
actor's live role in the job's workspace. A revoked member reads nothing, which
is the answer, and the job is dead-lettered naming revocation rather than
failing obscurely inside a handler that could not see anything.

### Why the tenant session is not held open across the handler

ADR-005 §4 is explicit that the handler "opens **short, discrete** RLS-scoped
transactions for each unit of database work", because a single transaction
spanning a multi-minute render would hold a connection and hold locks through an
upstream call -- exactly what `c8f1a3d54e29` rejected. So the identity is
established and proven in one short session that closes, and the handler is given
a *factory* that opens further short sessions as the same user.

That satisfies both halves of the ADR: constraint 4's ordering guarantee (the
identity is established, and proven, before the handler's first statement) and
§4's transaction shape (no transaction is open while the long work runs). Every
connection a handler can reach is RLS-subject; none is privileged; none is held.

## The retry policy lives here

`classify` says whether a failure is worth another attempt; this module combines
that with how many attempts remain and produces the `JobOutcome` the dispatcher
records. Keeping the decision here rather than in the repository is the same
split `WorkflowRunner` keeps from `WorkflowRepository` -- one place decides, one
place writes.

## One job at a time

The codebase is synchronous throughout, and ADR-005 §3 fixes concurrency at "more
worker processes", not more threads. The single background thread this module
does start is a **lease heartbeat**, which runs no job work at all; it exists so a
long job's lease does not lapse under a worker that is perfectly healthy.
"""

from __future__ import annotations

import os
import signal
import socket
import sys
import threading
import time
import types
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from app.core.api import request_id_var
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger, log_context
from app.jobs.contract import (
    ClaimedJob,
    JobContext,
    JobResult,
    JobStatus,
    TenantContextUnavailableError,
    classify,
)
from app.jobs.registry import JobHandlerRegistry, build_registry
from app.repositories.job_dispatch import JobDispatchRepository, JobOutcome
from app.repositories.memberships import MembershipRepository
from app.repositories.session import RequestSessionFactory

logger = get_logger(__name__)

#: How many consecutive dispatch failures end the process.
#:
#: A worker whose database is unreachable would otherwise poll forever, logging
#: the same error at whatever interval it was configured with -- alive, useless,
#: and green to any check that only asks whether the process exists.
#: [[CLAUDE|CLAUDE.md]] §15a's circuit-breaker principle applies to the loop
#: itself, not only to AI spend: something that keeps failing must stop rather
#: than degrade gracefully into an infinite retry.
#:
#: Exiting non-zero is the loud failure. Restarting with backoff is the
#: platform's job, and which platform is [[STEP-82 Staging Environment and
#: Deployment Pipeline]]'s decision.
MAX_CONSECUTIVE_DISPATCH_FAILURES = 10


def worker_identity() -> str:
    """Return a human-readable identifier for this worker process.

    Host and pid, so an operator reading a claimed row can find the process that
    holds it. Deliberately not a credential and not a secret -- it is written to a
    tenant-readable column, so it must carry nothing that is neither.
    """
    return f"{socket.gethostname()}:{os.getpid()}"


class LeaseHeartbeat:
    """Extends a job's lease while its handler runs.

    ADR-005 §6 requires that "a worker executing a long job extends it
    periodically". Doing that from the worker's own thread is impossible -- it is
    inside the handler -- so this is a daemon thread that does nothing but renew.

    It is **not** in-process job concurrency, which ADR-005 §3 rules out: it runs
    one statement on a bounded interval and executes no handler work.

    A failed extension stops the heartbeat rather than retrying it. Losing the
    lease means another worker has claimed the job, and hammering the row would
    only extend a lease this process no longer owns.
    """

    def __init__(
        self,
        dispatch: JobDispatchRepository,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        lease_seconds: int,
    ) -> None:
        """Prepare a heartbeat for one claim; nothing runs until `start`."""
        self._dispatch = dispatch
        self._job_id = job_id
        self._lease_token = lease_token
        self._lease_seconds = lease_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        # A third of the lease, so two consecutive renewals may fail before the
        # lease actually lapses. Renewing at the lease boundary would make every
        # transient blip a lost lease and a duplicate execution.
        self._interval = max(1.0, lease_seconds / 3)

    @contextmanager
    def running(self) -> Iterator[None]:
        """Run the heartbeat for the duration of the block.

        A context manager so the thread cannot outlive the work it is renewing
        for -- including when the handler raises, which is precisely when a
        forgotten `stop()` would leave a thread extending the lease of a job
        nobody is executing.
        """
        self.start()
        try:
            yield
        finally:
            self.stop()

    def start(self) -> None:
        """Begin renewing, on a daemon thread."""
        # Daemon, so a worker that is killed mid-job does not linger waiting for
        # this thread. Its lease then lapses on its own, which is exactly the
        # recovery path the queue is designed around.
        self._thread = threading.Thread(target=self._loop, name="job-lease-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop renewing and wait briefly for the thread to notice."""
        self._stop.set()

        if self._thread is not None:
            # Bounded join: a heartbeat blocked on an unresponsive database must
            # not stop the worker from settling the job it has already finished.
            self._thread.join(timeout=self._interval)
            self._thread = None

    def _loop(self) -> None:
        """Renew until told to stop, or until the lease is lost."""
        while not self._stop.wait(self._interval):
            try:
                held = self._dispatch.extend_lease(
                    self._job_id, self._lease_token, self._lease_seconds
                )
            except psycopg.Error as error:
                logger.warning(
                    log_context(
                        event="job_lease_extension_failed",
                        job_id=self._job_id,
                        cause=type(error).__name__,
                    )
                )
                return

            if not held:
                logger.warning(
                    log_context(
                        event="job_lease_lost",
                        job_id=self._job_id,
                        detail="another worker now holds this job",
                    )
                )
                return


class JobWorker:
    """Claims one job at a time and runs it under the enqueuing user's identity."""

    def __init__(
        self,
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
        registry: JobHandlerRegistry,
        lease_seconds: int,
        poll_interval_seconds: float,
        worker_id: str | None = None,
    ) -> None:
        """Store the collaborators and the two intervals that pace the loop."""
        self._dispatch = dispatch
        self._sessions = sessions
        self._registry = registry
        self._lease_seconds = lease_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._worker_id = worker_id or worker_identity()

    @property
    def worker_id(self) -> str:
        """Return this process's identifier, as written onto claimed rows."""
        return self._worker_id

    # ---------------------------------------------------------------- loop --

    def run_forever(self, stop: threading.Event | None = None) -> int:
        """Poll until asked to stop, or until dispatch keeps failing.

        Returns:
            A process exit code: 0 for a clean shutdown, 1 when the loop gave up
            after `MAX_CONSECUTIVE_DISPATCH_FAILURES` consecutive failures.
        """
        stopping = stop or threading.Event()
        consecutive_failures = 0

        logger.info(
            log_context(
                event="job_worker_started",
                worker_id=self._worker_id,
                lease_seconds=self._lease_seconds,
                poll_interval_seconds=self._poll_interval_seconds,
                job_types=",".join(self._registry.job_types),
            )
        )

        while not stopping.is_set():
            try:
                worked = self.run_once()
                consecutive_failures = 0
            except psycopg.Error as error:
                consecutive_failures += 1
                logger.error(
                    log_context(
                        event="job_dispatch_failed",
                        worker_id=self._worker_id,
                        cause=type(error).__name__,
                        consecutive_failures=consecutive_failures,
                        ceiling=MAX_CONSECUTIVE_DISPATCH_FAILURES,
                    )
                )

                if consecutive_failures >= MAX_CONSECUTIVE_DISPATCH_FAILURES:
                    logger.error(
                        log_context(
                            event="job_worker_stopped",
                            worker_id=self._worker_id,
                            reason="dispatch_failure_ceiling_reached",
                        )
                    )
                    return 1

                worked = False

            if not worked:
                # Only when the queue was empty (or dispatch failed). A worker
                # that just finished a job asks again immediately, so a backlog
                # drains at the speed of the work rather than of the poll.
                stopping.wait(self._poll_interval_seconds)

        logger.info(
            log_context(event="job_worker_stopped", worker_id=self._worker_id, reason="signalled")
        )

        return 0

    def run_once(self) -> bool:
        """Claim and run at most one job.

        Returns:
            True when a job was claimed and settled, False when the queue held
            nothing claimable.
        """
        claimed, dead_lettered = self._dispatch.claim(self._worker_id, self._lease_seconds)

        for job in dead_lettered:
            # Reaped by this poll: their worker stopped without settling them, so
            # nothing else is left to report them. §26 -- a state change nobody
            # would notice is an observability gap.
            logger.error(
                log_context(
                    event="job_dead_lettered",
                    job_id=job.id,
                    job_type=job.job_type,
                    workspace_id=job.workspace_id,
                    attempts=job.attempts,
                    reason="lease_expired_with_attempts_exhausted",
                )
            )

        if claimed is None:
            return False

        # Bind the enqueuing request's correlation id, so every line this job
        # produces -- including a handler's own logging -- carries the id of the
        # request that caused it. Reset in `finally`: a token left set would
        # attribute the *next* job's lines to this one.
        token = request_id_var.set(claimed.correlation_id or "-")

        try:
            self._process(claimed)
        finally:
            request_id_var.reset(token)

        return True

    # ------------------------------------------------------------ one job --

    def _process(self, claimed: ClaimedJob) -> None:
        """Execute one claimed job and record what happened."""
        started = time.monotonic()

        try:
            self._establish_identity(claimed)
            result = self._execute(claimed)
        except Exception as error:  # noqa: BLE001 - classified below, never swallowed
            outcome = self._failure_outcome(claimed, error)
        else:
            outcome = JobOutcome(
                status=JobStatus.SUCCEEDED,
                result=result.output,
                last_error=None,
            )

        self._settle(claimed, outcome, elapsed=time.monotonic() - started)

    def _establish_identity(self, claimed: ClaimedJob) -> None:
        """Prove the enqueuing user still holds the access this job needs.

        ADR-005 §5 constraint 4, as an ordering guarantee: this runs between the
        claim committing and the handler's first statement, and a handler is
        never invoked if it fails.

        The check is a *read through RLS*, not a privileged lookup, and that is
        the point -- it exercises the same policies the handler's own queries
        will, so a job that passes here is a job whose session genuinely resolves
        to a live member.

        Raises:
            TenantContextUnavailableError: the actor has no live membership in
                the job's workspace. Classified terminal, so the job is
                dead-lettered on this attempt rather than retried -- retrying
                would spend the ceiling re-asking a permission question of a
                database that will keep answering no (ADR-005 §4, §7).
        """
        with self._sessions.authenticated_as(claimed.enqueued_by) as connection:
            role = MembershipRepository(connection).role_in(
                claimed.workspace_id, claimed.enqueued_by
            )

        if role is None:
            raise TenantContextUnavailableError(
                f"User {claimed.enqueued_by} holds no live membership in workspace "
                f"{claimed.workspace_id}; job {claimed.id} will not be executed"
            )

    def _execute(self, claimed: ClaimedJob) -> JobResult:
        """Run the registered handler, with its lease kept alive.

        The handler receives a `JobContext` whose only database access is
        `tenant_session` -- a factory opening RLS-subject sessions as the
        enqueuing user. No privileged connection is passed to it, reachable from
        it, or held open behind it (ADR-005 §5 constraint 3).
        """
        handler = self._registry.get(claimed.job_type)

        context = JobContext(
            job_id=claimed.id,
            workspace_id=claimed.workspace_id,
            enqueued_by=claimed.enqueued_by,
            payload=claimed.payload,
            attempt=claimed.attempt,
            max_attempts=claimed.max_attempts,
            tenant_session=lambda: self._sessions.authenticated_as(claimed.enqueued_by),
        )

        heartbeat = LeaseHeartbeat(
            self._dispatch, claimed.id, claimed.lease_token, self._lease_seconds
        )

        with heartbeat.running():
            return handler.execute(context)

    def _failure_outcome(self, claimed: ClaimedJob, error: BaseException) -> JobOutcome:
        """Decide what a failed attempt becomes, and log it.

        Two questions, in this order:

        1. **Is this failure worth retrying at all?** `classify` answers it, and
           a terminal refusal is dead-lettered immediately however many attempts
           remain -- a budget refusal retried is the refusal repeated.
        2. **Are there attempts left?** A retryable failure on the last attempt
           is dead-lettered too, which is what makes the ceiling a ceiling.

        The message stored is the error's `public_message` where it has one, and
        a fixed string otherwise. An unexpected exception's own text never
        reaches the row: `jobs.last_error` is tenant-readable, and an unexpected
        exception's message is written for an engineer ([[CLAUDE|CLAUDE.md]] §24).
        The full traceback goes to the log.
        """
        retryable = classify(error)
        attempts_left = claimed.attempt < claimed.max_attempts
        message = getattr(error, "public_message", None)

        if message is None:
            # Genuinely unexpected: log the traceback, store nothing from it.
            logger.exception(
                log_context(
                    event="job_crashed",
                    job_id=claimed.id,
                    job_type=claimed.job_type,
                    workspace_id=claimed.workspace_id,
                    attempt=claimed.attempt,
                )
            )
            message = "This job failed unexpectedly"

        if retryable and attempts_left:
            logger.warning(
                log_context(
                    event="job_retry_scheduled",
                    job_id=claimed.id,
                    job_type=claimed.job_type,
                    workspace_id=claimed.workspace_id,
                    attempt=claimed.attempt,
                    max_attempts=claimed.max_attempts,
                    cause=type(error).__name__,
                )
            )

            return JobOutcome(status=JobStatus.PENDING, last_error=message)

        logger.error(
            log_context(
                event="job_dead_lettered",
                job_id=claimed.id,
                job_type=claimed.job_type,
                workspace_id=claimed.workspace_id,
                attempts=claimed.attempt,
                max_attempts=claimed.max_attempts,
                cause=type(error).__name__,
                reason="terminal_failure" if not retryable else "attempts_exhausted",
            )
        )

        return JobOutcome(status=JobStatus.DEAD_LETTERED, last_error=message)

    def _settle(self, claimed: ClaimedJob, outcome: JobOutcome, elapsed: float) -> None:
        """Record the outcome, or report that the lease was lost.

        A settle that affects no rows is not an error to raise -- it is the
        at-least-once case working exactly as ADR-005 §6 describes. This worker's
        lease lapsed, another worker took the job, and this one must not overwrite
        that. Saying so, with the state the job actually reached, is what turns a
        confusing silence into a readable log line.
        """
        held = self._dispatch.record_outcome(claimed.id, claimed.lease_token, outcome)

        if not held:
            logger.warning(
                log_context(
                    event="job_outcome_discarded",
                    job_id=claimed.id,
                    job_type=claimed.job_type,
                    workspace_id=claimed.workspace_id,
                    attempted_status=outcome.status,
                    current_status=self._dispatch.status_of(claimed.id),
                    detail="this worker no longer held the lease",
                )
            )
            return

        if outcome.status is JobStatus.SUCCEEDED:
            logger.info(
                log_context(
                    event="job_succeeded",
                    job_id=claimed.id,
                    job_type=claimed.job_type,
                    workspace_id=claimed.workspace_id,
                    attempt=claimed.attempt,
                    duration_seconds=round(elapsed, 3),
                )
            )


def build_worker(settings: Settings) -> JobWorker:
    """Construct the worker from configuration.

    The composition root for the second process, and the counterpart of
    `create_app`. Everything it needs comes from the same `Settings` the API
    validates, which is what ADR-005 §3's one-image-two-processes model buys.
    """
    return JobWorker(
        dispatch=JobDispatchRepository(settings),
        sessions=RequestSessionFactory(settings),
        registry=build_registry(),
        lease_seconds=settings.job_lease_seconds,
        poll_interval_seconds=settings.job_poll_interval_seconds,
    )


def main() -> int:
    """Start a worker and run until signalled.

    **Configuration is validated with the same strictness as the API**, because
    it is the same `get_settings()`. STEP-28 made object storage a startup
    requirement rather than a first-upload surprise; a worker that touches assets
    and starts without R2 credentials would reproduce exactly the defect that
    change removed, one layer deeper and far less visible (ADR-005 §3). A missing
    variable exits here, at deploy, naming what is absent.

    SIGTERM and SIGINT ask the loop to stop after the current job rather than
    killing it mid-flight. A job interrupted mid-flight is recoverable -- its
    lease lapses and another worker takes it -- but recovering costs an attempt,
    and spending one on an orderly deploy is avoidable waste.

    Returns:
        A process exit code.
    """
    settings = get_settings()
    configure_logging()

    worker = build_worker(settings)
    stopping = threading.Event()

    def request_stop(signal_number: int, _frame: types.FrameType | None) -> None:
        logger.info(
            log_context(
                event="job_worker_shutdown_requested",
                worker_id=worker.worker_id,
                signal=signal.Signals(signal_number).name,
            )
        )
        stopping.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    return worker.run_forever(stopping)


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
