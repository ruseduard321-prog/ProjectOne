"""The five protected commands, the login boundary, and the fences (STEP-31).

**Every property here is one an offline suite structurally cannot prove.** A fake
has no `SECURITY DEFINER`, no `session_user`, no column grant, no partial unique
index and no `FOR UPDATE` -- so it would report success for an implementation
that let any member forge an approval. That is not hypothetical in this
codebase: STEP-23's chat defect shipped green against exactly such a fake, and
[[ADR-006 Workflow Async Execution and Run Reconciliation]] exists because the
same class of gap was found in the workflow layer.

What only PostgreSQL can answer, and what each section here asks it:

1. **Is the caller boundary real?** The application and a direct Supabase client
   reach the database as the *same role* and differ only in their **login**.
   `session_user` is fixed at authentication and changes only through
   `SET SESSION AUTHORIZATION`, which is superuser-only -- so the tests below
   connect as a second, non-superuser login shaped exactly like PostgREST's
   `authenticator` and try to get in.
2. **Is execution state out of a client's reach?** Not "does the UI expose it" --
   PostgREST is an endpoint this application does not control, so the question is
   what the *grants* say.
3. **Does one execution win a claim?** Asserted with concurrent sessions, because
   a claim that is conditional only in prose is not conditional.
4. **Does a stale worker write anything?** Each of the three settlement
   predicates is defeated on its own, so none of them is load-bearing alone.
5. **Does a dead-lettered job leave a stranded run?** Including the path where no
   worker is alive to notice.

## The `authenticator` stand-in

Supabase's `authenticator` is reserved and cannot be provisioned from a
migration -- `d7b95c1f4e08` records exactly that, and it is why ProjectOne has
`projectone_api` at all. So this suite creates a login with the same shape:
`LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS`, granted `authenticated`. That is what
PostgREST is, and being non-superuser is the half that matters: a superuser could
`SET SESSION AUTHORIZATION` its way past any login check, and proving the guard
against one would prove nothing.
"""

from __future__ import annotations

import re
import threading
import urllib.parse
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from app.jobs.contract import MAX_JOB_ATTEMPTS, JobStatus
from app.repositories.job_dispatch import JobDispatchRepository, JobOutcome
from app.workflows.models import RunStatus, StepStatus
from tests.conftest import Identity, seed_identity

pytestmark = pytest.mark.usefixtures("migrated_database")

#: The five, with their argument types, as `pg_proc` records them.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("app_start_workflow_run", "uuid, text, integer, uuid, jsonb, text"),
    ("app_approve_workflow_step", "uuid, uuid, integer, text"),
    ("app_recover_workflow_run", "uuid, uuid, integer, boolean, text"),
    ("app_admit_workflow_step", "uuid, uuid, integer, text, boolean, boolean, uuid, uuid"),
    (
        "app_settle_workflow_step",
        "uuid, uuid, integer, text, text, text, jsonb, integer, uuid, uuid, uuid",
    ),
)

#: The login every command demands, as a literal -- the same literal the function
#: bodies carry. Written out here rather than imported from the migration so the
#: assertion is a genuine second opinion: if someone changes it in one place,
#: these tests fail rather than agreeing with the change.
APPLICATION_LOGIN = "projectone_api"

#: A stand-in for Supabase's PostgREST login. See the module docstring.
POSTGREST_LOGIN = "projectone_postgrest_probe"
POSTGREST_PASSWORD = "projectone-test-postgrest-probe"  # noqa: S105 - throwaway test database

#: The only tables any command may name.
PERMITTED_TABLES = frozenset(
    {"workflow_runs", "workflow_step_runs", "jobs", "audit_log", "workspace_members"}
)

WORKFLOW_JOB_TYPE = "workflow.execute"
LONG_LEASE = 300


# ------------------------------------------------------------------ tenants --


class Workspace:
    """One workspace with an owner and a member, plus an unrelated stranger."""

    def __init__(self, owner: Identity, member: Identity, stranger: Identity) -> None:
        """Record the identities and the workspace the first two share."""
        self.owner = owner
        self.member = member
        self.stranger = stranger
        self.id = owner.workspace_id


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[Workspace]:
    """Seed one workspace with an owner and a member, plus an unrelated one."""
    owner = seed_identity(admin_connection, "cmd-owner")
    member = seed_identity(admin_connection, "cmd-member")
    stranger = seed_identity(admin_connection, "cmd-stranger")

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (owner.workspace_id, member.user_id),
        )

    yield Workspace(owner, member, stranger)


@pytest.fixture(scope="session")
def postgrest_url(migrated_database: str, request_database_url: str) -> str:
    """Return a connection string for a login shaped exactly like PostgREST's.

    `LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS`, granted `authenticated`: the same
    shape `d7b95c1f4e08` gave `projectone_api`, and the same shape Supabase gives
    `authenticator`. Created here rather than in a migration because it exists to
    *attack* the boundary, and a role that exists only in tests cannot become one
    the application accidentally starts using.
    """
    with psycopg.connect(migrated_database, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{POSTGREST_LOGIN}')
                    THEN
                        CREATE ROLE {POSTGREST_LOGIN}
                            LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
                            PASSWORD '{POSTGREST_PASSWORD}';
                    END IF;
                END
                $$;
                """
            )
            cursor.execute(f"ALTER ROLE {POSTGREST_LOGIN} WITH PASSWORD '{POSTGREST_PASSWORD}'")
            cursor.execute(f"GRANT authenticated TO {POSTGREST_LOGIN}")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {POSTGREST_LOGIN}")
            cursor.execute(f"GRANT USAGE ON SCHEMA auth TO {POSTGREST_LOGIN}")

    parsed = urllib.parse.urlparse(request_database_url)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""

    return f"postgresql://{POSTGREST_LOGIN}:{POSTGREST_PASSWORD}@{host}{port}{parsed.path}"


@pytest.fixture
def dispatch(migrated_database: str) -> JobDispatchRepository:
    """The real dispatcher, over the privileged connection."""

    class _Secret:
        def __init__(self, value: str) -> None:
            self._value = value

        def get_secret_value(self) -> str:
            return self._value

    class _Settings:
        database_url = _Secret(migrated_database)
        database_health_timeout_seconds = 10

    return JobDispatchRepository(_Settings())  # type: ignore[arg-type]


# ------------------------------------------------------------------ calling --


def open_session(url: str, user_id: uuid.UUID) -> psycopg.Connection:
    """Open a connection acting as one authenticated user, as the API does.

    `SET ROLE authenticated` plus the JWT claim, which is exactly what
    `RequestSessionFactory` runs per transaction -- so what these tests exercise
    is the session a real request meets, over the real login.
    """
    connection = psycopg.connect(url)

    with connection.cursor() as cursor:
        cursor.execute("SET ROLE authenticated")
        cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (str(user_id),))

    return connection


def call(url: str, user_id: uuid.UUID, sql: str, params: tuple[Any, ...] = ()) -> Any:
    """Invoke one command over a tenant session and commit, returning its result."""
    connection = open_session(url, user_id)

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()

        connection.commit()
    finally:
        connection.close()

    return None if row is None else row[0]


#: The workspace a helper acts in defaults to the actor's own. Every test where
#: the actor's *membership* is the question -- a member of someone else's
#: workspace, a stranger reaching in -- passes it explicitly, because
#: `seed_identity` gives every identity a workspace of its own where it is the
#: owner, and defaulting to that would quietly answer a different question.
def start_run(
    url: str,
    actor: Identity,
    project_id: uuid.UUID | None = None,
    workspace: uuid.UUID | None = None,
) -> uuid.UUID:
    """Start a run through the command, and return its id."""
    return call(  # type: ignore[no-any-return]
        url,
        actor.user_id,
        "SELECT public.app_start_workflow_run("
        "%s::uuid, %s::text, %s::integer, %s::uuid, %s::jsonb, %s::text)",
        (workspace or actor.workspace_id, "project_planning", 1, project_id, "{}", "req-test"),
    )


def approve(
    url: str,
    actor: Identity,
    run_id: uuid.UUID,
    step_index: int,
    workspace: uuid.UUID | None = None,
) -> uuid.UUID:
    """Approve one step through the command, and return the job it enqueued."""
    return call(  # type: ignore[no-any-return]
        url,
        actor.user_id,
        "SELECT public.app_approve_workflow_step(%s::uuid, %s::uuid, %s::integer, %s::text)",
        (workspace or actor.workspace_id, run_id, step_index, "req-test"),
    )


def recover(
    url: str,
    actor: Identity,
    run_id: uuid.UUID,
    step_index: int,
    gated: bool,
    workspace: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Recover a failed run through the command, returning the replacement job id."""
    return call(
        url,
        actor.user_id,
        "SELECT public.app_recover_workflow_run("
        "%s::uuid, %s::uuid, %s::integer, %s::boolean, %s::text)",
        (workspace or actor.workspace_id, run_id, step_index, gated, "req-test"),
    )


def admit(
    url: str,
    actor: Identity,
    run_id: uuid.UUID,
    job_id: uuid.UUID,
    lease: uuid.UUID,
    step_index: int = 0,
    step_name: str = "plan",
    requires_approval: bool = False,
    replayable: bool = False,
) -> uuid.UUID | None:
    """Admit one step through the command, returning its claim token."""
    return call(
        url,
        actor.user_id,
        "SELECT public.app_admit_workflow_step("
        "%s::uuid, %s::uuid, %s::integer, %s::text, %s::boolean, %s::boolean, "
        "%s::uuid, %s::uuid)",
        (
            actor.workspace_id,
            run_id,
            step_index,
            step_name,
            requires_approval,
            replayable,
            job_id,
            lease,
        ),
    )


def settle(
    url: str,
    actor: Identity,
    run_id: uuid.UUID,
    job_id: uuid.UUID,
    lease: uuid.UUID,
    claim: uuid.UUID | None,
    step_index: int = 0,
    step_name: str = "plan",
    status: str = StepStatus.COMPLETED,
) -> bool:
    """Settle one step through the command, returning whether it was written."""
    return call(  # type: ignore[no-any-return]
        url,
        actor.user_id,
        "SELECT public.app_settle_workflow_step("
        "%s::uuid, %s::uuid, %s::integer, %s::text, %s::text, %s::text, "
        "%s::jsonb, %s::integer, %s::uuid, %s::uuid, %s::uuid)",
        (
            actor.workspace_id,
            run_id,
            step_index,
            step_name,
            status,
            "done",
            None,
            0,
            job_id,
            lease,
            claim,
        ),
    )


# ------------------------------------------------------------------ reading --


def run_row(connection: psycopg.Connection, run_id: uuid.UUID) -> dict[str, Any]:
    """Return one run as a mapping, over the owner connection."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, detail, finished_at FROM public.workflow_runs WHERE id = %s",
            (run_id,),
        )
        row = cursor.fetchone()

    assert row is not None, f"run {run_id} not found"

    return {"status": row[0], "detail": row[1], "finished_at": row[2]}


def step_row(connection: psycopg.Connection, run_id: uuid.UUID, step_index: int) -> dict[str, Any]:
    """Return one step row as a mapping, including the columns a client cannot read."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, detail, approved_by, claim_token, claimed_by_job_id, "
            "claimed_by_lease_token, tokens_used FROM public.workflow_step_runs "
            "WHERE run_id = %s AND step_index = %s",
            (run_id, step_index),
        )
        row = cursor.fetchone()

    assert row is not None, f"step {step_index} of run {run_id} not found"

    return {
        "status": row[0],
        "detail": row[1],
        "approved_by": row[2],
        "claim_token": row[3],
        "claimed_by_job_id": row[4],
        "claimed_by_lease_token": row[5],
        "tokens_used": row[6],
    }


def maybe_step_row(
    connection: psycopg.Connection, run_id: uuid.UUID, step_index: int
) -> dict[str, Any] | None:
    """Return one step row, or None when the step has never been recorded."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM public.workflow_step_runs WHERE run_id = %s AND step_index = %s",
            (run_id, step_index),
        )

        if cursor.fetchone() is None:
            return None

    return step_row(connection, run_id, step_index)


def live_jobs(connection: psycopg.Connection, run_id: uuid.UUID) -> list[uuid.UUID]:
    """Return every pending or running job linked to a run."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM public.jobs WHERE workflow_run_id = %s AND deleted_at IS NULL "
            "AND status IN ('pending', 'running') ORDER BY created_at",
            (run_id,),
        )

        return [row[0] for row in cursor.fetchall()]


def claim_job(dispatch: JobDispatchRepository) -> Any:
    """Claim the next job as a worker does, returning the claim."""
    claimed, _reaped = dispatch.claim("test-worker", LONG_LEASE)

    assert claimed is not None, "no job was claimable"

    return claimed


def snapshot(connection: psycopg.Connection) -> dict[str, int]:
    """Count every table a command could write, for a before/after comparison.

    Asserting on the error alone would pass an implementation that raised
    *after* doing its work. Comparing counts is what makes "changes nothing"
    a claim about state rather than about control flow.
    """
    counts: dict[str, int] = {}

    with connection.cursor() as cursor:
        for table in ("workflow_runs", "workflow_step_runs", "jobs", "audit_log"):
            cursor.execute(f"SELECT count(*) FROM public.{table}")  # noqa: S608 - fixed list
            row = cursor.fetchone()
            counts[table] = 0 if row is None else int(row[0])

        cursor.execute(
            "SELECT count(*) FROM public.workflow_step_runs "
            "WHERE approved_by IS NOT NULL OR claim_token IS NOT NULL"
        )
        row = cursor.fetchone()
        counts["execution_state"] = 0 if row is None else int(row[0])

    return counts


# ------------------------------------------------------------- containment --


class TestContainment:
    """The eight conditions `postgres` ownership was approved subject to.

    Each is asserted against the catalog rather than against the migration's
    source, because what protects the database is what is *installed* in it.
    """

    def test_every_command_is_a_definer_with_a_pinned_search_path(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """`SECURITY DEFINER` with `SET search_path = ''` on all five.

        An unpinned `search_path` on a definer function is a privilege
        escalation: a caller who can create a schema earlier in the path can
        shadow any unqualified name the body uses and have it run as the owner.
        """
        for name, args in COMMANDS:
            with admin_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT prosecdef, proconfig FROM pg_proc WHERE oid = %s::regprocedure",
                    (f"public.{name}({args})",),
                )
                row = cursor.fetchone()

            assert row is not None, f"{name} is not installed"
            assert row[0] is True, f"{name} is not SECURITY DEFINER"
            assert any(setting.startswith("search_path=") for setting in (row[1] or [])), (
                f"{name} does not pin its search_path"
            )

    def test_the_command_owner_can_reach_every_tenant(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """The owner is a role RLS does not apply to, which is why this works.

        Asserted as the *property* rather than as the name `postgres`: what makes
        a definer command able to write a claim on behalf of a member is that its
        owner is not subject to row security, and a deployment whose migration
        role differs by name still has to satisfy that.
        """
        for name, args in COMMANDS:
            with admin_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT r.rolsuper OR r.rolbypassrls FROM pg_proc p "
                    "JOIN pg_roles r ON r.oid = p.proowner "
                    "WHERE p.oid = %s::regprocedure",
                    (f"public.{name}({args})",),
                )
                row = cursor.fetchone()

            assert row is not None and row[0] is True, (
                f"{name} is owned by a role row security still applies to"
            )

    def test_no_command_body_builds_a_statement_from_a_string(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """No `EXECUTE`, no `format(`, no concatenated SQL.

        A definer function that builds SQL from its arguments runs whatever the
        caller managed to smuggle into one, with the owner's rights.
        """
        for name, args in COMMANDS:
            body = _body(admin_connection, name, args).lower()

            for forbidden in ("execute ", "format(", "quote_ident", "||'"):
                assert forbidden not in body, f"{name} builds SQL dynamically: `{forbidden}`"

    def test_every_table_reference_is_schema_qualified(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """`public.` on every table, which is what makes the pinned path usable."""
        for name, args in COMMANDS:
            body = _body(admin_connection, name, args)

            for table in PERMITTED_TABLES:
                for keyword in ("FROM ", "INTO ", "UPDATE "):
                    assert f"{keyword}{table}" not in body, (
                        f"{name} names `{table}` without its schema"
                    )

    def test_commands_touch_only_the_tables_the_decision_names(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """The statement boundary, asserted from the installed bodies.

        A command that grew a join to `projects` or `users` would be reading
        tenant data under the owner's rights, which is the one thing a definer
        function must not quietly start doing.
        """
        for name, args in COMMANDS:
            body = _body(admin_connection, name, args)

            for table in _tables_named(body):
                assert table in PERMITTED_TABLES, f"{name} references public.{table}"

            assert not re.search(r"\bDELETE\b", body.upper()), f"{name} deletes rows"
            assert not re.search(r"\bTRUNCATE\b", body.upper()), f"{name} truncates"

    def test_execution_is_granted_only_where_it_is_required(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """`authenticated` yes; `anon`, `service_role` and PUBLIC no.

        `anon` is named explicitly because `c4f21a86b3de` proved against a real
        database that revoking from PUBLIC does **not** cover it here.
        """
        for name, args in COMMANDS:
            signature = f"public.{name}({args})"

            with admin_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_function_privilege('authenticated', %s, 'EXECUTE'), "
                    "has_function_privilege('anon', %s, 'EXECUTE'), "
                    "has_function_privilege('service_role', %s, 'EXECUTE')",
                    (signature, signature, signature),
                )
                row = cursor.fetchone()

            assert row is not None
            assert row[0] is True, f"{name} is not executable by the role the application uses"
            assert row[1] is False, f"{name} is executable by anon"
            assert row[2] is False, f"{name} is executable by service_role"

    def test_no_command_takes_an_actor(self, admin_connection: psycopg.Connection) -> None:
        """The actor is always `auth.uid()`, never a parameter.

        A command taking an actor id would let any caller name anyone -- and an
        approval naming someone else is precisely the forgery this design exists
        to make unexpressible.
        """
        for name, args in COMMANDS:
            with admin_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT proargnames FROM pg_proc WHERE oid = %s::regprocedure",
                    (f"public.{name}({args})",),
                )
                row = cursor.fetchone()

            assert row is not None
            names = row[0] or []

            for argument in names:
                assert "actor" not in argument, f"{name} takes an actor parameter: {argument}"
                assert argument not in ("p_user_id", "p_approved_by", "p_triggered_by"), (
                    f"{name} takes an identity parameter: {argument}"
                )

            assert "auth.uid()" in _body(admin_connection, name, args)

    def test_every_command_returns_a_scalar(self, admin_connection: psycopg.Connection) -> None:
        """A uuid or a boolean, never a row and never a set.

        A command returning `SETOF` a tenant table would be a read path wearing a
        command's name, and would be the easiest way for this boundary to leak.
        """
        for name, args in COMMANDS:
            with admin_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT format_type(prorettype, NULL), proretset FROM pg_proc "
                    "WHERE oid = %s::regprocedure",
                    (f"public.{name}({args})",),
                )
                row = cursor.fetchone()

            assert row is not None
            assert row[0] in ("uuid", "boolean"), f"{name} returns {row[0]}"
            assert row[1] is False, f"{name} returns a set"

    def test_the_enqueued_ceiling_matches_the_handler(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """The retry ceiling is fixed in three places, and they must agree.

        `MAX_JOB_ATTEMPTS`, the CHECK constraint on `jobs`, and the literal
        inside every command that enqueues. Asserted rather than trusted to have
        been edited together -- the defect STEP-21 paid for on `assets.kind`.
        """
        for name in (
            "app_start_workflow_run",
            "app_approve_workflow_step",
            "app_recover_workflow_run",
        ):
            args = dict(COMMANDS)[name]
            body = " ".join(_body(admin_connection, name, args).split())

            assert f"'{WORKFLOW_JOB_TYPE}'" in body, f"{name} does not fix the job type"
            assert f"'pending', {MAX_JOB_ATTEMPTS}," in body, (
                f"{name} does not enqueue at MAX_JOB_ATTEMPTS={MAX_JOB_ATTEMPTS}"
            )


def _body(connection: psycopg.Connection, name: str, args: str) -> str:
    """Return a command's installed source, from `pg_proc`."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT prosrc FROM pg_proc WHERE oid = %s::regprocedure",
            (f"public.{name}({args})",),
        )
        row = cursor.fetchone()

    assert row is not None, f"{name} is not installed"

    return str(row[0])


def _tables_named(body: str) -> set[str]:
    """Return every `public.<table>` a body references."""
    return {
        match.group(1)
        for match in re.finditer(r"public\.([a-z_]+)", body)
        if not match.group(1).startswith("app_")
    }


# ------------------------------------------------------- the caller boundary --


class TestTheCallerBoundary:
    """The one thing separating the application from a stranger holding a JWT.

    Both reach `current_user = authenticated`. Only the **login** differs, and a
    login cannot be changed without superuser.
    """

    def test_the_application_connection_is_the_login_the_commands_accept(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """`session_user = projectone_api`, `current_user = authenticated`, actor intact."""
        connection = open_session(request_database_url, tenants.owner.user_id)

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT session_user, current_user, auth.uid()")
                row = cursor.fetchone()
        finally:
            connection.close()

        assert row is not None
        assert row[0] == APPLICATION_LOGIN
        assert row[1] == "authenticated"
        assert row[2] == tenants.owner.user_id

    def test_a_direct_client_reaches_the_same_role_under_a_different_login(
        self, postgrest_url: str, tenants: Workspace
    ) -> None:
        """**The fact the whole boundary rests on.**

        A PostgREST-shaped caller is indistinguishable from the application by
        role, by policy and by `auth.uid()`. `session_user` is the only thing
        that differs, and it is asserted here before it is relied on.
        """
        connection = open_session(postgrest_url, tenants.owner.user_id)

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT session_user, current_user, auth.uid()")
                row = cursor.fetchone()
        finally:
            connection.close()

        assert row is not None
        assert row[0] == POSTGREST_LOGIN
        assert row[1] == "authenticated", "the stand-in does not reach the role it must"
        assert row[2] == tenants.owner.user_id, "the stand-in is not the actor it claims"

    def test_every_command_refuses_a_direct_client_and_writes_nothing(
        self, postgrest_url: str, admin_connection: psycopg.Connection, tenants: Workspace
    ) -> None:
        """**The proof, not the argument.**

        Every command, called directly, as the workspace **owner** -- the most
        privileged caller there is. Each raises `42501`, and the table counts are
        identical afterwards: no run, no job, no grant, no claim, no audit row.
        Asserting the error alone would pass an implementation that raised after
        doing its work.
        """
        before = snapshot(admin_connection)
        run_id = uuid.uuid4()
        token = uuid.uuid4()

        attempts = (
            (
                "SELECT public.app_start_workflow_run("
                "%s::uuid, %s::text, %s::integer, %s::uuid, %s::jsonb, %s::text)",
                (tenants.id, "project_planning", 1, None, "{}", None),
            ),
            (
                "SELECT public.app_approve_workflow_step("
                "%s::uuid, %s::uuid, %s::integer, %s::text)",
                (tenants.id, run_id, 0, None),
            ),
            (
                "SELECT public.app_recover_workflow_run("
                "%s::uuid, %s::uuid, %s::integer, %s::boolean, %s::text)",
                (tenants.id, run_id, 0, False, None),
            ),
            (
                "SELECT public.app_admit_workflow_step("
                "%s::uuid, %s::uuid, %s::integer, %s::text, %s::boolean, %s::boolean, "
                "%s::uuid, %s::uuid)",
                (tenants.id, run_id, 0, "plan", False, False, token, token),
            ),
            (
                "SELECT public.app_settle_workflow_step("
                "%s::uuid, %s::uuid, %s::integer, %s::text, %s::text, %s::text, "
                "%s::jsonb, %s::integer, %s::uuid, %s::uuid, %s::uuid)",
                (tenants.id, run_id, 0, "plan", "completed", None, None, 0, token, token, token),
            ),
        )

        for actor in (tenants.owner, tenants.member, tenants.stranger):
            for sql, params in attempts:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    call(postgrest_url, actor.user_id, sql, params)

        assert snapshot(admin_connection) == before, (
            "a direct client changed state before being refused"
        )

    def test_a_direct_client_cannot_forge_the_login(
        self, postgrest_url: str, tenants: Workspace
    ) -> None:
        """Every surface a caller controls, tried in turn.

        `SET ROLE`, a JWT claim, an arbitrary GUC, `set_config`, and
        `SET SESSION AUTHORIZATION`. Each either errors or leaves `session_user`
        untouched -- there is nothing to steal, nothing to replay and nothing to
        leak, because the value is asserted by the database at connection time
        from a credential the client does not hold.
        """
        connection = open_session(postgrest_url, tenants.owner.user_id)

        try:
            with connection.cursor() as cursor:
                for statement, parameters in (
                    (f"SET ROLE {APPLICATION_LOGIN}", ()),
                    ("SELECT set_config('session_user', %s, false)", (APPLICATION_LOGIN,)),
                    ("SELECT set_config('role', %s, false)", (APPLICATION_LOGIN,)),
                    (
                        "SELECT set_config('request.jwt.claim.role', %s, false)",
                        (APPLICATION_LOGIN,),
                    ),
                    (f"SET SESSION AUTHORIZATION {APPLICATION_LOGIN}", ()),
                ):
                    try:
                        cursor.execute(statement, parameters)  # type: ignore[arg-type]
                    except psycopg.Error:
                        connection.rollback()
                        cursor.execute("SET ROLE authenticated")

                    cursor.execute("SELECT session_user")
                    row = cursor.fetchone()

                    assert row is not None
                    assert row[0] == POSTGREST_LOGIN, (
                        f"`{statement}` changed session_user; the boundary is forgeable"
                    )
        finally:
            connection.close()

    def test_the_guard_names_one_hard_coded_login(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """**The architectural test ADR-006 I21 asks for.**

        It fails if the check is removed from any command, if the accepted login
        becomes a parameter, a GUC or a list, if a second login is accepted, or
        if `authenticator` ever appears in a body.
        """
        for name, args in COMMANDS:
            body = _body(admin_connection, name, args)

            assert f"session_user <> '{APPLICATION_LOGIN}'" in body, (
                f"{name} does not check the application login as a literal"
            )
            assert body.count("session_user") == 1, (
                f"{name} reads session_user more than once; the check must be one equality"
            )
            assert "current_setting" not in body, f"{name} reads a GUC"
            assert "authenticator" not in body, f"{name} names Supabase's login"
            assert "IN (" not in body.split("session_user")[1][:120], (
                f"{name} accepts a list of logins rather than one"
            )

    def test_the_guard_runs_before_anything_else(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """First, so a refused call touches nothing rather than being rolled back.

        Asserted positionally: the login check appears before the first `SELECT`,
        `INSERT` or `UPDATE` in every body.
        """
        for name, args in COMMANDS:
            body = _body(admin_connection, name, args)
            guard = body.index("session_user")

            for keyword in ("SELECT", "INSERT", "UPDATE"):
                if keyword in body:
                    assert guard < body.index(keyword), (
                        f"{name} reads or writes before checking its caller"
                    )

    def test_the_worker_path_works_and_reads_nothing_wider(
        self, request_database_url: str, tenants: Workspace, dispatch: JobDispatchRepository
    ) -> None:
        """The commands do work over the application login, and only there.

        The other half of the boundary: a guard that refused everyone would pass
        every test above.
        """
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)

        claim = admit(request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token)

        assert claim is not None
        assert settle(
            request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token, claim
        )

        connection = open_session(request_database_url, tenants.owner.user_id)

        try:
            with connection.cursor() as cursor:
                # Still cannot read a fence, and still cannot see another tenant.
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute("SELECT claim_token FROM public.workflow_step_runs")

                connection.rollback()
                cursor.execute("SET ROLE authenticated")
                cursor.execute(
                    "SELECT set_config('request.jwt.claim.sub', %s, false)",
                    (str(tenants.owner.user_id),),
                )
                cursor.execute(
                    "SELECT count(*) FROM public.workflow_runs WHERE workspace_id = %s",
                    (tenants.stranger.workspace_id,),
                )
                row = cursor.fetchone()

            assert row is not None and row[0] == 0
        finally:
            connection.close()


def concurrently(count: int, work: Any) -> tuple[list[Any], list[BaseException]]:
    """Run `work(index)` in `count` threads that start together.

    A barrier rather than a sleep: what these tests ask is what PostgreSQL does
    when two transactions genuinely contend, and a stagger large enough to be
    reliable is a stagger large enough to serialise them by accident.
    """
    results: list[Any] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(count)

    def run(index: int) -> None:
        barrier.wait()

        try:
            results.append(work(index))
        except BaseException as error:  # noqa: BLE001 - collected and asserted on
            errors.append(error)

    threads = [threading.Thread(target=run, args=(index,)) for index in range(count)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=30)

    return results, errors


# ------------------------------------------------------------ client grants --


class TestWhatAClientCanReachDirectly:
    """The grants, asked of the database rather than of the user interface.

    "No endpoint exposes that column" is not an answer here: PostgREST is an
    endpoint this application does not control, and a member holding their own
    Supabase JWT reaches these tables as `authenticated` whatever the routes do.
    """

    def test_a_member_cannot_write_execution_state(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """**The forgery this design exists to make impossible.**

        A member writing `approved_by` would grant themselves the owner's
        approval and detonate the CLAUDE.md §15 gate; a member writing
        `claim_token` would take or release a fence. Both are refused by
        privilege, before any policy is consulted.
        """
        run_id = start_run(request_database_url, tenants.owner)
        connection = open_session(request_database_url, tenants.member.user_id)

        try:
            for column, value in (
                ("approved_by", str(tenants.owner.user_id)),
                ("claim_token", str(uuid.uuid4())),
                ("claimed_by_job_id", str(uuid.uuid4())),
                ("claimed_by_lease_token", str(uuid.uuid4())),
                ("status", "completed"),
            ):
                with (
                    connection.cursor() as cursor,
                    pytest.raises(psycopg.errors.InsufficientPrivilege),
                ):
                    cursor.execute(
                        f"UPDATE public.workflow_step_runs SET {column} = %s "  # noqa: S608
                        "WHERE run_id = %s",
                        (value, run_id),
                    )

                connection.rollback()
                _reset_session(connection, tenants.member.user_id)

            with connection.cursor() as cursor, pytest.raises(psycopg.errors.InsufficientPrivilege):
                cursor.execute(
                    "INSERT INTO public.workflow_step_runs "
                    "(workspace_id, run_id, step_index, step_name, status) "
                    "VALUES (%s, %s, 0, 'forged', 'completed')",
                    (tenants.id, run_id),
                )
        finally:
            connection.close()

    def test_a_member_can_still_erase(
        self, request_database_url: str, admin_connection: psycopg.Connection, tenants: Workspace
    ) -> None:
        """**Erasure is unbroken**, which is the half a narrowed grant could break.

        `UPDATE (deleted_at)` is exactly what workspace erasure needs, and a
        migration that took the whole grant would make a workspace impossible to
        forget (CLAUDE.md §16).
        """
        run_id = start_run(request_database_url, tenants.owner)

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.workflow_step_runs "
                "(workspace_id, run_id, step_index, step_name, status) "
                "VALUES (%s, %s, 0, 'plan', 'pending')",
                (tenants.id, run_id),
            )

        connection = open_session(request_database_url, tenants.owner.user_id)

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.workflow_step_runs SET deleted_at = now() WHERE run_id = %s",
                    (run_id,),
                )

                assert cursor.rowcount == 1

            connection.commit()
        finally:
            connection.close()

    def test_no_fencing_token_is_readable_by_a_client(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """**A fence a client can read is a capability, not a fence.**

        A member who could read `jobs.lease_token` could forge a claim that
        satisfied the lease predicate; one who could read `claim_token` could
        settle a step they never ran.
        """
        start_run(request_database_url, tenants.owner)
        connection = open_session(request_database_url, tenants.owner.user_id)

        try:
            for statement in (
                "SELECT lease_token FROM public.jobs",
                "SELECT claim_token FROM public.workflow_step_runs",
                "SELECT claimed_by_lease_token FROM public.workflow_step_runs",
                # Not a fence -- a timestamp -- but nothing on the tenant path
                # reads it, so ADR-006 v1.6 revokes it rather than grant a
                # column no caller consumes.
                "SELECT lease_expires_at FROM public.jobs",
                "SELECT * FROM public.jobs",
                "SELECT * FROM public.workflow_step_runs",
            ):
                with (
                    connection.cursor() as cursor,
                    pytest.raises(psycopg.errors.InsufficientPrivilege),
                ):
                    cursor.execute(statement)

                connection.rollback()
                _reset_session(connection, tenants.owner.user_id)
        finally:
            connection.close()

    def test_a_member_still_sees_everything_else(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """The narrowing took a fence, not the product.

        A member can still read their workspace's runs and queue -- status,
        history, cost, failure detail, and who approved. A control nobody can
        inspect is one nobody can audit.
        """
        run_id = start_run(request_database_url, tenants.owner)
        connection = open_session(request_database_url, tenants.member.user_id)

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, workspace_id, job_type, status, attempts, max_attempts, "
                    "last_error, workflow_run_id FROM public.jobs "
                    "WHERE workflow_run_id = %s",
                    (run_id,),
                )

                assert cursor.fetchone() is not None

                cursor.execute(
                    "SELECT step_index, step_name, status, detail, tokens_used, output, "
                    "approved_by FROM public.workflow_step_runs WHERE run_id = %s",
                    (run_id,),
                )
                cursor.fetchall()
        finally:
            connection.close()


def _reset_session(connection: psycopg.Connection, user_id: uuid.UUID) -> None:
    """Re-establish the tenant session after a rollback.

    A rollback reverts the session-scoped `SET ROLE`, leaving the connection as
    `projectone_api` -- which is `NOINHERIT` and therefore holds nothing at all.
    The next statement then fails with a permission error that looks exactly like
    the assertion under test failing, and is not. The same fail-closed property
    the request path depends on, surfacing where nobody expects it.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET ROLE authenticated")
        cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (str(user_id),))


# ---------------------------------------------------------- the enqueue door --


class TestTheEnqueueDoor:
    """Two rules that compose into a closed door, and neither is enough alone."""

    def test_a_direct_insert_cannot_set_a_run_link(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """The INSERT policy forces the link to be NULL.

        Without this a member could occupy the partial unique key for any run in
        their workspace and **block every legitimate start, approval and resume
        for it** -- a denial of service, not a forgery, which is the half an
        earlier draft of this design missed entirely.
        """
        run_id = start_run(request_database_url, tenants.owner)
        connection = open_session(request_database_url, tenants.owner.user_id)

        try:
            for job_type in (WORKFLOW_JOB_TYPE, "tenant_probe"):
                with connection.cursor() as cursor, pytest.raises(psycopg.Error):
                    cursor.execute(
                        "INSERT INTO public.jobs "
                        "(workspace_id, enqueued_by, job_type, max_attempts, workflow_run_id) "
                        "VALUES (%s, %s, %s, 1, %s)",
                        (tenants.id, tenants.owner.user_id, job_type, run_id),
                    )

                connection.rollback()
                _reset_session(connection, tenants.owner.user_id)
        finally:
            connection.close()

    def test_a_direct_insert_cannot_construct_a_workflow_job(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """And the CHECK closes the other half.

        With the link forced to NULL, `job_type = 'workflow.execute'` is refused
        by `ck_jobs_workflow_link_matches_type`. No combination of type and
        payload produces a workflow job, and a payload naming a run on some other
        job type drives nothing at all.
        """
        connection = open_session(request_database_url, tenants.owner.user_id)

        try:
            with connection.cursor() as cursor, pytest.raises(psycopg.errors.CheckViolation):
                cursor.execute(
                    "INSERT INTO public.jobs "
                    "(workspace_id, enqueued_by, job_type, max_attempts) "
                    "VALUES (%s, %s, %s, 1)",
                    (tenants.id, tenants.owner.user_id, WORKFLOW_JOB_TYPE),
                )
        finally:
            connection.close()

    def test_the_link_cannot_cross_a_workspace(
        self, request_database_url: str, admin_connection: psycopg.Connection, tenants: Workspace
    ) -> None:
        """Two independent gates, asserted independently.

        The policy refuses a cross-workspace link, and the composite foreign key
        refuses it again with the policy out of the way. Neither is load-bearing
        alone: a link that was only checked by a policy would be an unchecked
        claim the moment a definer function wrote one.
        """
        # A run in the other workspace with **no** live job, so the unique index
        # cannot answer before the constraints under test do.
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.workflow_runs "
                "(workspace_id, workflow_type, definition_version, status, triggered_by) "
                "VALUES (%s, 'project_planning', 1, 'pending', %s) RETURNING id",
                (tenants.stranger.workspace_id, tenants.stranger.user_id),
            )
            row = cursor.fetchone()

        assert row is not None
        stranger_run = row[0]

        connection = open_session(request_database_url, tenants.owner.user_id)

        try:
            with connection.cursor() as cursor, pytest.raises(psycopg.Error):
                cursor.execute(
                    "INSERT INTO public.jobs "
                    "(workspace_id, enqueued_by, job_type, max_attempts, workflow_run_id) "
                    "VALUES (%s, %s, %s, 1, %s)",
                    (tenants.id, tenants.owner.user_id, WORKFLOW_JOB_TYPE, stranger_run),
                )
        finally:
            connection.close()

        # And again with RLS out of the picture entirely: the foreign key is what
        # answers, so even the table owner cannot write a cross-tenant link.
        with admin_connection.cursor() as cursor, pytest.raises(psycopg.errors.ForeignKeyViolation):
            cursor.execute(
                "INSERT INTO public.jobs "
                "(workspace_id, enqueued_by, job_type, max_attempts, workflow_run_id) "
                "VALUES (%s, %s, %s, 1, %s)",
                (tenants.id, tenants.owner.user_id, WORKFLOW_JOB_TYPE, stranger_run),
            )

    def test_the_link_is_not_client_writable_afterwards(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """Creation is closed by the policy; mutation is closed by the write guard.

        A link a member could repoint would let them aim a live job at a
        different run -- and the reconciliation that follows would fail the wrong
        one.
        """
        run_id = start_run(request_database_url, tenants.owner)
        other_run = start_run(request_database_url, tenants.owner)

        connection = open_session(request_database_url, tenants.owner.user_id)

        try:
            with connection.cursor() as cursor, pytest.raises(psycopg.Error):
                cursor.execute(
                    "UPDATE public.jobs SET workflow_run_id = %s WHERE workflow_run_id = %s",
                    (other_run, run_id),
                )
        finally:
            connection.close()

    def test_the_index_admits_one_live_job_per_run(
        self, request_database_url: str, admin_connection: psycopg.Connection, tenants: Workspace
    ) -> None:
        """**The final concurrency authority, asserted as a constraint.**

        No command decides whether a second live job may exist; they all attempt
        the insert and let PostgreSQL serialise. Asserted here as the table owner,
        with every policy and command out of the way, because what must hold is
        the *constraint* rather than any caller's discipline.
        """
        run_id = start_run(request_database_url, tenants.owner)

        with admin_connection.cursor() as cursor, pytest.raises(psycopg.errors.UniqueViolation):
            cursor.execute(
                "INSERT INTO public.jobs "
                "(workspace_id, enqueued_by, job_type, max_attempts, workflow_run_id) "
                "VALUES (%s, %s, %s, 2, %s)",
                (tenants.id, tenants.owner.user_id, WORKFLOW_JOB_TYPE, run_id),
            )

    def test_a_settled_job_leaves_the_live_set(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """Which is what lets a recovery enqueue a replacement at all.

        The index is partial on `pending` and `running`; a dead-lettered job is
        outside it, so the door reopens exactly when delivery is over.
        """
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)

        dispatch.record_outcome(
            claimed.id, claimed.lease_token, JobOutcome(status=JobStatus.DEAD_LETTERED)
        )

        assert live_jobs(admin_connection, run_id) == []

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.jobs "
                "(workspace_id, enqueued_by, job_type, max_attempts, workflow_run_id) "
                "VALUES (%s, %s, %s, 2, %s)",
                (tenants.id, tenants.owner.user_id, WORKFLOW_JOB_TYPE, run_id),
            )

        assert len(live_jobs(admin_connection, run_id)) == 1


# --------------------------------------------------------- start and approve --


class TestStartingAndApproving:
    """The two complete domain transitions a client-facing route reaches."""

    def test_starting_creates_a_run_and_exactly_one_live_job(
        self, request_database_url: str, admin_connection: psycopg.Connection, tenants: Workspace
    ) -> None:
        """**Transactional enqueue**: a run with no job cannot be produced here.

        Both inserts are in the caller's transaction, which is the first property
        ADR-005 §1 chose a database-backed queue for.
        """
        run_id = start_run(request_database_url, tenants.owner)

        assert run_row(admin_connection, run_id)["status"] == RunStatus.PENDING

        jobs = live_jobs(admin_connection, run_id)

        assert len(jobs) == 1

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT job_type, max_attempts, enqueued_by FROM public.jobs WHERE id = %s",
                (jobs[0],),
            )
            row = cursor.fetchone()

        assert row is not None
        assert row[0] == WORKFLOW_JOB_TYPE
        assert row[1] == MAX_JOB_ATTEMPTS
        assert row[2] == tenants.owner.user_id, "the actor is not the one who called"

    def test_a_non_member_cannot_start_a_run(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """Membership is checked inside the command, not only by the route."""
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            call(
                request_database_url,
                tenants.stranger.user_id,
                "SELECT public.app_start_workflow_run("
                "%s::uuid, %s::text, %s::integer, %s::uuid, %s::jsonb, %s::text)",
                (tenants.id, "project_planning", 1, None, "{}", None),
            )

    def test_a_malformed_domain_value_is_refused(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """Every caller-supplied value is validated before anything is written."""
        for workflow_type, version in (("", 1), ("   ", 1), ("project_planning", 0)):
            with pytest.raises(psycopg.Error):
                call(
                    request_database_url,
                    tenants.owner.user_id,
                    "SELECT public.app_start_workflow_run("
                    "%s::uuid, %s::text, %s::integer, %s::uuid, %s::jsonb, %s::text)",
                    (tenants.id, workflow_type, version, None, "{}", None),
                )

    def test_approving_writes_the_grant_and_the_job_together(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**The grant and the job are inseparable.**

        A grant written without its job would leave a run carrying a live
        entitlement that some later, differently authorized path could spend.
        There is no way to obtain one without the other.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)

        job_id = approve(request_database_url, tenants.owner, run_id, 0)

        assert job_id is not None
        assert live_jobs(admin_connection, run_id) == [job_id]
        assert step_row(admin_connection, run_id, 0)["approved_by"] == tenants.owner.user_id

    def test_a_member_cannot_approve(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """Owner or admin only, checked inside the command.

        A gated step spends money or acts externally, which is the same class of
        consequence guarding AI keys and spend ceilings.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            approve(request_database_url, tenants.member, run_id, 0, workspace=tenants.id)

        assert step_row(admin_connection, run_id, 0)["approved_by"] is None
        assert live_jobs(admin_connection, run_id) == []

    def test_approval_is_pinned_to_the_step_the_run_is_waiting_on(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """A stale client approving "step 3" of a run waiting on step 0 is refused."""
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)

        with pytest.raises(psycopg.Error):
            approve(request_database_url, tenants.owner, run_id, 3)

        assert step_row(admin_connection, run_id, 0)["approved_by"] is None

    def test_an_unspent_grant_cannot_be_re_issued(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """A second approval over a live entitlement is refused, serially too.

        Otherwise "approve" would be a way to enqueue arbitrarily many jobs for
        one run, each of which the index would then have to refuse.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)
        approve(request_database_url, tenants.owner, run_id, 0)

        with pytest.raises(psycopg.Error):
            approve(request_database_url, tenants.owner, run_id, 0)

    def test_approving_a_run_that_is_not_waiting_is_refused(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """A client acting on stale state is told so rather than silently ignored."""
        run_id = start_run(request_database_url, tenants.owner)

        with pytest.raises(psycopg.Error):
            approve(request_database_url, tenants.owner, run_id, 0)

    def test_two_concurrent_approvals_consume_one_grant_and_create_one_job(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**Two owners clicking approve at the same instant.**

        The run's row lock serialises them and the partial unique index stands
        behind that; either way exactly one grant is consumed and exactly one job
        exists. The loser's grant rolls back with its transaction.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)

        results, errors = concurrently(
            4, lambda _index: approve(request_database_url, tenants.owner, run_id, 0)
        )

        assert len(results) == 1, f"{len(results)} approvals succeeded"
        assert len(errors) == 3
        assert len(live_jobs(admin_connection, run_id)) == 1


def _paused_at_gate(
    url: str,
    admin_connection: psycopg.Connection,
    tenants: Workspace,
    dispatch: JobDispatchRepository,
) -> uuid.UUID:
    """Return a run parked at an approval gate, reached the way a worker reaches it.

    Start, claim the job, discover the step is gated, record the pause, settle
    the job. Written out rather than seeded by hand so the state under test is
    one the system actually produces.
    """
    run_id = start_run(url, tenants.owner)
    claimed = claim_job(dispatch)

    with pytest.raises(psycopg.Error):
        admit(url, tenants.owner, run_id, claimed.id, claimed.lease_token, requires_approval=True)

    settled = settle(
        url,
        tenants.owner,
        run_id,
        claimed.id,
        claimed.lease_token,
        None,
        status=StepStatus.AWAITING_APPROVAL,
    )

    assert settled

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.workflow_runs SET status = %s WHERE id = %s",
            (RunStatus.AWAITING_APPROVAL, run_id),
        )

    dispatch.record_outcome(claimed.id, claimed.lease_token, JobOutcome(status=JobStatus.SUCCEEDED))

    return run_id


# ------------------------------------------------------- admission and claims --


class TestAdmissionAndClaims:
    """Entering a step: one execution, one grant, one lease."""

    def test_only_one_of_many_concurrent_executions_claims_a_step(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**The conditional claim, proven with real contention.**

        Four executions attempt one non-replayable step; exactly one receives a
        token. This is the shape `c8f1a3d54e29` verified for chat turns, one
        layer up -- and a claim that is conditional only in prose is not
        conditional at all.
        """
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)

        results, errors = concurrently(
            4,
            lambda _index: admit(
                request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token
            ),
        )

        tokens = [result for result in results if result is not None]

        assert len(tokens) == 1, f"{len(tokens)} executions claimed one step"
        assert len(errors) == 3
        assert step_row(admin_connection, run_id, 0)["claim_token"] == tokens[0]

    def test_a_replayable_step_is_admitted_without_a_claim(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """Claiming a pure step would strand a run on work always safe to repeat."""
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)

        token = admit(
            request_database_url,
            tenants.owner,
            run_id,
            claimed.id,
            claimed.lease_token,
            replayable=True,
        )

        assert token is None
        assert step_row(admin_connection, run_id, 0)["claim_token"] is None
        assert step_row(admin_connection, run_id, 0)["status"] == StepStatus.RUNNING

    def test_a_held_step_interrupts_a_replacement_execution(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**The case that would otherwise call a paid provider twice.**

        A replacement worker reaching a claimed step acquires nothing. It cannot
        prove the holder is dead, so it must not proceed and must not report
        success -- the repository turns this refusal into a terminal
        `StepInterruptedError`.
        """
        run_id = start_run(request_database_url, tenants.owner)
        first = claim_job(dispatch)
        held = admit(request_database_url, tenants.owner, run_id, first.id, first.lease_token)

        _expire_lease(admin_connection, first.id)
        second = claim_job(dispatch)

        with pytest.raises(psycopg.Error):
            admit(request_database_url, tenants.owner, run_id, second.id, second.lease_token)

        assert step_row(admin_connection, run_id, 0)["claim_token"] == held

    def test_admission_refuses_an_execution_that_lost_its_job(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """A lapsed lease must not admit the next step.

        The provider call that step would make is the cost this whole design
        exists to avoid.
        """
        run_id = start_run(request_database_url, tenants.owner)
        first = claim_job(dispatch)

        _expire_lease(admin_connection, first.id)
        claim_job(dispatch)

        with pytest.raises(psycopg.Error):
            admit(request_database_url, tenants.owner, run_id, first.id, first.lease_token)

        # The refusal rolls back the row admission would have created, so there
        # is nothing at all -- which is the strongest form of "wrote nothing".
        assert maybe_step_row(admin_connection, run_id, 0) is None

    def test_admission_consumes_the_grant_including_for_a_replayable_step(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**Consumption is tied to admission, not to the claim.**

        A step that is gated *and* replayable takes no claim, so tying
        consumption to the claim would leave its grant unspent forever -- and
        every redelivery would re-run a step a person approved once.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)
        approve(request_database_url, tenants.owner, run_id, 0)
        claimed = claim_job(dispatch)

        assert step_row(admin_connection, run_id, 0)["approved_by"] is not None

        admit(
            request_database_url,
            tenants.owner,
            run_id,
            claimed.id,
            claimed.lease_token,
            requires_approval=True,
            replayable=True,
        )

        assert step_row(admin_connection, run_id, 0)["approved_by"] is None

        # A redelivery of the same job finds nothing left to spend.
        with pytest.raises(psycopg.Error):
            admit(
                request_database_url,
                tenants.owner,
                run_id,
                claimed.id,
                claimed.lease_token,
                requires_approval=True,
                replayable=True,
            )

    def test_a_payload_cannot_grant_an_approval(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """Authorization comes from validated domain state, never from a blob.

        `jobs.payload` is client-writable on INSERT, so a payload-carried
        approval would be forgeable by any member.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.jobs "
                "(workspace_id, enqueued_by, job_type, payload, max_attempts, workflow_run_id) "
                "VALUES (%s, %s, %s, %s::jsonb, 2, %s)",
                (
                    tenants.id,
                    tenants.owner.user_id,
                    WORKFLOW_JOB_TYPE,
                    '{"approved": true, "approved_by": "anyone"}',
                    run_id,
                ),
            )

        claimed = claim_job(dispatch)

        with pytest.raises(psycopg.Error):
            admit(
                request_database_url,
                tenants.owner,
                run_id,
                claimed.id,
                claimed.lease_token,
                requires_approval=True,
            )


def _expire_lease(admin_connection: psycopg.Connection, job_id: uuid.UUID) -> None:
    """Push a job's lease into the past, so it becomes claimable again."""
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s",
            (job_id,),
        )


# ------------------------------------------------------------- settlement --


class TestSettlementIsFencedThreeWays:
    """Persisting a step requires the claim, the lease **and** a live run.

    The three are deliberately redundant: each closes a different window, and any
    one surviving a future refactor still fences the write. Each is defeated on
    its own below, so none of them is load-bearing alone.
    """

    def test_a_settle_requires_the_current_claim_token(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """A guessed or stale token writes nothing."""
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)
        admit(request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token)

        before = step_row(admin_connection, run_id, 0)

        assert not settle(
            request_database_url,
            tenants.owner,
            run_id,
            claimed.id,
            claimed.lease_token,
            uuid.uuid4(),
        )
        assert step_row(admin_connection, run_id, 0) == before

    def test_a_settle_requires_the_job_lease_that_took_the_claim(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**The at-least-once case, made survivable.**

        Worker A holds the claim; A's lease lapses and worker B claims the job,
        rotating `lease_token`. A finishes its provider call minutes later and
        tries to persist -- and matches nothing. The row is byte-for-byte what it
        was, and the run is untouched.
        """
        run_id = start_run(request_database_url, tenants.owner)
        first = claim_job(dispatch)
        claim = admit(request_database_url, tenants.owner, run_id, first.id, first.lease_token)

        before = step_row(admin_connection, run_id, 0)
        run_before = run_row(admin_connection, run_id)

        _expire_lease(admin_connection, first.id)
        claim_job(dispatch)

        assert not settle(
            request_database_url, tenants.owner, run_id, first.id, first.lease_token, claim
        )
        assert step_row(admin_connection, run_id, 0) == before
        assert run_row(admin_connection, run_id) == run_before

    def test_a_settle_is_refused_once_the_run_is_reconciled(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """The third predicate, and the one that closes the window after the fact.

        Reconciliation marks the run `failed` the instant delivery ends. A
        straggling execution finishing afterwards cannot mark its step completed,
        cannot advance the run, and cannot overwrite a recovery already in
        progress.
        """
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)
        claim = admit(request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token)

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workflow_runs SET status = 'failed' WHERE id = %s", (run_id,)
            )

        before = step_row(admin_connection, run_id, 0)

        assert not settle(
            request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token, claim
        )
        assert step_row(admin_connection, run_id, 0) == before

    def test_a_replayable_step_is_still_fenced_by_the_lease_and_the_run(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """Skipping the claim does not skip the other two.

        A replayable step is still not writable by an execution that has lost its
        job or whose run has already been reconciled.
        """
        run_id = start_run(request_database_url, tenants.owner)
        first = claim_job(dispatch)
        admit(
            request_database_url,
            tenants.owner,
            run_id,
            first.id,
            first.lease_token,
            replayable=True,
        )

        _expire_lease(admin_connection, first.id)
        claim_job(dispatch)

        assert not settle(
            request_database_url, tenants.owner, run_id, first.id, first.lease_token, None
        )

    def test_a_settle_that_wins_clears_the_claim(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """The claim is released only by a fenced write from its holder."""
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)
        claim = admit(request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token)

        assert settle(
            request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token, claim
        )

        row = step_row(admin_connection, run_id, 0)

        assert row["status"] == StepStatus.COMPLETED
        assert row["claim_token"] is None
        assert row["claimed_by_job_id"] is None
        assert row["claimed_by_lease_token"] is None


# ------------------------------------------------------------ reconciliation --


class TestReconciliation:
    """Every dead-lettered job carrying a run leaves that run terminal.

    Not only the ones that failed before a handler ran: the dispatcher cannot
    know *where* a job failed, only that delivery is over -- and a run left
    non-terminal when its job is abandoned was abandoned whatever stage it
    reached.
    """

    def test_a_dead_lettered_job_fails_its_run_in_the_same_commit(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """The settle leg, with a fixed public sentence rather than an error's text."""
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)

        settled = dispatch.record_outcome(
            claimed.id,
            claimed.lease_token,
            JobOutcome(status=JobStatus.DEAD_LETTERED, last_error="internal detail"),
        )

        assert settled.held
        assert settled.run_reconciled

        run = run_row(admin_connection, run_id)

        assert run["status"] == RunStatus.FAILED
        assert run["finished_at"] is not None
        assert run["detail"] is not None
        assert "internal detail" not in run["detail"], "an internal message reached the run"

    def test_the_reap_path_reconciles_with_no_worker_alive(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**The case that used to strand a run with nothing able to notice.**

        A worker died holding the job and never recorded an outcome. There is no
        tenant identity here to reconcile under and no later delivery to do it --
        which is why the reap carries the leg itself.
        """
        run_id = start_run(request_database_url, tenants.owner)

        for _attempt in range(MAX_JOB_ATTEMPTS):
            claimed = claim_job(dispatch)
            _expire_lease(admin_connection, claimed.id)

        _claimed, reaped = dispatch.claim("test-reaper", LONG_LEASE)

        assert len(reaped) == 1
        assert reaped[0].workflow_run_id == run_id
        assert run_row(admin_connection, run_id)["status"] == RunStatus.FAILED

    def test_a_terminal_run_is_never_overwritten(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**The whole safety of the rule.**

        A run the runner already failed keeps its own, more specific `detail`, and
        a completed run is never touched at all -- a job that dead-letters after
        its run finished must not rewrite history.
        """
        for status, detail in (
            (RunStatus.COMPLETED, "finished cleanly"),
            (RunStatus.FAILED, "the planning step did not produce a usable outline"),
        ):
            run_id = start_run(request_database_url, tenants.owner)
            claimed = claim_job(dispatch)

            with admin_connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.workflow_runs SET status = %s, detail = %s WHERE id = %s",
                    (status, detail, run_id),
                )

            settled = dispatch.record_outcome(
                claimed.id, claimed.lease_token, JobOutcome(status=JobStatus.DEAD_LETTERED)
            )

            assert settled.held
            assert not settled.run_reconciled

            run = run_row(admin_connection, run_id)

            assert run["status"] == status
            assert run["detail"] == detail

    def test_a_succeeding_job_leaves_a_paused_run_alone(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """A job that succeeds while its run waits at a gate is the healthy pause."""
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)

        assert run_row(admin_connection, run_id)["status"] == RunStatus.AWAITING_APPROVAL

    def test_the_claim_survives_reconciliation(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**Reconciliation never touches `workflow_step_runs`**, and that is load-bearing.

        The stale claim is the evidence of what was in flight, a live fence
        against the worker that took it, and the only thing standing between the
        next automatic delivery and a provider that has already been paid. A run
        may therefore be `failed` while still holding a claimed step -- which is
        the honest description of "this stopped mid-call".
        """
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)
        claim = admit(request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token)

        dispatch.record_outcome(
            claimed.id, claimed.lease_token, JobOutcome(status=JobStatus.DEAD_LETTERED)
        )

        row = step_row(admin_connection, run_id, 0)

        assert run_row(admin_connection, run_id)["status"] == RunStatus.FAILED
        assert row["claim_token"] == claim
        assert row["claimed_by_job_id"] == claimed.id
        assert row["status"] == StepStatus.RUNNING


# ---------------------------------------------------------------- recovery --


class TestExplicitRecovery:
    """Continuing an interrupted run is a decision a person makes.

    A claim protecting a paid step never expires and is never stolen, so nothing
    automatic re-enters it. The alternative -- a platform that silently re-spends
    a user's money to avoid showing them a failure -- makes the user's decision
    for them.
    """

    def test_recovering_an_ungated_step_supersedes_the_claim_and_enqueues_one_job(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """One user action, and execution follows from the last completed step."""
        run_id, _claim = _interrupted(request_database_url, admin_connection, tenants, dispatch)

        job_id = recover(request_database_url, tenants.owner, run_id, 0, gated=False)

        assert job_id is not None
        assert live_jobs(admin_connection, run_id) == [job_id]

        run = run_row(admin_connection, run_id)
        step = step_row(admin_connection, run_id, 0)

        assert run["status"] == RunStatus.PENDING
        assert run["finished_at"] is None
        assert step["status"] == StepStatus.FAILED, "the step is not claimable again"
        assert step["claim_token"] is None

    def test_recovering_a_gated_step_re_arms_the_gate_and_enqueues_nothing(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**Approval is never inferred.**

        The grant was spent at admission, so there is nothing left to infer it
        from. Continuing needs a *second*, separately authorized action -- and
        `resume` is `VIEW_WORKSPACE`, so for a gated step it grants nothing at
        all.
        """
        run_id, _claim = _interrupted(request_database_url, admin_connection, tenants, dispatch)

        job_id = recover(request_database_url, tenants.owner, run_id, 0, gated=True)

        assert job_id is None
        assert live_jobs(admin_connection, run_id) == []

        run = run_row(admin_connection, run_id)
        step = step_row(admin_connection, run_id, 0)

        assert run["status"] == RunStatus.AWAITING_APPROVAL
        assert step["status"] == StepStatus.AWAITING_APPROVAL
        assert step["approved_by"] is None, "recovery left a grant nobody issued"
        assert step["claim_token"] is None

        # And the gate is genuinely re-armed: approving works, and enqueues.
        assert approve(request_database_url, tenants.owner, run_id, 0) is not None

    def test_recovery_audits_the_supersession_without_the_token(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**A recovery may cause a second provider charge**, so it is audited.

        The record names the run, the step, the actor and the replacement job,
        and the *fact* that a stale claim was superseded. It never carries the
        token: a fencing value in an audit table is a value some future grant can
        expose.
        """
        run_id, claim = _interrupted(request_database_url, admin_connection, tenants, dispatch)
        job_id = recover(request_database_url, tenants.owner, run_id, 0, gated=False)

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT actor_id, target_id, detail::text FROM public.audit_log "
                "WHERE action = 'workflow.recovered' AND workspace_id = %s",
                (tenants.id,),
            )
            rows = cursor.fetchall()

        assert len(rows) == 1

        actor_id, target_id, detail = rows[0]

        assert actor_id == tenants.owner.user_id
        assert target_id == run_id
        assert '"superseded_claim": true' in detail
        assert str(job_id) in detail
        assert str(claim) not in detail, "a fencing token was written to the audit log"

    def test_recovery_refuses_a_run_that_is_not_failed(
        self, request_database_url: str, tenants: Workspace
    ) -> None:
        """A live run is not recoverable; there is nothing stale to supersede."""
        run_id = start_run(request_database_url, tenants.owner)

        with pytest.raises(psycopg.Error):
            recover(request_database_url, tenants.owner, run_id, 0, gated=False)

    def test_recovery_refuses_a_step_the_run_did_not_stop_on(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """The command re-derives the interrupted step under its own lock.

        The caller says which step is gated, because that is a property of code
        rather than of any row -- so the command refuses if the step it finds is
        not the one named, and a stale read cannot make it take the wrong branch.
        """
        run_id, _claim = _interrupted(request_database_url, admin_connection, tenants, dispatch)

        with pytest.raises(psycopg.Error):
            recover(request_database_url, tenants.owner, run_id, 4, gated=False)

        assert step_row(admin_connection, run_id, 0)["claim_token"] is not None

    def test_a_non_member_cannot_recover(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """Membership is checked inside the command, not only by the route."""
        run_id, _claim = _interrupted(request_database_url, admin_connection, tenants, dispatch)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            recover(
                request_database_url,
                tenants.stranger,
                run_id,
                0,
                gated=False,
                workspace=tenants.id,
            )

    def test_two_concurrent_recoveries_produce_one_job(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """Two people clicking continue at the same instant enqueue one replacement."""
        run_id, _claim = _interrupted(request_database_url, admin_connection, tenants, dispatch)

        results, errors = concurrently(
            4,
            lambda _index: recover(request_database_url, tenants.owner, run_id, 0, gated=False),
        )

        assert len(results) == 1, f"{len(results)} recoveries succeeded"
        assert len(errors) == 3
        assert len(live_jobs(admin_connection, run_id)) == 1

    def test_the_superseded_claim_lets_the_replacement_execute(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**And only then.** The claim released, the replacement admitted, once.

        Before the recovery, every delivery was interrupted; after it, exactly
        one execution can enter the step again. That is the whole shape of "no
        automatic re-invocation, and a deliberate one may repeat the call".
        """
        run_id, _claim = _interrupted(request_database_url, admin_connection, tenants, dispatch)
        recover(request_database_url, tenants.owner, run_id, 0, gated=False)

        replacement = claim_job(dispatch)
        fresh = admit(
            request_database_url, tenants.owner, run_id, replacement.id, replacement.lease_token
        )

        assert fresh is not None
        assert settle(
            request_database_url,
            tenants.owner,
            run_id,
            replacement.id,
            replacement.lease_token,
            fresh,
        )
        assert step_row(admin_connection, run_id, 0)["status"] == StepStatus.COMPLETED


def _interrupted(
    url: str,
    admin_connection: psycopg.Connection,
    tenants: Workspace,
    dispatch: JobDispatchRepository,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Return a run stranded mid-step, reached the way the system reaches it.

    Start, claim, admit a non-replayable step, then dead-letter the job -- which
    reconciles the run to `failed` and leaves the claim standing. That
    combination is not a broken state: it is the honest description of "this
    stopped mid-call", and it is what a recovery has to unpick.
    """
    run_id = start_run(url, tenants.owner)
    claimed = claim_job(dispatch)
    claim = admit(url, tenants.owner, run_id, claimed.id, claimed.lease_token)

    assert claim is not None

    dispatch.record_outcome(
        claimed.id, claimed.lease_token, JobOutcome(status=JobStatus.DEAD_LETTERED)
    )

    assert run_row(admin_connection, run_id)["status"] == RunStatus.FAILED

    return run_id, claim


# ------------------------------------------------- the accepted five names --

#: The repository root, four levels up from `apps/api/tests/`.
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: ADR-006, the document these commands are specified in.
_ADR_006 = (
    _REPO_ROOT
    / "ProjectOne Vault"
    / "08 ADR"
    / "ADR-006 Workflow Async Execution and Run Reconciliation.md"
)

#: The function names ADR-006 v1.4 consolidated away. They named half-transitions
#: -- a grant with no job, a supersession with no next state -- which is the one
#: shape §D11 exists to make unreachable.
_ABOLISHED_COMMANDS = ("app_grant_step_approval", "app_supersede_step_claim")

#: What makes a mention historical rather than normative.
#:
#: Deliberately a property of **the line**, not of the section it sits in. A
#: section-level exemption grows quietly -- a normative paragraph added under a
#: heading that was once historical inherits the exemption and nobody notices.
#: A line naming an abolished command has to say, on that line, that the command
#: is gone.
_HISTORICAL_MARKERS = ("v1.3", "half-transition", "consolidated away")


class TestTheAcceptedCommandNames:
    """The five D11 commands are the only ones the design may specify.

    **A documentation guard rather than a behaviour test, and it earns its place
    by what it prevents.** ADR-006 carried the v1.3 names in four normative
    sections for three revisions -- the recovery transaction, the state machine,
    an invariant and four Required Proofs -- and a reader implementing from those
    sections would have built the exact half-transitions §D11 abolished. Nothing
    in CI could notice, because prose does not fail to compile.

    So the names are asserted here, next to the tests that prove the real
    functions exist. If a future revision reintroduces one, this fails and says
    where.
    """

    def test_the_migration_creates_exactly_the_five_accepted_commands(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """The database is the arbiter, not the ADR's prose."""
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT p.proname FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' AND p.proname LIKE 'app_%workflow%' "
                "   OR (n.nspname = 'public' AND p.proname LIKE 'app_%step%') "
                "ORDER BY p.proname"
            )
            found = tuple(row[0] for row in cursor.fetchall())

        assert found == (
            "app_admit_workflow_step",
            "app_approve_workflow_step",
            "app_recover_workflow_run",
            "app_settle_workflow_step",
            "app_start_workflow_run",
        )

        for abolished in _ABOLISHED_COMMANDS:
            assert abolished not in found

    def test_no_abolished_name_appears_in_a_normative_section_of_the_adr(self) -> None:
        """An abolished name is history only where the text says it is history.

        The exemption is per line: a mention is allowed only where that same
        line marks the command as superseded. Everywhere else a v1.3 name is a
        specification of a function that does not exist and cannot be built.
        """
        text = _ADR_006.read_text(encoding="utf-8")
        offenders: list[tuple[int, str]] = []

        for number, line in enumerate(text.splitlines(), start=1):
            if not any(abolished in line for abolished in _ABOLISHED_COMMANDS):
                continue

            if any(marker in line for marker in _HISTORICAL_MARKERS):
                continue

            offenders.append((number, line.strip()[:100]))

        assert offenders == [], (
            "ADR-006 names a command v1.4 consolidated away, on a line that does not "
            f"say it is superseded: {offenders}"
        )


# ------------------------------------------------ the grants, as PostgreSQL --
#: Exactly what `authenticated` may read on `jobs` after the narrowing.
_JOB_READABLE = (
    "id", "workspace_id", "enqueued_by", "job_type", "payload", "status",
    "attempts", "max_attempts", "claimed_by", "claimed_at", "result",
    "last_error", "dead_lettered_at", "correlation_id", "created_at",
    "updated_at", "deleted_at", "version", "finished_at", "workflow_run_id",
)  # fmt: skip

#: Exactly what `authenticated` may read on `workflow_step_runs`.
_STEP_READABLE = (
    "id", "workspace_id", "run_id", "step_index", "step_name", "status",
    "detail", "tokens_used", "output", "started_at", "finished_at",
    "created_at", "updated_at", "deleted_at", "version", "approved_by",
)  # fmt: skip


class TestTheGrantsThemselves:
    """The privilege state PostgreSQL actually holds, column by column.

    The tests above prove the *consequences* -- a member cannot read a token, a
    member can still read a status. This proves the **shape**, and the two fail
    differently. A migration that granted columns and then revoked the table
    would leave every consequence test passing on a fresh database and every
    column privilege silently gone, because `REVOKE SELECT ON t` removes the
    column grants too. Asserting the end state catches the ordering without
    having to reason about it.
    """

    def test_no_table_wide_select_survives_on_either_table(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """Table-level SELECT is gone; whatever a member reads, they read by column."""
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege('authenticated', 'public.jobs', 'SELECT'), "
                "       has_table_privilege('authenticated', "
                "                           'public.workflow_step_runs', 'SELECT')"
            )
            jobs, steps = cursor.fetchone()  # type: ignore[misc]

        assert jobs is False, "jobs still carries a table-wide SELECT grant"
        assert steps is False, "workflow_step_runs still carries a table-wide SELECT grant"

    def test_the_readable_columns_are_exactly_the_enumerated_ones(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """Every accepted column is readable, and every other column is not.

        Both halves matter. Only checking the granted list would pass a migration
        that granted the whole table; only checking the withheld list would pass
        one that granted nothing and broke every read.
        """
        for table, readable in (
            ("public.jobs", _JOB_READABLE),
            ("public.workflow_step_runs", _STEP_READABLE),
        ):
            with admin_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT attname, "
                    "       has_column_privilege('authenticated', %s, attname, 'SELECT') "
                    "FROM pg_attribute "
                    "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped",
                    (table, table),
                )
                granted = {name: allowed for name, allowed in cursor.fetchall()}

            assert set(readable) <= set(granted), f"{table} lost a column it should have"

            for column, allowed in sorted(granted.items()):
                expected = column in readable

                assert allowed is expected, (
                    f"{table}.{column} is "
                    f"{'readable' if allowed else 'unreadable'} by authenticated, "
                    f"and ADR-006 §D11 says it should be "
                    f"{'readable' if expected else 'unreadable'}"
                )

    def test_approval_metadata_is_readable_and_unwritable(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """`approved_by` exactly as ADR-006 v1.6 I15 states it.

        One test for one proposition, because I15's whole correction is that
        reading and writing this column are different questions. Reading it is
        audit -- a member learns that a step they can already see was approved by
        a colleague they can already see. Writing it is authority, and forging an
        owner's approval was the compromise §Authenticated-Client Attack Surface
        was written about.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)
        approve(request_database_url, tenants.owner, run_id, 0, workspace=tenants.id)

        connection = open_session(request_database_url, tenants.member.user_id)

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT approved_by FROM public.workflow_step_runs "
                    "WHERE run_id = %s AND step_index = 0",
                    (run_id,),
                )
                row = cursor.fetchone()

            assert row is not None
            assert row[0] == tenants.owner.user_id, "the grant is not visible to a member"

            for statement in (
                "UPDATE public.workflow_step_runs SET approved_by = %s",
                "INSERT INTO public.workflow_step_runs "
                "(workspace_id, run_id, step_index, step_name, status, approved_by) "
                "VALUES ('00000000-0000-0000-0000-000000000000', "
                "'00000000-0000-0000-0000-000000000000', 0, 'x', 'pending', %s)",
            ):
                with (
                    connection.cursor() as cursor,
                    pytest.raises(psycopg.errors.InsufficientPrivilege),
                ):
                    cursor.execute(statement, (tenants.member.user_id,))

                connection.rollback()
                _reset_session(connection, tenants.member.user_id)
        finally:
            connection.close()


# ------------------------------------------------ foreign keys and indexes --
#: The child-side foreign keys STEP-31 adds, and the index each one needs.
_STEP_31_FOREIGN_KEYS = {
    "fk_jobs_workflow_run_id_workflow_runs": "ix_jobs_workflow_run_id_workspace_id",
    "fk_workflow_step_runs_claimed_by_job_id_jobs": (
        "ix_workflow_step_runs_claimed_by_job_id_workspace_id"
    ),
}

#: Finds every foreign key whose *referencing* columns lead no index.
#:
#: PostgreSQL indexes the referenced side automatically and never the
#: referencing side, so an unindexed child foreign key is the single most common
#: finding a database advisor reports. This is the query behind that finding,
#: written out because the Supabase CLI is not installed here -- see the class
#: docstring.
#:
#: A **partial** index counts, provided its predicate cannot exclude a row the
#: constraint cares about. `WHERE col IS NOT NULL` is exactly that: a null
#: referencing column matches no parent, so those rows are never scanned for.
_UNINDEXED_FOREIGN_KEYS = """
SELECT c.conname,
       c.conrelid::regclass::text AS child_table,
       (SELECT array_agg(a.attname ORDER BY k.ord)
          FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
          JOIN pg_attribute a
            ON a.attrelid = c.conrelid AND a.attnum = k.attnum) AS child_columns
  FROM pg_constraint c
 WHERE c.contype = 'f'
   AND c.connamespace = 'public'::regnamespace
   AND NOT EXISTS (
       SELECT 1
         FROM pg_index i
        WHERE i.indrelid = c.conrelid
          AND i.indisvalid
          AND (i.indkey::smallint[])[0:array_length(c.conkey, 1) - 1] @> c.conkey
          AND c.conkey @> (i.indkey::smallint[])[0:array_length(c.conkey, 1) - 1]
   )
 ORDER BY 1
"""


#: Child foreign keys that already lacked a covering index before STEP-31.
#:
#: Every one is defined in a migration that predates this step -- `e5a91c34d7f2`,
#: `a7d24e91f3b6`, `c8f1a3d54e29` and `f3c82b19d4a7` -- so none is this step's to
#: fix (CLAUDE.md §29). They are pinned so that a *new* unindexed foreign key
#: fails, and so that fixing one of these is a deliberate edit here rather than a
#: silent change.
_UNINDEXED_BASELINE = frozenset(
    {
        "fk_assets_project_id_projects",
        "fk_conversations_project_id_projects",
        "fk_messages_conversation_id_conversations",
        "fk_messages_reply_to_messages",
        "fk_workflow_runs_project_id_projects",
        "fk_workflow_step_runs_run_id_workflow_runs",
    }
)


class TestForeignKeysAreIndexedOnTheChildSide:
    """Every referencing foreign key leads an index that covers its rows.

    **Run as the fallback for a database advisor, and kept as a test.** The
    Supabase CLI is not installed in this environment, so the missing-FK-index
    check an advisor would perform is written out here instead -- which is the
    better home for it anyway: an advisor run is a moment, and this fails the
    next migration that forgets one.

    The reason it matters for STEP-31 specifically is that the obvious candidate
    does not qualify. `uq_jobs_one_live_job_per_workflow_run` is partial on
    `status IN ('pending','running')`, so a job leaves it the moment it succeeds
    or dead-letters -- and terminal jobs are exactly the rows that accumulate.
    `ON DELETE RESTRICT` still has to find them.
    """

    def test_the_two_new_foreign_keys_have_covering_indexes(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """Each new child foreign key is led by the index named for it."""
        with admin_connection.cursor() as cursor:
            for constraint, index in _STEP_31_FOREIGN_KEYS.items():
                cursor.execute(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = %s",
                    (index,),
                )
                row = cursor.fetchone()

                assert row is not None, f"{constraint} has no index {index}"

                definition = row[0]

                # Partial on IS NOT NULL only -- anything narrower would exclude
                # rows the constraint still has to find.
                assert "IS NOT NULL" in definition
                assert "status" not in definition, (
                    f"{index} is narrowed by status and would drop terminal rows: {definition}"
                )

    def test_no_new_foreign_key_is_unindexed_on_the_child_side(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """The advisor check itself, run over the whole schema against a baseline.

        Scoped to *new* findings rather than to STEP-31's tables, because a check
        that only ever looked at this step's constraints would pass while the
        schema degraded around it.

        The baseline is the six findings that already existed when STEP-31 was
        written. **They are recorded rather than fixed**, because indexing six
        foreign keys across `assets`, `conversations`, `messages` and
        `workflow_runs` is unrelated work in a step about workflow execution
        ([[CLAUDE|CLAUDE.md]] §29), and each deserves its own judgement about
        whether the write cost is worth paying. Writing them down is what turns
        them from invisible into a decision somebody can take.
        """
        with admin_connection.cursor() as cursor:
            cursor.execute(_UNINDEXED_FOREIGN_KEYS)
            unindexed = {name for name, _table, _columns in cursor.fetchall()}

        assert unindexed - _UNINDEXED_BASELINE == set(), (
            "a foreign key was added with no index leading its referencing columns: "
            f"{sorted(unindexed - _UNINDEXED_BASELINE)}"
        )

        assert _UNINDEXED_BASELINE - unindexed == set(), (
            "a baseline finding was fixed without updating the baseline: "
            f"{sorted(_UNINDEXED_BASELINE - unindexed)}"
        )


# ------------------------------------------------------- approval, audited --


def _approval_rows(connection: psycopg.Connection, workspace_id: uuid.UUID) -> list[tuple]:
    """Return every `workflow.approved` audit row in a workspace, oldest first."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT actor_id, target_id, detail::text, created_at FROM public.audit_log "
            "WHERE action = 'workflow.approved' AND workspace_id = %s "
            "ORDER BY created_at, id",
            (workspace_id,),
        )
        return list(cursor.fetchall())


class TestApprovalLeavesAHistory:
    """Who approved a gated step, and when, survives the grant being spent.

    **`approved_by` is enforcement state, not history.** Admission clears it --
    that is what makes the grant single-use -- so the column stops answering
    "who approved this" at the exact moment the approved step begins to run.

    ADR-006 §Column Necessity declines to add an `approved_at` column on the
    grounds that "'when' is history and belongs in `audit_log`, which survives
    consumption". That sentence is only true if something writes the row. Before
    this correction nothing did, so the approval history vanished at admission
    and the ADR described a property the schema did not have.
    """

    def test_approving_writes_one_audit_row_with_the_grant_and_the_job(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """The row names the workspace, actor, run, step and created job."""
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)
        job_id = approve(request_database_url, tenants.owner, run_id, 0, workspace=tenants.id)

        rows = _approval_rows(admin_connection, tenants.id)

        assert len(rows) == 1

        actor_id, target_id, detail, created_at = rows[0]

        assert actor_id == tenants.owner.user_id, "the actor is not auth.uid()"
        assert target_id == run_id
        assert '"step_index": 0' in detail
        assert str(job_id) in detail, "the audit row does not name the job it authorized"
        assert created_at is not None, "audit_log.created_at is the durable approval time"

    def test_no_fencing_token_reaches_the_audit_row(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """I17, asserted against the values themselves rather than the column list.

        A claim token does not exist yet at approval time, and a lease token
        belongs to a job nobody has claimed. Both are checked anyway, because the
        cost of this row quietly gaining one later is that a fencing value sits
        in a table some future grant may expose.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)
        job_id = approve(request_database_url, tenants.owner, run_id, 0, workspace=tenants.id)

        with admin_connection.cursor() as cursor:
            cursor.execute("SELECT lease_token FROM public.jobs WHERE id = %s", (job_id,))
            row = cursor.fetchone()

        assert row is not None

        detail = _approval_rows(admin_connection, tenants.id)[0][2]

        assert "lease_token" not in detail
        assert "claim_token" not in detail

        if row[0] is not None:  # pragma: no cover - a fresh job holds no lease
            assert str(row[0]) not in detail

    def test_a_refused_approval_leaves_no_audit_row(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """The row is part of the transaction, not a side effect beside it.

        A member's refused approval, and an approval named at the wrong step,
        must both leave the audit table exactly as they found it -- otherwise the
        log records approvals that never happened, which is worse than recording
        none.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            approve(request_database_url, tenants.member, run_id, 0, workspace=tenants.id)

        assert _approval_rows(admin_connection, tenants.id) == []

        with pytest.raises(psycopg.Error):
            approve(request_database_url, tenants.owner, run_id, 7, workspace=tenants.id)

        assert _approval_rows(admin_connection, tenants.id) == []

    def test_concurrent_approvals_leave_one_grant_one_job_and_one_row(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """Four approvals at once produce exactly one of each.

        The audit row is inside the same transaction as the grant and the job, so
        the losers roll all three back together. A log showing four approvals of
        one step would describe a race rather than a decision.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)

        results, errors = concurrently(
            4,
            lambda _index: approve(
                request_database_url, tenants.owner, run_id, 0, workspace=tenants.id
            ),
        )

        assert len(results) == 1, f"{len(results)} approvals succeeded"
        assert len(errors) == 3

        assert live_jobs(admin_connection, run_id) == [results[0]]
        assert len(_approval_rows(admin_connection, tenants.id)) == 1

    def test_the_history_survives_admission_clearing_the_grant(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**The whole point.** The column empties; the record does not.

        This is the property ADR-006 asserts when it declines an `approved_at`
        column, and the one that was untrue before this correction: once the
        approved step is admitted, `approved_by` is null and the audit row is the
        only remaining answer to who authorized the spend.
        """
        run_id = _paused_at_gate(request_database_url, admin_connection, tenants, dispatch)
        job_id = approve(request_database_url, tenants.owner, run_id, 0, workspace=tenants.id)
        claimed = claim_job(dispatch)

        assert claimed.id == job_id

        admit(
            request_database_url,
            tenants.owner,
            run_id,
            claimed.id,
            claimed.lease_token,
            step_index=0,
            requires_approval=True,
        )

        assert step_row(admin_connection, run_id, 0)["approved_by"] is None, (
            "admission must consume the grant, or this test proves nothing"
        )

        rows = _approval_rows(admin_connection, tenants.id)

        assert len(rows) == 1
        assert rows[0][0] == tenants.owner.user_id
        assert rows[0][3] is not None


# -------------------------------------- the step outcome and the run, as one --


def _all_steps_done_but_run_live(
    connection: psycopg.Connection, run_id: uuid.UUID, expected_steps: int
) -> bool:
    """Return whether an observer would see every step finished under a live run."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FILTER (WHERE status = 'completed'), "
            "       (SELECT status FROM public.workflow_runs WHERE id = %s) "
            "  FROM public.workflow_step_runs WHERE run_id = %s AND deleted_at IS NULL",
            (run_id, run_id),
        )
        completed, run_status = cursor.fetchone()  # type: ignore[misc]

    return completed == expected_steps and run_status not in ("completed", "failed")


class TestTheStepOutcomeAndTheRunMoveTogether:
    """A step's outcome and the run transition it causes are one transaction.

    **Two transactions with a commit between them leave a gap, and the gap is
    reachable**, because a job's lease can rotate inside it. Three losses follow,
    and the first two are the expensive ones:

    - the final step commits `completed` while its run is still `running`, so a
      replacement seeing every step complete can reconcile that run to `failed`;
    - a non-replayable step commits `failed` with its claim cleared, and a
      replacement arriving before the run turns `failed` can admit and
      **re-execute a step that has already been paid for**.

    These force the boundary directly: the settling transaction is held open
    while a second connection tries to observe or act, which is the state a
    lease rotation would otherwise have to be raced into existence.
    """

    def test_no_observer_sees_every_step_complete_under_a_live_run(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """The contradictory state is unobservable, before and after commit.

        Held open deliberately. If the two writes were separate transactions the
        first would already be visible here, which is exactly what a replacement
        worker would find.
        """
        run_id = start_run(request_database_url, tenants.owner)
        claimed = claim_job(dispatch)
        claim = admit(request_database_url, tenants.owner, run_id, claimed.id, claimed.lease_token)
        settling = open_session(request_database_url, tenants.owner.user_id)

        try:
            with settling.cursor() as cursor:
                cursor.execute(
                    "SELECT public.app_settle_workflow_step("
                    "%s::uuid, %s::uuid, 0::integer, %s::text, %s::text, NULL::text, "
                    "NULL::jsonb, 0::integer, %s::uuid, %s::uuid, %s::uuid)",
                    (
                        tenants.id,
                        run_id,
                        "plan",
                        StepStatus.COMPLETED,
                        claimed.id,
                        claimed.lease_token,
                        claim,
                    ),
                )

                assert cursor.fetchone()[0] is True  # type: ignore[index]

                cursor.execute(
                    "UPDATE public.workflow_runs SET status = %s, finished_at = now() "
                    "WHERE id = %s AND workspace_id = %s",
                    (RunStatus.COMPLETED, run_id, tenants.id),
                )

                # Mid-transaction: an outside reader must see neither write.
                assert not _all_steps_done_but_run_live(admin_connection, run_id, 1)

            settling.commit()
        finally:
            settling.close()

        # After commit: both, and therefore still never the contradiction.
        assert not _all_steps_done_but_run_live(admin_connection, run_id, 1)
        assert run_row(admin_connection, run_id)["status"] == RunStatus.COMPLETED
        assert step_row(admin_connection, run_id, 0)["status"] == StepStatus.COMPLETED

    def test_a_failed_claimed_step_cannot_be_re_entered_across_the_boundary(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        tenants: Workspace,
        dispatch: JobDispatchRepository,
    ) -> None:
        """**The expensive one.** A replacement must not admit the failed step.

        The failing settlement clears the claim, so between the two writes there
        is a step with no claim under a run that is still `running` -- which is
        precisely an admissible step. Holding both writes in one transaction
        means the step row stays locked until the run is `failed`, so a
        replacement blocks and then finds a terminal run.
        """
        run_id = start_run(request_database_url, tenants.owner)
        first = claim_job(dispatch)
        claim = admit(request_database_url, tenants.owner, run_id, first.id, first.lease_token)

        assert claim is not None, "a non-replayable step must take a claim"

        outcome: dict[str, object] = {}

        def try_to_admit() -> None:
            # A redelivery of the same job -- the shape a lease rotation
            # produces. It is refused after the pair commits because the run is
            # terminal; the half being proven here is that it cannot act
            # *during*, which is where separate transactions left a door.
            try:
                outcome["claim"] = admit(
                    request_database_url, tenants.owner, run_id, first.id, first.lease_token
                )
            except BaseException as error:  # noqa: BLE001 - asserted on below
                outcome["error"] = error

        settling = open_session(request_database_url, tenants.owner.user_id)

        try:
            with settling.cursor() as cursor:
                cursor.execute(
                    "SELECT public.app_settle_workflow_step("
                    "%s::uuid, %s::uuid, 0::integer, %s::text, %s::text, %s::text, "
                    "NULL::jsonb, 0::integer, %s::uuid, %s::uuid, %s::uuid)",
                    (
                        tenants.id,
                        run_id,
                        "plan",
                        StepStatus.FAILED,
                        "it failed",
                        first.id,
                        first.lease_token,
                        claim,
                    ),
                )

                assert cursor.fetchone()[0] is True  # type: ignore[index]

                cursor.execute(
                    "UPDATE public.workflow_runs SET status = %s, finished_at = now() "
                    "WHERE id = %s AND workspace_id = %s",
                    (RunStatus.FAILED, run_id, tenants.id),
                )

                # Started while the pair is still uncommitted. It blocks on the
                # step row's lock rather than reading a half-applied outcome.
                thread = threading.Thread(target=try_to_admit)
                thread.start()
                thread.join(timeout=1.0)

                assert thread.is_alive(), "the replacement did not block on the step lock"

            settling.commit()
            thread.join(timeout=10.0)
        finally:
            settling.close()

        assert "claim" not in outcome, "a replacement admitted a step that had already failed"
        assert isinstance(outcome.get("error"), psycopg.Error)
        assert step_row(admin_connection, run_id, 0)["status"] == StepStatus.FAILED
        assert run_row(admin_connection, run_id)["status"] == RunStatus.FAILED

    def test_the_lock_order_is_run_then_step_then_job_in_every_command(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """One order everywhere, asserted on the command bodies.

        Two orders is a deadlock between a stale worker settling and a
        replacement admitting -- a shape this codebase would meet in production
        and not in review. Now that the run transition shares the settlement's
        transaction, the locks are also held longer, which makes a second
        ordering more expensive rather than less.
        """
        for name, args in COMMANDS:
            body = _body(admin_connection, name, args)
            order = re.findall(r"FROM public\.(workflow_runs|workflow_step_runs|jobs)\b", body)
            first_seen: list[str] = []

            for table in order:
                if table not in first_seen:
                    first_seen.append(table)

            expected = [
                table
                for table in ("workflow_runs", "workflow_step_runs", "jobs")
                if table in first_seen
            ]

            assert first_seen == expected, f"{name} takes locks out of order: {first_seen}"


# --------------------------------------------- the ADR's own identifiers --

#: How many proofs and invariants ADR-006 defines. Both are contiguous from 1.
#:
#: Stated as totals rather than inferred from the file, because inferring them
#: would make the check tautological -- it would pass on any numbering the
#: document happened to contain, which is exactly the defect it exists to catch.
_ADR_006_PROOFS = 65
_ADR_006_INVARIANTS = 24


def _defined_identifiers(text: str, letter: str) -> list[int]:
    """Return every identifier *defined* in the ADR, in document order.

    A definition is a list item opening with the bolded identifier. References
    in prose and tables -- "P45–P52 prove it", "asserted by P34–P42" -- are
    deliberately not matched: those are citations, and citing an identifier
    twice is correct.
    """
    return [
        int(match.group(1))
        for match in re.finditer(rf"^- \*\*{letter}(\d+)\.\*\*", text, re.MULTILINE)
    ]


class TestTheADRNumbersEachThingOnce:
    """Every proof and invariant ADR-006 defines is defined exactly once.

    **Written because it happened.** The v1.7 conformance correction appended
    thirteen proofs starting again at `P42`, so the document defined `P42`
    through `P52` twice -- once for the caller-identity proofs accepted in v1.5,
    once for the new ones. Nothing failed. A reviewer asked to check "P50" would
    have found two different proofs under that name, and a step note citing a
    range would silently mean whichever block the reader reached first.

    Prose cannot fail to compile, so the identifiers are checked here instead.
    """

    def test_every_proof_is_defined_exactly_once_and_none_is_missing(self) -> None:
        """P1 through P65, each defined once, with no gaps and no repeats."""
        defined = _defined_identifiers(_ADR_006.read_text(encoding="utf-8"), "P")
        duplicates = sorted({n for n in defined if defined.count(n) > 1})
        missing = sorted(set(range(1, _ADR_006_PROOFS + 1)) - set(defined))
        unexpected = sorted(n for n in set(defined) if n > _ADR_006_PROOFS)

        assert duplicates == [], f"ADR-006 defines these proofs more than once: {duplicates}"
        assert missing == [], f"ADR-006 defines no proof for: {missing}"
        assert unexpected == [], (
            f"ADR-006 defines proofs above P{_ADR_006_PROOFS}: {unexpected}. "
            "Raise _ADR_006_PROOFS deliberately when adding proofs."
        )

    def test_the_proofs_are_defined_in_ascending_order(self) -> None:
        """Numbering that runs backwards is how the duplicate block arrived.

        The v1.7 proofs were inserted between `P41` and the legacy `P42`, so the
        document counted up to `P54` and then restarted at `P42`. Ascending order
        catches that shape even when every identifier happens to be unique.
        """
        defined = _defined_identifiers(_ADR_006.read_text(encoding="utf-8"), "P")

        assert defined == sorted(defined), (
            "ADR-006 defines its proofs out of order; the first descent is at "
            f"{next(b for a, b in zip(defined, defined[1:], strict=False) if b < a)}"
        )

    def test_every_invariant_is_defined_exactly_once_and_none_is_missing(self) -> None:
        """I1 through I24, on the same terms as the proofs."""
        defined = _defined_identifiers(_ADR_006.read_text(encoding="utf-8"), "I")
        duplicates = sorted({n for n in defined if defined.count(n) > 1})
        missing = sorted(set(range(1, _ADR_006_INVARIANTS + 1)) - set(defined))

        assert duplicates == [], f"ADR-006 defines these invariants more than once: {duplicates}"
        assert missing == [], f"ADR-006 defines no invariant for: {missing}"
        assert defined == sorted(defined), "ADR-006 defines its invariants out of order"
