"""The queue itself, against a real database (STEP-30).

**Every property here is one an offline suite structurally cannot prove.** A dict
has no `FOR UPDATE SKIP LOCKED`, no lease that lapses, no RLS policy and no CHECK
constraint, so a fake would report success for an implementation that duplicates
every job it runs. That is not hypothetical in this codebase: STEP-23's chat
defect shipped green against exactly such a fake.

What only PostgreSQL can answer:

- **Concurrent claims do not collide.** Exactly one worker claims a given job,
  and two workers polling at the same instant get *different* jobs rather than
  queueing behind each other -- `SKIP LOCKED` is what makes the second true, and
  it is the property that makes ADR-005 §3's "concurrency is more processes"
  workable.
- **A job survives the process that enqueued it.** The queue is a table, so this
  is nearly definitional -- and it is the whole reason a database queue was
  chosen, so it is asserted rather than assumed.
- **A lapsed lease returns a job to the queue, and consumes an attempt.**
- **A superseded worker cannot settle or extend a job someone else now holds.**
- **A job whose attempts are exhausted is dead-lettered rather than left
  running**, including when its worker died without recording anything.
- **The tenant boundary holds on the tenant path**, and the write guard holds
  against the one client write the table accepts.
- **The two vocabularies match the database**: `JobStatus` against the CHECK
  constraint, and `MAX_JOB_ATTEMPTS` against the ceiling constraint.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
import pytest

from app.jobs.contract import MAX_JOB_ATTEMPTS, JobStatus
from app.repositories.job_dispatch import JobDispatchRepository, JobOutcome
from app.repositories.jobs import JobRepository
from tests.conftest import Identity, seed_identity

pytestmark = pytest.mark.usefixtures("migrated_database")

#: A lease long enough that nothing lapses by accident during a test run.
LONG_LEASE = 300


class _Secret:
    """Minimal `SecretStr` stand-in exposing only what the repository calls."""

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        """Return the wrapped connection string."""
        return self._value


@pytest.fixture
def dispatch(migrated_database: str) -> JobDispatchRepository:
    """The real dispatcher, pointed at the throwaway database.

    A minimal settings stand-in rather than real `Settings`, matching
    `test_ai_spend_isolation.py` and `test_chat_turn_claims.py`: this suite needs
    no environment beyond the test database URL.
    """

    class _Settings:
        database_url = _Secret(migrated_database)
        database_health_timeout_seconds = 10

    return JobDispatchRepository(_Settings())  # type: ignore[arg-type]


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[tuple[Identity, Identity]]:
    """Seed two unrelated tenants, each owning one workspace."""
    yield seed_identity(admin_connection, "alice"), seed_identity(admin_connection, "bob")


def as_user(url: str, user_id: uuid.UUID) -> psycopg.Connection:
    """Open a connection acting as one authenticated user.

    `SET ROLE` plus the JWT claim, exactly as `RequestSessionFactory` does per
    transaction on a real request -- so what these tests exercise is the policy a
    request actually meets, not a convenient approximation of it.
    """
    connection = psycopg.connect(url)

    with connection.cursor() as cursor:
        cursor.execute("SET ROLE authenticated")
        cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (str(user_id),))

    return connection


@contextmanager
def session_as(url: str, user_id: uuid.UUID) -> Iterator[psycopg.Connection]:
    """Yield a short-lived tenant connection, closed on exit.

    **A fresh connection per refused statement, deliberately.** `as_user`
    establishes the role with a session-scoped `SET ROLE`, and a `rollback()`
    reverts it -- so a test that expected a refusal, rolled back and carried on
    would continue as `projectone_api`, which holds no privileges at all
    (`NOINHERIT`). The next statement then fails with "permission denied",
    which looks like the assertion under test failing and is not.

    Found while writing these tests, and worth recording: it is the same
    fail-closed property the request path depends on, showing up in a place
    nobody expects it.
    """
    connection = as_user(url, user_id)

    try:
        yield connection
    finally:
        connection.close()


def enqueue(
    url: str,
    identity: Identity,
    job_type: str = "tenant_probe",
    payload: dict[str, Any] | None = None,
    max_attempts: int = MAX_JOB_ATTEMPTS,
    correlation_id: str | None = None,
) -> uuid.UUID:
    """Enqueue one job through the tenant path and return its id.

    Deliberately **not** seeded over the owner connection. Enqueueing is the one
    queue operation that genuinely runs subject to RLS, so a test that arranged
    rows privileged would skip the policy it depends on.
    """
    connection = as_user(url, identity.user_id)

    try:
        job = JobRepository(connection).enqueue(
            workspace_id=identity.workspace_id,
            enqueued_by=identity.user_id,
            job_type=job_type,
            payload=payload or {},
            max_attempts=max_attempts,
            correlation_id=correlation_id,
        )
        connection.commit()
    finally:
        connection.close()

    return job.id


def read_job(admin_connection: psycopg.Connection, job_id: uuid.UUID) -> dict[str, Any]:
    """Return one job row as a mapping, over the owner connection.

    Owner-connection reads are used for *assertions about queue state*, which is
    exactly what a tenant cannot see the whole of -- the point is to check what
    the dispatcher wrote, not what a tenant may read. Isolation is asserted
    separately, over `as_user`.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, attempts, max_attempts, claimed_by, lease_expires_at, "
            "lease_token, result, last_error, dead_lettered_at, finished_at, correlation_id "
            "FROM public.jobs WHERE id = %s",
            (job_id,),
        )
        row = cursor.fetchone()

    assert row is not None, f"job {job_id} not found"

    return {
        "status": row[0],
        "attempts": row[1],
        "max_attempts": row[2],
        "claimed_by": row[3],
        "lease_expires_at": row[4],
        "lease_token": row[5],
        "result": row[6],
        "last_error": row[7],
        "dead_lettered_at": row[8],
        "finished_at": row[9],
        "correlation_id": row[10],
    }


def expire_lease(admin_connection: psycopg.Connection, job_id: uuid.UUID) -> None:
    """Push a job's lease into the past.

    A test that slept for a real lease is a test nobody runs, and shortening the
    lease to milliseconds would make the suite race its own database. Moving the
    expiry is the same technique `ExecutionBudget.elapsed` exposes `now` for.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s",
            (job_id,),
        )
    admin_connection.commit()


# ------------------------------------------------------- schema agreement --


class TestTheSchemaAgreesWithTheCode:
    """Two lists edited in different files, which is the shape that drifts."""

    def test_job_status_vocabulary_matches_the_database(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """`JobStatus` against `ck_jobs_status_valid`.

        The defect STEP-21 paid for on `assets.kind`: an enum and a CHECK
        constraint that were meant to be edited together and were not, so a value
        the code produced was refused by the database at runtime.
        """
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_jobs_status_valid'"
            )
            row = cursor.fetchone()

        assert row is not None, "ck_jobs_status_valid is missing"
        definition = str(row[0])

        for status in JobStatus:
            assert f"'{status.value}'" in definition, (
                f"JobStatus.{status.name} is not permitted by ck_jobs_status_valid"
            )

        # And the reverse: a value the database allows that the code does not
        # know about would be a state nothing can ever handle.
        allowed = definition.count("::text")
        assert allowed == len(JobStatus), (
            f"ck_jobs_status_valid permits {allowed} values but JobStatus has {len(JobStatus)}"
        )

    def test_the_database_enforces_the_same_attempt_ceiling(
        self, admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
    ) -> None:
        """`MAX_JOB_ATTEMPTS` against `ck_jobs_max_attempts_within_ceiling`.

        The registry refuses an over-ceiling handler at import, which is the
        readable failure. **This is the guarantee.** A job row is what actually
        costs money, so the bound the owner accepted in ADR-005 §7 is enforced
        where a row is written, not only where a handler is registered.
        """
        alice, _bob = tenants

        with admin_connection.transaction(), pytest.raises(psycopg.errors.CheckViolation):
            with admin_connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.jobs (workspace_id, enqueued_by, job_type, max_attempts) "
                    "VALUES (%s, %s, 'tenant_probe', %s)",
                    (alice.workspace_id, alice.user_id, MAX_JOB_ATTEMPTS + 1),
                )

        # The accepted ceiling itself is accepted, so the refusal above is the
        # bound rather than the column being unusable.
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.jobs (workspace_id, enqueued_by, job_type, max_attempts) "
                "VALUES (%s, %s, 'tenant_probe', %s)",
                (alice.workspace_id, alice.user_id, MAX_JOB_ATTEMPTS),
            )
        admin_connection.commit()


# ------------------------------------------------------------- claiming --


class TestClaiming:
    """`FOR UPDATE SKIP LOCKED`, and what it guarantees."""

    def test_a_claim_carries_what_a_worker_needs_and_nothing_wider(
        self,
        request_database_url: str,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """An identity, a type, an opaque payload and a lease token.

        ADR-005 §5 constraint 1 bounds what leaves the dispatcher to exactly
        that. Asserting the fields individually is what makes a future widening
        of `ClaimedJob` visible here rather than silent -- a `Job` returned
        instead would carry every column the table grows.
        """
        alice, _bob = tenants
        job_id = enqueue(
            request_database_url,
            alice,
            payload={"note": "hello"},
            correlation_id="req-abc",
        )

        claimed, _reaped = dispatch.claim("worker-1", LONG_LEASE)

        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.workspace_id == alice.workspace_id
        assert claimed.enqueued_by == alice.user_id
        assert claimed.job_type == "tenant_probe"
        assert claimed.payload == {"note": "hello"}
        assert claimed.attempt == 1
        assert claimed.max_attempts == MAX_JOB_ATTEMPTS
        assert claimed.correlation_id == "req-abc"
        assert isinstance(claimed.lease_token, uuid.UUID)

        # The set is closed: no connection, no cursor, no DSN reaches a caller.
        assert set(vars(claimed)) == {
            "id",
            "workspace_id",
            "enqueued_by",
            "job_type",
            "payload",
            "attempt",
            "max_attempts",
            "correlation_id",
            "lease_token",
            # New in STEP-31, and the reason it is still "nothing wider": a
            # workflow job's run is a **relational** fact on `jobs`, read by the
            # same statement that claimed the row. A handler driving a run from
            # this can never be driven from a payload a member could forge.
            "workflow_run_id",
        }
        assert claimed.workflow_run_id is None

    def test_only_one_of_many_concurrent_workers_claims_a_job(
        self,
        request_database_url: str,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """The property that stops one job running twice at once.

        ADR-005 §5 requires this be "proven rather than assumed from the presence
        of a claim". Four threads, one job: PostgreSQL serialises the conditional
        update, so exactly one wins.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        winners: list[uuid.UUID] = []
        lock = threading.Lock()

        def attempt(index: int) -> None:
            claimed, _reaped = dispatch.claim(f"worker-{index}", LONG_LEASE)

            if claimed is not None:
                with lock:
                    winners.append(claimed.id)

        threads = [threading.Thread(target=attempt, args=(index,)) for index in range(4)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert winners == [job_id], f"expected exactly one claimant, got {len(winners)}"

    def test_two_workers_polling_at_once_receive_different_jobs(
        self,
        request_database_url: str,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """`SKIP LOCKED`, which is what makes more processes mean more throughput.

        Without it the second worker would block on the first's row lock and the
        queue would drain serially however many workers were running -- so
        ADR-005 §3's "concurrency is achieved by running more worker processes"
        would be false.
        """
        alice, bob = tenants
        first = enqueue(request_database_url, alice)
        second = enqueue(request_database_url, bob)

        claimed: list[uuid.UUID] = []
        lock = threading.Lock()

        def attempt(index: int) -> None:
            job, _reaped = dispatch.claim(f"worker-{index}", LONG_LEASE)

            if job is not None:
                with lock:
                    claimed.append(job.id)

        threads = [threading.Thread(target=attempt, args=(index,)) for index in range(2)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert sorted(claimed) == sorted([first, second])

    def test_an_empty_queue_returns_nothing_rather_than_waiting(
        self, dispatch: JobDispatchRepository
    ) -> None:
        """A poll against an empty queue is a fast, honest 'nothing here'."""
        claimed, reaped = dispatch.claim("worker-1", LONG_LEASE)

        assert claimed is None
        assert reaped == ()

    def test_a_job_survives_the_process_that_enqueued_it(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """The required proof: a job survives an API process restart.

        The enqueue happens on one connection which is then **closed**, standing
        in for the process that made it going away. Nothing is held in memory
        anywhere, which is what a database-backed queue buys and what ADR-005 §1
        rejected a broker to keep.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice, payload={"survives": True})

        claimed, _reaped = dispatch.claim("worker-after-restart", LONG_LEASE)

        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.payload == {"survives": True}
        assert claimed.enqueued_by == alice.user_id
        assert claimed.workspace_id == alice.workspace_id

    def test_a_claim_is_committed_before_the_handler_would_run(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """ADR-005 §4: the claim commits, so the long work holds no lock.

        Read back over a *different* connection immediately after claiming. A
        claim still inside an open transaction would be invisible here, which is
        the shape `c8f1a3d54e29` rejected -- a row locked for the duration of an
        upstream call is how a cost control becomes a bottleneck.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        claimed, _reaped = dispatch.claim("worker-1", LONG_LEASE)
        assert claimed is not None

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.RUNNING
        assert stored["claimed_by"] == "worker-1"
        assert stored["attempts"] == 1
        assert stored["lease_expires_at"] is not None

    def test_a_running_job_with_a_live_lease_is_not_claimable(
        self,
        request_database_url: str,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """The lease is what keeps a job off the queue while it runs."""
        alice, _bob = tenants
        enqueue(request_database_url, alice)

        first, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert first is not None

        second, _ = dispatch.claim("worker-2", LONG_LEASE)
        assert second is None

    def test_a_soft_deleted_job_is_not_claimable(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """Workspace erasure drains the queue as well as clearing the rows.

        A workspace that asked to be cleared must not have work still running on
        its behalf afterwards -- so the claim filters `deleted_at IS NULL`, and
        this asserts that rather than trusting the clause is still there.
        """
        alice, _bob = tenants
        enqueue(request_database_url, alice)

        with admin_connection.cursor() as cursor:
            cursor.execute("UPDATE public.jobs SET deleted_at = now()")
        admin_connection.commit()

        claimed, _reaped = dispatch.claim("worker-1", LONG_LEASE)
        assert claimed is None


# ---------------------------------------------------------------- leases --


class TestLeases:
    """What a lapsed lease means, stated as ADR-005 §6 states it."""

    def test_an_expired_lease_makes_a_job_claimable_and_consumes_an_attempt(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """The at-least-once case, and the reason it is bounded.

        A crashed worker's job returns to the queue -- and the recovery **costs an
        attempt**. ADR-005 §6 is explicit about why: a worker crash-looping on a
        job that kills the process would otherwise be unbounded, the one shape
        where "the process died so it does not count" produces an infinite loop
        with no error to observe.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        first, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert first is not None
        assert first.attempt == 1

        expire_lease(admin_connection, job_id)

        second, _ = dispatch.claim("worker-2", LONG_LEASE)
        assert second is not None
        assert second.id == job_id
        assert second.attempt == 2, "a lease recovery must consume an attempt"
        assert second.lease_token != first.lease_token

    def test_a_lease_can_be_extended_while_it_is_held(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """A long job stays claimed as long as its worker keeps saying so."""
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        claimed, _ = dispatch.claim("worker-1", 30)
        assert claimed is not None
        before = read_job(admin_connection, job_id)["lease_expires_at"]

        assert dispatch.extend_lease(claimed.id, claimed.lease_token, 600) is True

        after = read_job(admin_connection, job_id)["lease_expires_at"]
        assert after > before

    def test_a_superseded_worker_cannot_extend_a_lease_it_lost(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """Otherwise a dead worker's heartbeat would reclaim live work.

        The stale holder returning late is not hypothetical: it is exactly what
        at-least-once delivery produces. Without the token it would extend the
        lease of a job another worker is now running.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        stale, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert stale is not None

        expire_lease(admin_connection, job_id)

        current, _ = dispatch.claim("worker-2", LONG_LEASE)
        assert current is not None

        assert dispatch.extend_lease(stale.id, stale.lease_token, 600) is False
        assert dispatch.extend_lease(current.id, current.lease_token, 600) is True

    def test_a_superseded_worker_cannot_settle_a_job_it_lost(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """A late finisher must not overwrite the state of the job's real owner.

        The same defect `test_a_superseded_claim_cannot_settle_the_turn` guards
        for chat turns, one layer up. Here it would be worse: the stale worker
        would mark a job `succeeded` that another worker is still executing, so
        the queue would report finished work that is still running.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        stale, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert stale is not None

        expire_lease(admin_connection, job_id)

        current, _ = dispatch.claim("worker-2", LONG_LEASE)
        assert current is not None

        assert (
            dispatch.record_outcome(
                stale.id, stale.lease_token, JobOutcome(status=JobStatus.SUCCEEDED)
            ).held
            is False
        )
        assert read_job(admin_connection, job_id)["status"] == JobStatus.RUNNING

        assert (
            dispatch.record_outcome(
                current.id, current.lease_token, JobOutcome(status=JobStatus.SUCCEEDED)
            ).held
            is True
        )
        assert read_job(admin_connection, job_id)["status"] == JobStatus.SUCCEEDED


# ------------------------------------------------- outcomes and the ceiling --


class TestOutcomesAndTheCeiling:
    """Retry until the ceiling, then dead-letter -- never retry forever."""

    def test_a_successful_outcome_clears_the_lease_and_stores_the_result(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        claimed, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert claimed is not None

        assert dispatch.record_outcome(
            claimed.id,
            claimed.lease_token,
            JobOutcome(status=JobStatus.SUCCEEDED, result={"ok": True}),
        ).held

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.SUCCEEDED
        assert stored["result"] == {"ok": True}
        assert stored["finished_at"] is not None
        assert stored["claimed_by"] is None, "a settled job must not look owned"
        assert stored["lease_expires_at"] is None
        assert stored["lease_token"] is None

    def test_a_retryable_failure_returns_the_job_to_the_queue(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """`pending` again, with the attempt already spent and the error kept."""
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        claimed, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert claimed is not None

        assert dispatch.record_outcome(
            claimed.id,
            claimed.lease_token,
            JobOutcome(status=JobStatus.PENDING, last_error="upstream timed out"),
        ).held

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.PENDING
        assert stored["attempts"] == 1
        assert stored["last_error"] == "upstream timed out"
        assert stored["claimed_by"] is None
        assert stored["finished_at"] is None

        retried, _ = dispatch.claim("worker-2", LONG_LEASE)
        assert retried is not None
        assert retried.attempt == 2

    def test_a_job_is_dead_lettered_rather_than_retried_forever(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """The required proof, end to end at the queue layer.

        Two attempts is the accepted ceiling, so the second failure is the last
        one. After it the job is dead-lettered and **no further claim is
        possible** -- which is the difference between a ceiling and a suggestion.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        first, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert first is not None
        dispatch.record_outcome(
            first.id, first.lease_token, JobOutcome(status=JobStatus.PENDING, last_error="flaky")
        )

        second, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert second is not None
        assert second.attempt == MAX_JOB_ATTEMPTS
        dispatch.record_outcome(
            second.id,
            second.lease_token,
            JobOutcome(status=JobStatus.DEAD_LETTERED, last_error="still flaky"),
        )

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.DEAD_LETTERED
        assert stored["attempts"] == MAX_JOB_ATTEMPTS
        assert stored["dead_lettered_at"] is not None
        assert stored["last_error"] == "still flaky"

        exhausted, _ = dispatch.claim("worker-2", LONG_LEASE)
        assert exhausted is None, "a dead-lettered job must never be claimed again"

    def test_a_job_whose_worker_died_on_its_last_attempt_is_dead_lettered(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """The reap, and the silent state it exists to prevent.

        A worker that dies on the final attempt records nothing, and the job is
        no longer claimable because its attempts are spent. Without the reap it
        would sit in `running` with a lapsed lease forever: unfinished, invisible
        and never dead-lettered -- [[CLAUDE|CLAUDE.md]] §26's "fail in a way
        nobody would notice", exactly.

        The reaped job is **returned** so the caller can log it, because nothing
        else is left running to report it.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice, max_attempts=1)

        claimed, _ = dispatch.claim("worker-that-dies", LONG_LEASE)
        assert claimed is not None

        expire_lease(admin_connection, job_id)

        nothing, reaped = dispatch.claim("worker-2", LONG_LEASE)

        assert nothing is None
        assert [job.id for job in reaped] == [job_id]
        assert reaped[0].attempts == 1

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.DEAD_LETTERED
        assert stored["dead_lettered_at"] is not None
        assert stored["last_error"] is not None, "a dead-lettered job must say why"
        assert stored["claimed_by"] is None

    def test_status_of_answers_without_returning_tenant_data(
        self,
        request_database_url: str,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """A status string, never a row: the boundary holds even for diagnostics."""
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        assert dispatch.status_of(job_id) == JobStatus.PENDING
        assert dispatch.status_of(uuid.uuid4()) is None


# ------------------------------------------------------------- the tenant --


class TestTheTenantPath:
    """RLS on the enqueue-and-read side, and the write guard on top of it."""

    def test_another_tenants_job_is_invisible(
        self,
        request_database_url: str,
        tenants: tuple[Identity, Identity],
    ) -> None:
        """RLS, not a `WHERE` clause, is what keeps these apart."""
        alice, bob = tenants
        bobs_job = enqueue(request_database_url, bob)

        connection = as_user(request_database_url, alice.user_id)

        try:
            repository = JobRepository(connection)

            assert repository.get(bob.workspace_id, bobs_job) is None
            assert repository.get(alice.workspace_id, bobs_job) is None
            assert repository.list_for_workspace(bob.workspace_id) == ()
        finally:
            connection.close()

        # Visible to its owner, so the refusals above were scoping rather than
        # the job being unreadable for some unrelated reason.
        owner = as_user(request_database_url, bob.user_id)

        try:
            found = JobRepository(owner).get(bob.workspace_id, bobs_job)
            assert found is not None
            assert found.id == bobs_job
        finally:
            owner.close()

    def test_a_member_cannot_enqueue_work_that_runs_as_someone_else(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
    ) -> None:
        """The INSERT policy pins `enqueued_by` to `auth.uid()`.

        **The escalation this table would otherwise carry.** `enqueued_by` is the
        identity a worker replays, so a member naming a colleague would get that
        colleague's row visibility on a delayed fuse -- and the workspace
        predicate alone would permit it, because both users are in the same
        workspace, which is the whole point.
        """
        alice, _bob = tenants

        # A second member of Alice's workspace, so the workspace predicate is
        # satisfied and only the `enqueued_by` clause can refuse this.
        colleague = seed_identity(admin_connection, "colleague")
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, 'member')",
                (alice.workspace_id, colleague.user_id),
            )
        admin_connection.commit()

        with session_as(request_database_url, colleague.user_id) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                JobRepository(connection).enqueue(
                    workspace_id=alice.workspace_id,
                    enqueued_by=alice.user_id,
                    job_type="tenant_probe",
                    payload={},
                    max_attempts=MAX_JOB_ATTEMPTS,
                )

        # The same enqueue as themselves succeeds, so the refusal above was the
        # identity clause rather than the workspace one.
        with session_as(request_database_url, colleague.user_id) as connection:
            job = JobRepository(connection).enqueue(
                workspace_id=alice.workspace_id,
                enqueued_by=colleague.user_id,
                job_type="tenant_probe",
                payload={},
                max_attempts=MAX_JOB_ATTEMPTS,
            )
            connection.commit()

        assert job.enqueued_by == colleague.user_id

    def test_erasure_is_the_one_client_write_jobs_accepts(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
    ) -> None:
        """Both halves of the guard, asserted together.

        A tenant may set `deleted_at` -- workspace erasure depends on it, and the
        SELECT policy deliberately omits the `deleted_at IS NULL` filter that
        would make it impossible. A tenant may not touch queue state, because
        resetting `attempts` would replay a job indefinitely and setting `status`
        would forge an outcome.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        # Every value here must genuinely *differ* from what the row holds. The
        # guard compares `OLD` and `NEW`, so `SET attempts = 0` on a job that
        # already has 0 changes nothing and is correctly permitted -- a first
        # draft of this test used exactly that and reported the guard as broken
        # when it was the assertion that was.
        for column, value in (
            ("status", JobStatus.SUCCEEDED.value),
            ("attempts", 1),
            ("max_attempts", 1),
            ("job_type", "something_else"),
        ):
            # One connection per refused statement -- see `session_as`.
            with session_as(request_database_url, alice.user_id) as connection:
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.cursor() as cursor:
                        cursor.execute(
                            f"UPDATE public.jobs SET {column} = %s WHERE id = %s",  # noqa: S608
                            (value, job_id),
                        )

        # The soft delete, which must work.
        with session_as(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.jobs SET deleted_at = now() "
                    "WHERE id = %s AND deleted_at IS NULL",
                    (job_id,),
                )
                assert cursor.rowcount == 1, (
                    "erasure must be able to soft-delete a job; a SELECT policy "
                    "filtering deleted_at would silently make this affect zero rows"
                )
            connection.commit()

        assert read_job(admin_connection, job_id)["status"] == JobStatus.PENDING

    def test_the_policies_are_what_makes_the_isolation_test_pass(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
    ) -> None:
        """The negative control [[RLS Policy Pattern]] step 8 requires.

        **An isolation test that passes with RLS off is testing nothing**, and
        that is not a hypothetical: STEP-09 verified that 15 of its 17 tests fail
        without the policies, precisely so the suite could be trusted.

        This disables row level security on `jobs`, observes the breach, and
        restores it. The restoration is in a `finally` because leaving the table
        unprotected would silently weaken every later test in the session.
        """
        alice, bob = tenants
        enqueue(request_database_url, bob)

        with session_as(request_database_url, alice.user_id) as connection:
            assert JobRepository(connection).list_for_workspace(bob.workspace_id) == ()

        try:
            with admin_connection.cursor() as cursor:
                cursor.execute("ALTER TABLE public.jobs DISABLE ROW LEVEL SECURITY")
            admin_connection.commit()

            with session_as(request_database_url, alice.user_id) as connection:
                leaked = JobRepository(connection).list_for_workspace(bob.workspace_id)

            assert len(leaked) == 1, (
                "with RLS disabled the other tenant's job should be readable; if it is "
                "not, this isolation test is passing for some reason other than the policy"
            )
        finally:
            with admin_connection.cursor() as cursor:
                cursor.execute("ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY")
                cursor.execute("ALTER TABLE public.jobs FORCE ROW LEVEL SECURITY")
            admin_connection.commit()

        with session_as(request_database_url, alice.user_id) as connection:
            assert JobRepository(connection).list_for_workspace(bob.workspace_id) == ()

    def test_the_dispatcher_is_not_bound_by_the_client_write_guard(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
    ) -> None:
        """The guard bounds the client path only.

        Worth asserting explicitly: a guard that also refused the dispatcher
        would make the queue unable to run at all, and the obvious repair would
        be to weaken it for everyone.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        claimed, _ = dispatch.claim("worker-1", LONG_LEASE)
        assert claimed is not None

        assert read_job(admin_connection, job_id)["status"] == JobStatus.RUNNING
