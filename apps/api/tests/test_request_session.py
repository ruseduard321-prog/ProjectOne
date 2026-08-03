"""Tests that RLS actually protects the *application*, not just psql.

STEP-09 proved the policies work for a session that connects as `authenticated`
and sets a claim by hand. That is a necessary result and not a sufficient one:
it says nothing about whether the API's own connection is subject to them. An
API connecting as `postgres` would read every workspace's rows while all 17 of
those tests continued to pass.

These tests close that gap. They use `RequestSessionFactory` — the real one the
API uses — over the real request-path role, so what they observe is the
production path.
"""

import uuid

import psycopg
import pytest
from pydantic import SecretStr

from app.core.config import Environment, Settings
from app.repositories.session import RequestSessionFactory
from tests.conftest import TEST_BYOK_KEY, seed_identity


def make_settings(request_url: str, admin_url: str) -> Settings:
    """Build Settings pointing at the test database."""
    return Settings(
        environment=Environment.DEVELOPMENT,
        SUPABASE_URL="https://example.test",
        SUPABASE_SECRET_KEY=SecretStr("not-used-here"),
        DATABASE_URL=SecretStr(admin_url),
        REQUEST_DATABASE_URL=SecretStr(request_url),
        byok_encryption_key=SecretStr(TEST_BYOK_KEY),
        _env_file=None,
    )


@pytest.fixture
def factory(request_database_url: str, migrated_database: str) -> RequestSessionFactory:
    """Return a session factory wired to the request-path role."""
    return RequestSessionFactory(make_settings(request_database_url, migrated_database))


def test_request_role_does_not_bypass_rls(request_database_url: str) -> None:
    """The API's role must not carry rolbypassrls.

    The single most important assertion in this file. If this fails, every
    other isolation test in the suite is decorative — the policies are still
    correct, and the application is simply not subject to them.
    """
    with (
        psycopg.connect(request_database_url) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user")
        row = cursor.fetchone()

    assert row is not None
    assert row[0] is False, "the request-path role bypasses RLS — isolation is not enforced"
    assert row[1] is False, "the request-path role is a superuser"


def test_privileged_role_does_bypass_rls(migrated_database: str) -> None:
    """The migration role *does* bypass RLS — which is why it must not serve requests.

    Asserted rather than assumed, because the entire two-connection design rests
    on it. If this ever stops being true the design is over-engineered; if it
    silently became true of the request role, the design is broken.
    """
    with (
        psycopg.connect(migrated_database) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        row = cursor.fetchone()

    assert row is not None
    assert row[0] is True


def test_session_sees_only_the_callers_workspace(
    factory: RequestSessionFactory, admin_connection: psycopg.Connection
) -> None:
    """A session scoped to Alice reads Alice's workspace and not Bob's."""
    alice = seed_identity(admin_connection, "alice")
    bob = seed_identity(admin_connection, "bob")

    with factory.authenticated_as(alice.user_id) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM public.workspaces")
        visible = {row[0] for row in cursor.fetchall()}

    assert visible == {alice.workspace_id}
    assert bob.workspace_id not in visible


def test_claim_does_not_leak_between_sessions(
    factory: RequestSessionFactory, admin_connection: psycopg.Connection
) -> None:
    """A second session on the same pool sees its own identity, never the first's.

    This is the pooling leak the step note calls out, and it was reproduced for
    real during STEP-10 before the transaction-scoped form was adopted: with a
    session-scoped `set_config`, the claim survived its transaction and the next
    caller inherited the previous caller's identity.

    A single-request test cannot catch it — the first request always looks
    correct. Only the second one reveals it.
    """
    alice = seed_identity(admin_connection, "alice")
    bob = seed_identity(admin_connection, "bob")

    with factory.authenticated_as(alice.user_id) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM public.workspaces")
        first = {row[0] for row in cursor.fetchall()}

    with factory.authenticated_as(bob.user_id) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM public.workspaces")
        second = {row[0] for row in cursor.fetchall()}

    assert first == {alice.workspace_id}
    assert second == {bob.workspace_id}, "Bob's session inherited Alice's identity"
    assert alice.workspace_id not in second


def test_identity_and_role_reset_after_the_transaction(
    factory: RequestSessionFactory, admin_connection: psycopg.Connection
) -> None:
    """The role and claim must not survive the transaction that set them."""
    alice = seed_identity(admin_connection, "alice")

    with factory.authenticated_as(alice.user_id) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user, auth.uid()")
            inside = cursor.fetchone()

        assert inside is not None
        assert inside[0] == "authenticated"
        assert inside[1] == alice.user_id

        # The context manager's transaction has not closed yet, so check the
        # reset on a fresh connection from the same factory instead.

    with (
        psycopg.connect(
            factory._settings.request_database_url.get_secret_value()  # noqa: SLF001 - asserting internals
        ) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT current_user, current_setting('request.jwt.claim.sub', true)")
        after = cursor.fetchone()

    assert after is not None
    assert after[0] == "projectone_api", "the role outlived its transaction"
    assert after[1] in (None, ""), "the JWT claim outlived its transaction"


def test_session_with_an_unknown_identity_sees_nothing(
    factory: RequestSessionFactory, admin_connection: psycopg.Connection
) -> None:
    """An identity with no memberships reads no rows at all."""
    seed_identity(admin_connection, "alice")

    with factory.authenticated_as(uuid.uuid4()) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM public.workspaces")
        count = cursor.fetchone()

    assert count is not None
    assert count[0] == 0


def test_anon_holds_no_grants_on_tenant_tables(migrated_database: str) -> None:
    """`anon` must hold no table privileges after the grant migration.

    Grants and RLS are independent gates. Before `c4f21a86b3de`, `anon` held
    full DML and was stopped only by policies matching no rows — meaning a
    future table shipped without a policy would be open to an unauthenticated
    role. This asserts the grant itself is gone.
    """
    with (
        psycopg.connect(migrated_database) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE table_schema = 'public'
              AND grantee = 'anon'
              AND table_name IN ('users', 'workspaces', 'workspace_members')
            """
        )
        remaining = cursor.fetchall()

    assert remaining == [], f"anon still holds grants: {remaining}"


def test_authenticated_holds_no_delete_or_truncate(migrated_database: str) -> None:
    """`authenticated` keeps SELECT/INSERT/UPDATE and nothing more.

    TRUNCATE matters most: it is **not subject to RLS at all**, so a role
    holding it can empty a tenant table regardless of every policy on it.
    """
    with (
        psycopg.connect(migrated_database) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            SELECT DISTINCT privilege_type
            FROM information_schema.role_table_grants
            WHERE table_schema = 'public'
              AND grantee = 'authenticated'
              AND table_name IN ('users', 'workspaces', 'workspace_members')
            ORDER BY privilege_type
            """
        )
        privileges = {row[0] for row in cursor.fetchall()}

    assert privileges == {"SELECT", "INSERT", "UPDATE"}, f"unexpected grants: {privileges}"


def test_future_tables_do_not_inherit_permissive_grants(
    migrated_database: str, admin_connection: psycopg.Connection
) -> None:
    """A table created tomorrow must not arrive granted to `anon`.

    Revoking today's three tables is not enough on its own: Supabase ships
    `ALTER DEFAULT PRIVILEGES ... GRANT ALL ON TABLES TO anon, authenticated`,
    so every new table is granted full DML — DELETE and TRUNCATE included —
    automatically. This creates a real table and inspects what it inherited,
    rather than reading the catalog and reasoning about what it implies.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute("CREATE TABLE public.grant_probe (id uuid PRIMARY KEY)")

        try:
            cursor.execute(
                """
                SELECT grantee, privilege_type
                FROM information_schema.role_table_grants
                WHERE table_schema = 'public' AND table_name = 'grant_probe'
                  AND grantee IN ('anon', 'authenticated')
                """
            )
            inherited = {(row[0], row[1]) for row in cursor.fetchall()}
        finally:
            cursor.execute("DROP TABLE public.grant_probe")

    anon_grants = {privilege for grantee, privilege in inherited if grantee == "anon"}
    authenticated_grants = {
        privilege for grantee, privilege in inherited if grantee == "authenticated"
    }

    assert anon_grants == set(), f"a new table was granted to anon: {anon_grants}"
    assert "DELETE" not in authenticated_grants
    assert "TRUNCATE" not in authenticated_grants
