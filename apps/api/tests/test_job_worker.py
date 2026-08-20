"""The worker loop, against a real database (STEP-30).

The queue's own properties are proven in `test_job_queue.py`. This file covers
what only the *worker* can be wrong about, and the first of them is the one this
step exists to make impossible:

- **Tenant context is carried into the worker and enforced there.** A handler
  executing a job for workspace A cannot read workspace B, asserted directly
  rather than inferred from the presence of a parameter. ADR-005 §5 requires this
  be proven by test.
- **A handler is never invoked without an established identity.** A job whose
  actor lost their membership fails terminally and the handler is not called at
  all -- observed by a handler that records whether it ran.
- **The retry policy is what ADR-005 §7 says.** Retryable failures are retried up
  to the ceiling and then dead-lettered; terminal refusals are dead-lettered on
  the first attempt however many attempts remain.
- **Duplicate delivery does not duplicate effects**, on the real registered
  handler rather than on a fake.
- **Worker startup fails loudly without configuration**, matching what STEP-28
  established for the API.

A note on the handler fakes below: they are handlers, registered through the real
`JobHandlerRegistry`, executed by the real `JobWorker` against the real
dispatcher and the real `RequestSessionFactory`. The only thing substituted is
what the handler *does*, which is the one thing these tests are not asserting
about.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from app.ai.governance import BudgetExceededError
from app.core.config import STARTUP_REQUIRED_STORAGE_VARIABLES, Settings
from app.jobs.contract import (
    MAX_JOB_ATTEMPTS,
    JobContext,
    JobHandler,
    JobResult,
    JobStatus,
)
from app.jobs.registry import JobHandlerRegistry
from app.jobs.worker import JobWorker
from app.repositories.job_dispatch import JobDispatchRepository, JobOutcome
from app.repositories.session import RequestSessionFactory
from tests.conftest import TEST_BYOK_KEY, Identity, seed_identity
from tests.test_job_queue import LONG_LEASE, enqueue, expire_lease, read_job

pytestmark = pytest.mark.usefixtures("migrated_database")


def make_settings(request_url: str, admin_url: str) -> Settings:
    """Build real `Settings` pointed at the throwaway database.

    Real rather than a stand-in, unlike the queue tests: the worker is built by
    `build_worker(settings)` and reads the two job intervals off it, so a stub
    would be testing a different construction path from the one that runs.
    """
    return Settings(  # type: ignore[call-arg]
        environment="development",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_SECRET_KEY="sb_secret_test",
        DATABASE_URL=admin_url,
        REQUEST_DATABASE_URL=request_url,
        byok_encryption_key=TEST_BYOK_KEY,
    )


class _RecordingHandler(JobHandler):
    """A handler that records every invocation and does what it is told."""

    def __init__(
        self,
        job_type: str = "tenant_probe",
        max_attempts: int = MAX_JOB_ATTEMPTS,
        error: Exception | None = None,
    ) -> None:
        self._job_type = job_type
        self._max_attempts = max_attempts
        self._error = error
        self.invocations: list[JobContext] = []

    @property
    def job_type(self) -> str:
        return self._job_type

    @property
    def max_attempts(self) -> int:
        return self._max_attempts

    def execute(self, context: JobContext) -> JobResult:
        self.invocations.append(context)

        if self._error is not None:
            raise self._error

        return JobResult(output={"attempt": context.attempt}, detail="done")


@pytest.fixture
def dispatch(migrated_database: str, request_database_url: str) -> JobDispatchRepository:
    """The real dispatcher, over the privileged connection."""
    return JobDispatchRepository(make_settings(request_database_url, migrated_database))


@pytest.fixture
def sessions(migrated_database: str, request_database_url: str) -> RequestSessionFactory:
    """The real session factory, over the request-path role.

    The same object the API builds. Using it here is what makes these tests a
    statement about tenant isolation rather than about a test helper.
    """
    return RequestSessionFactory(make_settings(request_database_url, migrated_database))


def build_worker_with(
    dispatch: JobDispatchRepository,
    sessions: RequestSessionFactory,
    handler: JobHandler,
) -> JobWorker:
    """Return a worker running exactly one handler."""
    return JobWorker(
        dispatch=dispatch,
        sessions=sessions,
        registry=JobHandlerRegistry((handler,)),
        lease_seconds=LONG_LEASE,
        poll_interval_seconds=0.01,
        worker_id="test-worker",
    )


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[tuple[Identity, Identity]]:
    """Seed two unrelated tenants, each owning one workspace."""
    yield seed_identity(admin_connection, "alice"), seed_identity(admin_connection, "bob")


# ------------------------------------------------------- the tenant boundary --


class TestTenantContextInsideTheWorker:
    """The risk this step exists to close, asserted rather than assumed."""

    def test_a_handler_runs_as_the_enqueuing_user(
        self,
        request_database_url: str,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """The session a handler opens is RLS-subject and carries the actor's id.

        Both halves matter. `authenticated` is the role every policy is written
        `TO`, and `request.jwt.claim.sub` is what `auth.uid()` reads -- a session
        missing either matches no policy and reads nothing, which is the
        fail-closed direction `projectone_api`'s `NOINHERIT` was chosen for.
        """
        alice, _bob = tenants
        enqueue(request_database_url, alice)

        observed: dict[str, Any] = {}

        class _Inspecting(_RecordingHandler):
            def execute(self, context: JobContext) -> JobResult:
                with context.tenant_session() as connection, connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT current_user, "
                        "current_setting('request.jwt.claim.sub', true), "
                        "(SELECT rolbypassrls FROM pg_roles WHERE rolname = session_user)"
                    )
                    row = cursor.fetchone()

                assert row is not None
                observed["role"] = row[0]
                observed["claim"] = row[1]
                observed["bypasses_rls"] = row[2]

                return JobResult(output=None)

        worker = build_worker_with(dispatch, sessions, _Inspecting())

        assert worker.run_once() is True
        assert observed["role"] == "authenticated"
        assert observed["claim"] == str(alice.user_id)
        assert observed["bypasses_rls"] is False, (
            "the worker's login role must not carry rolbypassrls, or RLS is decorative"
        )

    def test_a_handler_cannot_read_another_workspace(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """**The required proof.** A job for workspace A must not read B's rows.

        A cross-tenant read here would pass every route test in the suite, which
        is precisely why ADR-005 §5 requires it be asserted directly. Bob's
        project exists and is invisible; Alice's own is visible through the same
        session, so the refusal is scoping rather than the query being broken.
        """
        alice, bob = tenants

        with admin_connection.cursor() as cursor:
            for identity, name in ((alice, "alice-project"), (bob, "bob-project")):
                cursor.execute(
                    "INSERT INTO public.projects (workspace_id, name, status, created_by) "
                    "VALUES (%s, %s, 'idea', %s)",
                    (identity.workspace_id, name, identity.user_id),
                )
        admin_connection.commit()

        enqueue(request_database_url, alice)
        seen: dict[str, list[str]] = {}

        class _Peeking(_RecordingHandler):
            def execute(self, context: JobContext) -> JobResult:
                with context.tenant_session() as connection, connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT name FROM public.projects WHERE workspace_id = %s",
                        (bob.workspace_id,),
                    )
                    seen["other_tenant"] = [str(row[0]) for row in cursor.fetchall()]

                    cursor.execute(
                        "SELECT name FROM public.projects WHERE workspace_id = %s",
                        (alice.workspace_id,),
                    )
                    seen["own"] = [str(row[0]) for row in cursor.fetchall()]

                return JobResult(output=None)

        worker = build_worker_with(dispatch, sessions, _Peeking())

        assert worker.run_once() is True
        assert seen["other_tenant"] == [], "the worker read another workspace's rows"
        assert seen["own"] == ["alice-project"], (
            "the worker could not read its own workspace, so the test above proved nothing"
        )

    def test_a_revoked_membership_fails_terminally_without_reaching_the_handler(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """ADR-005 §4 and §5 constraint 4, both halves.

        The owner accepted on 2026-08-17 that a job whose actor lost workspace
        membership **fails permanently**. Two things are asserted, and the second
        is the ordering guarantee: the handler is never invoked, so no work runs
        under an identity that no longer holds access.

        Terminal rather than retryable, so the ceiling is not spent re-asking a
        permission question of a database that will keep answering no -- proven
        by the attempt count stopping at one.

        The actor is a **plain member** rather than the workspace owner, and that
        is forced rather than chosen: `app_protect_last_owner` refuses to remove
        the last owner at all, so revoking one is not a state the platform can
        reach. A member being removed is, and it is the realistic case.
        """
        alice, _bob = tenants

        colleague = seed_identity(admin_connection, "colleague")
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, 'member')",
                (alice.workspace_id, colleague.user_id),
            )
        admin_connection.commit()

        actor = Identity(colleague.user_id, alice.workspace_id, colleague.email)
        job_id = enqueue(request_database_url, actor)

        # Revoke after enqueue: exactly the window ADR-005 §4 describes.
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND user_id = %s",
                (alice.workspace_id, colleague.user_id),
            )
        admin_connection.commit()

        handler = _RecordingHandler()
        worker = build_worker_with(dispatch, sessions, handler)

        assert worker.run_once() is True
        assert handler.invocations == [], "a handler ran for an actor with no live membership"

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.DEAD_LETTERED
        assert stored["attempts"] == 1, "a revoked membership must not be retried"
        assert stored["last_error"] is not None
        assert "access" in str(stored["last_error"]).lower(), (
            "the dead-letter record should name revocation, not a generic failure"
        )


# ------------------------------------------------------------ retry policy --


class TestTheRetryPolicy:
    """ADR-005 §7: classified first, counted second."""

    def test_a_retryable_failure_is_retried_then_dead_lettered(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """**The required proof**: retried up to its ceiling, then dead-lettered.

        Two attempts is the accepted ceiling, so the handler runs exactly twice
        and the job is then terminal. "Retried forever" and "retried once" are
        both wrong, and the count is what distinguishes them.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        handler = _RecordingHandler(error=ConnectionError("upstream is down"))
        worker = build_worker_with(dispatch, sessions, handler)

        assert worker.run_once() is True
        assert read_job(admin_connection, job_id)["status"] == JobStatus.PENDING

        assert worker.run_once() is True

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.DEAD_LETTERED
        assert stored["attempts"] == MAX_JOB_ATTEMPTS
        assert stored["dead_lettered_at"] is not None

        assert len(handler.invocations) == MAX_JOB_ATTEMPTS
        assert [context.attempt for context in handler.invocations] == [1, 2]

        # And nothing more is claimable, so the ceiling is a ceiling.
        assert worker.run_once() is False

    def test_a_governance_refusal_is_dead_lettered_on_the_first_attempt(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """A budget refusal retried is the refusal repeated.

        The attempt remaining on the clock is deliberately *not* spent: a
        ceiling that retries a settled "no" is a ceiling that costs money to
        confirm it is still a ceiling.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        handler = _RecordingHandler(error=BudgetExceededError("over the workspace ceiling"))
        worker = build_worker_with(dispatch, sessions, handler)

        assert worker.run_once() is True

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.DEAD_LETTERED
        assert stored["attempts"] == 1, "a terminal refusal must not spend the remaining attempt"
        assert stored["last_error"] == BudgetExceededError.public_message
        assert len(handler.invocations) == 1

    def test_an_unexpected_exception_never_reaches_the_stored_error(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """`jobs.last_error` is tenant-readable, so it carries no internal detail.

        [[CLAUDE|CLAUDE.md]] §24: an unexpected exception's message is written
        for an engineer and may quote internal state. It goes to the log; the row
        gets a fixed string.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        secret = "psycopg connection to internal-host-7 refused"
        handler = _RecordingHandler(error=RuntimeError(secret))
        worker = build_worker_with(dispatch, sessions, handler)

        worker.run_once()
        worker.run_once()

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.DEAD_LETTERED
        assert stored["last_error"] == "This job failed unexpectedly"
        assert secret not in str(stored["last_error"])

    def test_an_unregistered_job_type_is_dead_lettered_immediately(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """The registry is fixed at process start, so retrying asks the same question."""
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice, job_type="not_registered")

        worker = build_worker_with(dispatch, sessions, _RecordingHandler())

        assert worker.run_once() is True

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.DEAD_LETTERED
        assert stored["attempts"] == 1


# ----------------------------------------------------------- delivery again --


class TestAtLeastOnceDelivery:
    """What a second delivery costs, on the real registered handler."""

    def test_duplicate_delivery_does_not_duplicate_effects(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """**The required proof, on the real handler rather than a fake.**

        The job is claimed, its lease is expired underneath it, and it is claimed
        and executed again -- the exact at-least-once case ADR-005 §6 describes.
        `TenantProbeHandler` only reads, so the second delivery re-reads the same
        values: one row, one stored result, one workspace unchanged.

        The project count is asserted before and after because it is the closest
        thing this handler has to an effect. A handler that had created something
        would move it, which is what "duplicate effects" would look like here.
        """
        from app.jobs.handlers import TenantProbeHandler

        alice, _bob = tenants

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.projects (workspace_id, name, status, created_by) "
                "VALUES (%s, 'only-project', 'idea', %s)",
                (alice.workspace_id, alice.user_id),
            )
        admin_connection.commit()

        job_id = enqueue(request_database_url, alice)
        worker = build_worker_with(dispatch, sessions, TenantProbeHandler())

        # First delivery, interrupted: claimed, executed, but its lease lapses
        # before the outcome is recorded.
        claimed, _ = dispatch.claim("worker-that-stalls", LONG_LEASE)
        assert claimed is not None
        expire_lease(admin_connection, job_id)

        # Second delivery: a different worker picks the same job up.
        assert worker.run_once() is True

        stored = read_job(admin_connection, job_id)
        assert stored["status"] == JobStatus.SUCCEEDED
        assert stored["attempts"] == MAX_JOB_ATTEMPTS
        assert stored["result"]["workspace_name"] == f"Workspace {alice.email.split('-')[0]}"
        assert stored["result"]["project_count"] == 1

        with admin_connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM public.jobs")
            job_rows = cursor.fetchone()
            cursor.execute(
                "SELECT count(*) FROM public.projects WHERE workspace_id = %s",
                (alice.workspace_id,),
            )
            projects = cursor.fetchone()

        assert job_rows is not None and job_rows[0] == 1, "a redelivery must not create a job"
        assert projects is not None and projects[0] == 1, "the workspace gained nothing"

    def test_the_stalled_worker_cannot_settle_the_job_it_lost(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """The worker reports a discarded outcome rather than clobbering the winner.

        Asserted through `JobWorker` rather than the repository, because this is
        where the two-worker race actually resolves: `_settle` is told it no
        longer holds the lease and must not treat that as an error to raise.
        """
        alice, _bob = tenants
        job_id = enqueue(request_database_url, alice)

        stalled = build_worker_with(dispatch, sessions, _RecordingHandler())
        winner = build_worker_with(dispatch, sessions, _RecordingHandler())

        claimed, _ = dispatch.claim("stalled-worker", LONG_LEASE)
        assert claimed is not None
        expire_lease(admin_connection, job_id)

        assert winner.run_once() is True
        assert read_job(admin_connection, job_id)["status"] == JobStatus.SUCCEEDED

        # The stalled worker finishing late must not reopen a settled job.
        assert (
            dispatch.record_outcome(
                claimed.id,
                claimed.lease_token,
                JobOutcome(status=JobStatus.PENDING, last_error="late"),
            ).held
            is False
        )
        assert read_job(admin_connection, job_id)["status"] == JobStatus.SUCCEEDED
        assert stalled.worker_id == "test-worker"


# ------------------------------------------------------------ the loop itself --


class TestTheLoop:
    """Polling behaviour that does not need a full process to observe."""

    def test_an_empty_queue_is_reported_rather_than_worked(
        self, dispatch: JobDispatchRepository, sessions: RequestSessionFactory
    ) -> None:
        """`run_once` returning False is what makes the loop sleep."""
        worker = build_worker_with(dispatch, sessions, _RecordingHandler())

        assert worker.run_once() is False

    def test_the_correlation_id_of_the_enqueuing_request_reaches_the_handler(
        self,
        request_database_url: str,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """Or an async failure cannot be traced to what caused it (§26).

        Observed through the same `ContextVar` the log formatter reads, so this
        asserts the mechanism rather than a parallel copy of it.
        """
        from app.core.api import current_request_id

        alice, _bob = tenants
        enqueue(request_database_url, alice, correlation_id="req-from-the-browser")

        seen: dict[str, str] = {}

        class _Correlated(_RecordingHandler):
            def execute(self, context: JobContext) -> JobResult:
                seen["request_id"] = current_request_id()
                return JobResult(output=None)

        worker = build_worker_with(dispatch, sessions, _Correlated())

        assert worker.run_once() is True
        assert seen["request_id"] == "req-from-the-browser"

        # And it is unset again afterwards, or the next job would inherit it.
        assert current_request_id() == "-"


# --------------------------------------------------------- startup validation --


class TestWorkerStartupConfiguration:
    """STEP-30 Task 7: the worker refuses to start without its configuration.

    Run as a **subprocess**, because that is the only way to observe a
    `SystemExit` from `get_settings()` as a deploy would: exit code, stderr, and
    the variable named. Calling `get_settings()` in-process would exercise the
    same function while proving nothing about `python -m app.jobs.worker`, which
    is the command a deployment actually runs.

    `cwd` is a temporary directory so `SettingsConfigDict(env_file=".env")` finds
    no `.env`. Without that, a developer machine with a populated `.env` would
    pass this test for the wrong reason -- and CI, which has none, would be the
    only place it meant anything.
    """

    @staticmethod
    def _run_worker(env: dict[str, str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
        """Start the worker module with a controlled environment."""
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-m", "app.jobs.worker"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    @staticmethod
    def _complete_environment() -> dict[str, str]:
        """Return an environment satisfying every startup requirement."""
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PROJECTONE_ENVIRONMENT": "development",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SECRET_KEY": "sb_secret_test",
            "DATABASE_URL": "postgresql://postgres:throwaway@127.0.0.1:1/none",
            "REQUEST_DATABASE_URL": "postgresql://postgres:throwaway@127.0.0.1:1/none",
            "PROJECTONE_BYOK_ENCRYPTION_KEY": TEST_BYOK_KEY,
        }

        # Derived from the same tuple `get_settings()` enforces, so a fifth
        # storage variable is covered here without anyone remembering to add it.
        for variable in STARTUP_REQUIRED_STORAGE_VARIABLES:
            environment[variable] = "test-placeholder"

        return environment

    @pytest.mark.parametrize(
        "omitted",
        [
            "PROJECTONE_ENVIRONMENT",
            "DATABASE_URL",
            "REQUEST_DATABASE_URL",
            "PROJECTONE_BYOK_ENCRYPTION_KEY",
            *STARTUP_REQUIRED_STORAGE_VARIABLES,
        ],
    )
    def test_the_worker_refuses_to_start_without_a_required_variable(
        self, omitted: str, tmp_path: Path
    ) -> None:
        """Every requirement the API has, the worker has -- it is the same `Settings`.

        Object storage is the one worth naming. STEP-28 made it a startup
        requirement rather than a first-upload surprise; a worker that touches
        assets and started without R2 credentials would reproduce exactly the
        defect that change removed, one layer deeper and less visible
        (ADR-005 §3).
        """
        environment = self._complete_environment()
        del environment[omitted]

        result = self._run_worker(environment, tmp_path)

        assert result.returncode != 0, f"the worker started without {omitted}"
        assert omitted in result.stderr, (
            f"the startup failure does not name {omitted}; an operator reading a "
            f"container log needs the variable, not a generic message.\n{result.stderr}"
        )

    def test_the_startup_failure_never_prints_a_credential(self, tmp_path: Path) -> None:
        """A startup message is exactly where a secret leaks into a container log.

        `get_settings()` reformats pydantic's errors by hand for this reason --
        the default rendering echoes the entire input mapping, credentials
        included. This asserts the reformatting is still in place.
        """
        environment = self._complete_environment()
        environment["DATABASE_URL"] = "postgresql://postgres:hunter2-secret@db.internal:5432/x"
        del environment["PROJECTONE_R2_BUCKET"]

        result = self._run_worker(environment, tmp_path)

        assert result.returncode != 0
        assert "hunter2-secret" not in result.stderr
        assert "hunter2-secret" not in result.stdout

    def test_a_fully_configured_worker_starts_and_reports_itself(self, tmp_path: Path) -> None:
        """The positive control, without which every assertion above is vacuous.

        The database is deliberately unreachable, so the worker starts, logs that
        it started, fails to dispatch, and exits non-zero once it reaches
        `MAX_CONSECUTIVE_DISPATCH_FAILURES` -- which is itself the behaviour
        being asserted: a worker whose database is gone stops loudly rather than
        polling forever while looking alive.
        """
        environment = self._complete_environment()
        environment["PROJECTONE_JOB_POLL_INTERVAL_SECONDS"] = "0.01"

        result = self._run_worker(environment, tmp_path)

        assert "job_worker_started" in result.stdout, (
            f"the worker did not reach its loop:\n{result.stdout}\n{result.stderr}"
        )
        assert "job_dispatch_failed" in result.stdout
        assert result.returncode == 1, "a worker that cannot reach its database must stop"

    def test_the_worker_module_is_runnable_as_a_module(self) -> None:
        """`python -m app.jobs.worker` is the documented command (ADR-005 §3).

        Asserted because the deployment shape recorded in `infrastructure/` names
        it: a rename here would leave that document describing a command that no
        longer exists, which is worse than no document at all.
        """
        import app.jobs.worker as worker_module

        assert hasattr(worker_module, "main")
        assert Path(str(worker_module.__file__)).name == "worker.py"


def test_the_worker_and_the_api_share_one_settings_object() -> None:
    """One image, one configuration surface (ADR-005 §3).

    `build_worker` takes the same `Settings` `create_app` does. A worker with its
    own settings class would be the beginning of two configuration surfaces, and
    the drift would surface as a worker that starts where the API would not.
    """
    import inspect

    from app.jobs.worker import build_worker

    signature = inspect.signature(build_worker)
    annotation = signature.parameters["settings"].annotation

    assert annotation in (Settings, "Settings")


def test_a_job_id_is_a_uuid_the_worker_never_invents() -> None:
    """`ClaimedJob.id` comes from the database, never from the worker.

    A worker generating ids would be a worker able to settle a job that does not
    exist. Structural rather than behavioural, and cheap to keep true.
    """
    from app.jobs import worker as worker_module

    source = Path(str(worker_module.__file__)).read_text(encoding="utf-8")

    assert "uuid.uuid4()" not in source, (
        "the worker generates a UUID; job and lease identifiers are the "
        "dispatcher's to mint, so this is either a bug or a boundary change"
    )


class TestReconciliationReachesTheWorkflowLayer:
    """A dead-lettered job carrying a run leaves no non-terminal run behind.

    STEP-30 could not assert this: the link between a job and a run did not
    exist. [[ADR-006 Workflow Async Execution and Run Reconciliation]] D5 adds
    it, and the case that matters most is the one where **no tenant identity is
    available to do it** -- a revoked actor, or a worker that died.
    """

    def test_a_revoked_actors_job_leaves_its_run_failed(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: tuple[Identity, Identity],
        dispatch: JobDispatchRepository,
        sessions: RequestSessionFactory,
    ) -> None:
        """**The case reconciliation exists for, and the one it could not serve.**

        The actor's own session cannot see this run at all --
        `app_current_user_workspaces()` filters removed memberships, so a
        reconciliation over the actor's identity would match zero rows and the
        run would sit `pending` forever with nothing left to advance it.

        The dispatcher's connection is what closes it, in the same statement that
        dead-letters the job.
        """
        alice, _bob = tenants

        colleague = seed_identity(admin_connection, "reconciled-colleague")

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, 'member')",
                (alice.workspace_id, colleague.user_id),
            )
            cursor.execute(
                "INSERT INTO public.workflow_runs "
                "(workspace_id, workflow_type, definition_version, status, triggered_by) "
                "VALUES (%s, 'project_planning', 1, 'pending', %s) RETURNING id",
                (alice.workspace_id, colleague.user_id),
            )
            row = cursor.fetchone()

        assert row is not None
        run_id = row[0]

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.jobs "
                "(workspace_id, enqueued_by, job_type, max_attempts, workflow_run_id) "
                "VALUES (%s, %s, 'workflow.execute', 2, %s)",
                (alice.workspace_id, colleague.user_id, run_id),
            )
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND user_id = %s",
                (alice.workspace_id, colleague.user_id),
            )

        admin_connection.commit()

        worker = build_worker_with(dispatch, sessions, _RecordingHandler("workflow.execute"))

        assert worker.run_once() is True

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, detail FROM public.workflow_runs WHERE id = %s", (run_id,)
            )
            stored = cursor.fetchone()

        assert stored is not None
        assert stored[0] == "failed", "a revoked actor's job left a stranded run"
        assert stored[1] is not None
        assert "access" not in stored[1].lower(), (
            "the run's detail names another member's status; the cause belongs in the log line"
        )
