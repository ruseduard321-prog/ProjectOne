"""Shared test fixtures.

Most of this file exists for the RLS isolation tests (STEP-09), which are the
only tests in the suite that need a real database. Everything else runs against
substituted dependencies and stays offline (see `test_health.py`).

**Why these tests cannot use stubs.** They assert what PostgreSQL itself does
with a policy. A stub proving "our fake returns no rows" proves nothing about
whether workspace isolation actually holds -- and this is the one step where a
false pass is a cross-tenant data breach (CLAUDE.md §16).

**Which database.** `PROJECTONE_TEST_DATABASE_URL`, and never `DATABASE_URL`.
The tests create and destroy rows, so pointing them at the development Supabase
project would make running the suite destructive. When the variable is absent
the isolation tests are skipped rather than failed, so the offline suite still
passes on a machine with no PostgreSQL; CI sets it explicitly, so the coverage
is not quietly lost there.
"""

import os
import urllib.parse
import uuid
from collections.abc import Iterator

import psycopg
import pytest

# Applied to the throwaway test database only.
#
# `auth.uid()` is supplied by Supabase's platform image, not by PostgreSQL, so a
# stock `postgres:17` container in CI does not have it. Rather than weaken the
# policies to something a bare server can satisfy, the harness recreates the
# contract the policies actually depend on: a function reading the same
# `request.jwt.claim.sub` session setting, with the same STABLE volatility.
#
# The definition is copied from the live Supabase database (verified during
# STEP-09), so a divergence between this shim and the real thing means the
# tests would be proving something about a fiction. That risk is accepted
# deliberately and bounded: the surface is one function returning one claim, and
# the isolation tests also run against the real database locally, where the
# genuine `auth.uid()` is what answers.
#
# The roles are recreated for the same reason -- `authenticated` and `anon` are
# Supabase-provisioned, and the policies name them.
#
# Applied only when `auth.uid()` is missing. On a real Supabase project the
# `auth` schema is owned by `supabase_auth_admin` and even `postgres` cannot
# create in it -- so attempting the shim unconditionally fails with "permission
# denied for schema auth". Skipping it there is also correct on the merits: when
# the genuine function is present, the tests should be exercising that one.
_SUPABASE_SHIM = """
CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claim.sub', true), ''),
        (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
    )::uuid
$$;

GRANT USAGE ON SCHEMA auth TO anon, authenticated;
"""

# Roles the policies name. Supabase provisions these; a bare PostgreSQL does
# not. Safe to run against either -- each creation is guarded.
_TEST_ROLES = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO anon, authenticated;
"""

# Supabase grants these by default on its own projects; a bare PostgreSQL does
# not. Applied *before* migrations so the database starts from the same
# permissive posture a real Supabase project has -- which is what migration
# `c4f21a86b3de` then narrows. Without this the grant migration would be
# revoking privileges that were never granted, and the test database would end
# up in a state no real environment passes through.
_DEFAULT_TABLE_GRANTS = """
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON public.users TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON public.workspaces TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON public.workspace_members TO anon, authenticated;
"""

# The request-path role is created by migration `d7b95c1f4e08`, deliberately
# with NOLOGIN and no password -- a credential in a migration is a credential in
# source control. Tests therefore have to supply one, which is what this does,
# *after* migrations have run.
#
# Only LOGIN and the password are added. NOINHERIT and NOBYPASSRLS are left
# exactly as the migration set them, so what the tests exercise is the real
# role's attributes rather than a convenient local copy of them.
_REQUEST_ROLE_NAME = "projectone_api"
_REQUEST_ROLE_PASSWORD = "projectone-test-request-role"  # noqa: S105 - throwaway test database

_REQUEST_ROLE_LOGIN = f"""
ALTER ROLE {_REQUEST_ROLE_NAME} WITH LOGIN PASSWORD '{_REQUEST_ROLE_PASSWORD}';
"""

# A fixed, obviously-fake AES-256 key for tests that construct `Settings`
# directly (STEP-17).
#
# Deterministic rather than random so a failure is reproducible, and shared from
# here rather than repeated in eight files so adding the next required setting
# is one edit. It encrypts nothing real: the tests that exercise encryption
# generate their own random keys, and this exists purely to satisfy a required
# field.
TEST_BYOK_KEY = "dGVzdC1ieW9rLWtleS0zMi1ieXRlcy1sb25nLXh4eHg="  # noqa: S105 - fake test key

# Every table holding a foreign key to `public.workspaces`, in the order
# teardown must delete them: dependants first, then `workspaces`, then `users`.
#
# All of them are `ON DELETE RESTRICT` by design -- see `admin_connection`.
# Kept as one named list rather than inline statements so that adding a table
# is a one-line edit next to the reason it exists, and so a test can assert the
# list against the database's own catalog instead of trusting it.
#
# Order within the list is unconstrained: none of these reference each other,
# only `workspaces`. It is alphabetical for readability, not for correctness.
_WORKSPACE_DEPENDANTS = (
    "ai_budgets",
    "ai_shutdown_switches",
    "ai_spend_records",
    "audit_log",
    "provider_credentials",
    "workspace_members",
)

TEST_DATABASE_URL_VAR = "PROJECTONE_TEST_DATABASE_URL"

# Set in CI. Turns "no database configured" from a skip into a failure.
#
# A skip is the right behaviour on a developer machine with no PostgreSQL, and
# the wrong behaviour in a pipeline whose job is to prove tenant isolation: a
# misconfigured service container would otherwise downgrade the entire security
# suite to skips while CI still reported green.
REQUIRE_DATABASE_TESTS_VAR = "PROJECTONE_REQUIRE_DATABASE_TESTS"


def _test_database_url() -> str | None:
    """Return the throwaway database URL, or None when it is not configured."""
    return os.environ.get(TEST_DATABASE_URL_VAR) or None


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[str]:
    """Return a URL for a database with the full schema and RLS applied.

    Session-scoped: applying migrations is the expensive part, and the isolation
    tests only read and write rows, which each test cleans up after itself.
    """
    url = _test_database_url()

    if url is None:
        if os.environ.get(REQUIRE_DATABASE_TESTS_VAR):
            pytest.fail(
                f"{REQUIRE_DATABASE_TESTS_VAR} is set but {TEST_DATABASE_URL_VAR} is not. "
                "The RLS isolation tests must run here — refusing to skip them silently.",
                pytrace=False,
            )

        pytest.skip(f"{TEST_DATABASE_URL_VAR} is not set — skipping database-backed tests")

    from alembic import command
    from alembic.config import Config

    api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    with psycopg.connect(url, autocommit=True) as connection, connection.cursor() as cursor:
        cursor.execute(_TEST_ROLES)

        # Only shim `auth.uid()` when it is genuinely absent -- see the comment
        # above _SUPABASE_SHIM. Against a real Supabase project the tests
        # exercise the platform's own function, which is the stronger signal.
        cursor.execute("SELECT to_regprocedure('auth.uid()') IS NOT NULL")
        auth_uid_exists = cursor.fetchone()

        if auth_uid_exists is None or not auth_uid_exists[0]:
            cursor.execute(_SUPABASE_SHIM)

    config = Config(os.path.join(api_root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(api_root, "migrations"))
    # Overrides what migrations/env.py resolves from DATABASE_URL, so a test run
    # can never migrate the development database by accident.
    config.set_main_option(
        "sqlalchemy.url", url.replace("postgresql://", "postgresql+psycopg://", 1)
    )
    # Three phases, and the order is the whole point.
    #
    # Supabase's default grants must be in place *before* `c4f21a86b3de` runs,
    # so the narrowing migration acts on the permissive posture a real project
    # actually has rather than revoking privileges that were never granted.
    #
    # Applying them afterwards instead — which an earlier version of this
    # fixture did — silently undoes the migration: the database reports itself
    # at head while the grants are still wide open. That failure is invisible
    # unless something asserts the grants, which `test_request_session.py` now
    # does.
    #
    # Reaching that revision from *either* direction: a fresh container upgrades
    # to it, while a database already at head (the normal case when these run
    # against the development project) downgrades to it. `command.upgrade` alone
    # is a silent no-op on the latter, which is exactly how the permissive
    # grants survived and made the migration look applied when it was not.
    command.upgrade(config, "860a798d204b")

    with psycopg.connect(url, autocommit=True) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT version_num FROM alembic_version")
        current = cursor.fetchone()

    if current is not None and current[0] != "860a798d204b":
        command.downgrade(config, "860a798d204b")

    with psycopg.connect(url, autocommit=True) as connection, connection.cursor() as cursor:
        cursor.execute(_DEFAULT_TABLE_GRANTS)

    command.upgrade(config, "head")

    # The request role now exists (migration d7b95c1f4e08) but cannot log in --
    # by design, since the migration must not carry a password. Give the test
    # copy one, changing nothing else about it.
    with psycopg.connect(url, autocommit=True) as connection, connection.cursor() as cursor:
        cursor.execute(_REQUEST_ROLE_LOGIN)

    yield url


@pytest.fixture(scope="session")
def request_database_url(migrated_database: str) -> str:
    """Return a URL connecting as the API's request-path role.

    This is the role the API actually uses, and the distinction is the point:
    it has no `rolbypassrls`, so a test using it exercises the same isolation a
    real request gets. A test connecting as the owner would prove nothing about
    whether RLS protects the application.
    """
    parsed = urllib.parse.urlparse(migrated_database)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path

    return f"postgresql://{_REQUEST_ROLE_NAME}:{_REQUEST_ROLE_PASSWORD}@{host}{port}{database}"


@pytest.fixture
def admin_connection(migrated_database: str) -> Iterator[psycopg.Connection]:
    """Return a superuser connection used to arrange fixtures, never to assert.

    Seeding runs as the owner because the INSERT policies deliberately do not
    permit bootstrapping a workspace from a client (see the migration's note on
    `workspace_members_insert_same_workspace`). Assertions never use this
    connection -- they use `as_user`, which is subject to RLS.
    """
    with psycopg.connect(migrated_database, autocommit=True) as connection:
        yield connection

        with connection.cursor() as cursor:
            # Order matters, and every step of it is a RESTRICT foreign key.
            #
            # `workspaces` cannot be deleted while anything still references it,
            # and every dependant below is deliberately RESTRICT rather than
            # CASCADE: spend history, budgets, kill switches, provider keys and
            # the audit trail must not be silently cascaded away with the
            # workspace they describe. That production guarantee is exactly why
            # teardown has to clear them explicitly.
            #
            # `workspaces.owner_id` is likewise RESTRICT, so `users` goes last.
            # `workspace_members` is CASCADE on both sides, but is cleared here
            # anyway so the delete order reads as the dependency order rather
            # than relying on a cascade to cover part of it.
            #
            # **This list is not optional maintenance.** Any new table taking a
            # foreign key to `workspaces` must be added here in the same change
            # that creates it, or every database test that seeds a workspace
            # starts failing teardown with a ForeignKeyViolation naming the new
            # constraint. `test_teardown_covers_workspace_dependants` asserts
            # this list is complete by querying the live FK graph, so the
            # omission fails as a clear assertion rather than as a confusing
            # violation in an unrelated test.
            #
            # Note `ai_shutdown_switches.workspace_id` is NULLABLE -- a
            # platform-wide switch has no workspace. The unqualified DELETE is
            # therefore load-bearing: a workspace-scoped one would leave
            # platform-wide rows behind to leak into the next test.
            #
            # This is the owner connection, so it bypasses the grants that stop
            # a request from ever doing this.
            for table in _WORKSPACE_DEPENDANTS:
                cursor.execute(f"DELETE FROM public.{table}")

            cursor.execute("DELETE FROM public.workspaces")
            cursor.execute("DELETE FROM public.users")


class Identity:
    """A seeded user and the workspace they own."""

    def __init__(self, user_id: uuid.UUID, workspace_id: uuid.UUID, email: str) -> None:
        """Record the identifiers a test needs to assert against."""
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.email = email


def seed_identity(connection: psycopg.Connection, label: str) -> Identity:
    """Create a user, a workspace they own, and their membership row.

    Uses the owner connection deliberately -- see `admin_connection`.
    """
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    email = f"{label}-{user_id.hex[:8]}@example.test"

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.users (id, email, display_name) VALUES (%s, %s, %s)",
            (user_id, email, f"User {label}"),
        )
        cursor.execute(
            "INSERT INTO public.workspaces (id, name, owner_id) VALUES (%s, %s, %s)",
            (workspace_id, f"Workspace {label}", user_id),
        )
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'owner')",
            (workspace_id, user_id),
        )

    return Identity(user_id, workspace_id, email)
