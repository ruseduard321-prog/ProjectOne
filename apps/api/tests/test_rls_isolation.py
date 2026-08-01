"""Workspace isolation tests (STEP-09).

These are permanent regression protection for the property a multi-tenant
platform cannot get wrong: **a user from workspace A must never reach workspace
B's rows** (CLAUDE.md §16). A defect here is a cross-tenant data breach, and no
later step would catch it.

Read, write and delete are all tested. Testing only read is the common and
insufficient version -- a SELECT policy without matching UPDATE coverage lets an
attacker who cannot see a row still modify it.

`test_policies_are_what_makes_these_tests_pass` is the test that keeps the
others honest. An isolation test that would still pass with RLS switched off is
asserting nothing, so that test switches it off and proves the suite notices.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from tests.conftest import Identity, seed_identity

# Every test in this module needs a database, and skips without one.
pytestmark = pytest.mark.usefixtures("migrated_database")


def as_user(connection: psycopg.Connection, user_id: uuid.UUID) -> psycopg.Cursor:
    """Return a cursor acting as `authenticated` with the given identity.

    Sets the same session GUC Supabase's `auth.uid()` reads, then drops to the
    `authenticated` role. Order matters: `set_config` must run while still
    privileged. `SET LOCAL ROLE` means the change is scoped to the surrounding
    transaction, so a leaked role cannot affect a later test.
    """
    cursor = connection.cursor()
    cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))
    cursor.execute("SET LOCAL ROLE authenticated")

    return cursor


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[tuple[Identity, Identity]]:
    """Seed two unrelated tenants: user A owning workspace A, user B owning B."""
    yield seed_identity(admin_connection, "alice"), seed_identity(admin_connection, "bob")


# --------------------------------------------------------------------- read --


def test_user_sees_only_their_own_workspace(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT id FROM public.workspaces")
        visible = {row[0] for row in cursor.fetchall()}

    assert visible == {alice.workspace_id}
    assert bob.workspace_id not in visible


def test_cross_tenant_workspace_read_returns_nothing(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """Naming the other workspace's id directly must not reveal it.

    Distinct from the test above: RLS filters rows rather than raising, so a
    targeted lookup returns an empty result. Asserting that explicitly guards
    against a future policy that leaks on a primary-key lookup.
    """
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT id FROM public.workspaces WHERE id = %s", (bob.workspace_id,))

        assert cursor.fetchall() == []


def test_user_cannot_read_another_tenants_membership_rows(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT workspace_id FROM public.workspace_members")
        visible = {row[0] for row in cursor.fetchall()}

    assert visible == {alice.workspace_id}


def test_user_cannot_read_an_unrelated_users_profile(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """`users` is not tenant-scoped, so its policy is about co-membership."""
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT id FROM public.users")
        visible = {row[0] for row in cursor.fetchall()}

    assert visible == {alice.user_id}
    assert bob.user_id not in visible


def test_co_members_can_see_each_other(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """The other half of the users policy: isolation must not break the product.

    A policy that hides everyone from everyone would pass every test above while
    making member listings impossible. This is why `email` was denormalized onto
    `users` in STEP-08.
    """
    alice, bob = tenants

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (alice.workspace_id, bob.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT id FROM public.users")
        visible = {row[0] for row in cursor.fetchall()}

    assert visible == {alice.user_id, bob.user_id}


def test_soft_deleted_membership_loses_access(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """A removed member must not retain access while their row still exists.

    Membership is soft-deleted, so the row survives removal. `deleted_at IS NULL`
    in `app_current_user_workspaces()` is what stops that row still granting
    access -- forget it and a removed member is served indefinitely, silently,
    because everything still looks correct.

    **Bob is removed rather than Alice, and that matters.** Alice is the sole
    owner of her workspace, and since [[STEP-11a]] the last owner cannot be
    removed at all -- rule 1, enforced by
    `trg_workspace_members_protect_last_owner`. Removing her would now fail on
    that trigger rather than proving anything about access, so the test uses a
    member whose departure is actually permitted. The property under test is
    unchanged.
    """
    alice, bob = tenants

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (alice.workspace_id, bob.user_id),
        )
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (alice.workspace_id, bob.user_id),
        )

    # Bob keeps his own workspace, so the assertion is that he lost *Alice's* --
    # not that he can see nothing at all, which would also pass if the fixture
    # were broken.
    with admin_connection.transaction():
        cursor = as_user(admin_connection, bob.user_id)
        cursor.execute("SELECT id FROM public.workspaces")
        visible = {row[0] for row in cursor.fetchall()}

    assert alice.workspace_id not in visible
    assert visible == {bob.workspace_id}


def test_session_without_an_identity_sees_nothing(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """`auth.uid()` is NULL without a JWT claim, so every policy must deny."""
    with admin_connection.transaction():
        cursor = admin_connection.cursor()
        cursor.execute("SET LOCAL ROLE authenticated")
        cursor.execute("SELECT count(*) FROM public.workspaces")
        workspaces = cursor.fetchone()

        cursor.execute("SELECT count(*) FROM public.users")
        users = cursor.fetchone()

    assert workspaces is not None and workspaces[0] == 0
    assert users is not None and users[0] == 0


# -------------------------------------------------------------------- write --


def test_cross_tenant_update_changes_nothing(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """An UPDATE the policy excludes affects zero rows rather than erroring."""
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.workspaces SET name = %s WHERE id = %s",
            ("owned by alice now", bob.workspace_id),
        )

        assert cursor.rowcount == 0

    with admin_connection.cursor() as cursor:
        cursor.execute("SELECT name FROM public.workspaces WHERE id = %s", (bob.workspace_id,))
        row = cursor.fetchone()

    assert row is not None
    assert row[0] != "owned by alice now"


def test_cross_tenant_profile_update_changes_nothing(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.users SET display_name = %s WHERE id = %s",
            ("hijacked", bob.user_id),
        )

        assert cursor.rowcount == 0


def test_user_cannot_insert_a_membership_into_another_workspace(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """Adding yourself to someone else's workspace must be rejected outright.

    A WITH CHECK violation raises rather than silently affecting zero rows --
    the difference between UPDATE (filters, then checks) and INSERT (only
    checks).
    """
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, 'admin')",
                (bob.workspace_id, alice.user_id),
            )


def test_user_cannot_create_a_workspace_owned_by_someone_else(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """Stops a workspace being planted in another user's account."""
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                "INSERT INTO public.workspaces (name, owner_id) VALUES (%s, %s)",
                ("planted", bob.user_id),
            )


def test_user_cannot_reassign_their_profile_to_another_identity(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """The WITH CHECK clause on `users_update_self` exists for exactly this.

    USING alone would permit updating a visible row into one the user should
    never own.
    """
    alice, _bob = tenants
    stolen = uuid.uuid4()

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute("UPDATE public.users SET id = %s WHERE id = %s", (stolen, alice.user_id))


# ------------------------------------------------------------------- delete --


def test_delete_is_denied_on_every_table(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """A hard DELETE removes nothing, whichever gate stops it.

    Deliberate: removal is a soft delete (an UPDATE setting `deleted_at`). A
    hard DELETE would be a second removal path bypassing that entirely. Covers
    the user's *own* rows as well as another tenant's -- the restriction is not
    about ownership.

    **Two independent gates now deny this, and the test accepts either.** Before
    STEP-10 only RLS stopped it: no DELETE policy exists, so the command matched
    zero rows and returned quietly. STEP-10's `c4f21a86b3de` also revoked the
    DELETE *grant*, so PostgreSQL now refuses earlier, with a privilege error.

    Asserting on the specific mechanism would make this test fail whenever the
    defence got stronger -- which is what happened when the grant was revoked.
    What must hold is the outcome: the rows survive.
    """
    alice, bob = tenants

    targets = (
        ("public.workspaces", "id", bob.workspace_id),
        ("public.workspaces", "id", alice.workspace_id),
        ("public.workspace_members", "user_id", bob.user_id),
    )

    for table, column, value in targets:
        # Each in its own transaction: a privilege error aborts the transaction
        # it is raised in, so a shared one would fail every subsequent statement
        # for the wrong reason.
        with admin_connection.transaction():
            cursor = as_user(admin_connection, alice.user_id)

            try:
                cursor.execute(f"DELETE FROM {table} WHERE {column} = %s", (value,))
            except psycopg.errors.InsufficientPrivilege:
                # Denied by the missing grant -- the stronger of the two gates.
                continue

            # Denied by the missing policy: the command was permitted but
            # matched no rows.
            assert cursor.rowcount == 0

    # Whichever gate fired, the rows must still be there. This is the assertion
    # that actually matters, and it is checked outside the loop over a
    # connection that bypasses RLS, so a policy cannot hide a deleted row.
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM public.workspaces WHERE id = ANY(%s)",
            ([alice.workspace_id, bob.workspace_id],),
        )
        surviving = cursor.fetchone()

    assert surviving is not None
    assert surviving[0] == 2, "a hard DELETE removed a workspace row"


# ------------------------------------------------- the tests testing the tests --


def test_policies_are_what_makes_these_tests_pass(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """Prove the isolation above comes from RLS and not from an accident.

    Every assertion in this module is of the form "the other tenant's rows are
    absent". That shape passes just as happily against an empty table, a broken
    fixture, or a policy that was never enabled. This test disables RLS, shows
    the same query then returns both tenants, and restores it -- so a future
    change that quietly drops a policy turns this test red.

    Required by the step's Validation: *an isolation test that passes with RLS
    off is testing nothing.*
    """
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT id FROM public.workspaces")

        assert {row[0] for row in cursor.fetchall()} == {alice.workspace_id}

    with admin_connection.cursor() as cursor:
        cursor.execute("ALTER TABLE public.workspaces DISABLE ROW LEVEL SECURITY")

    try:
        with admin_connection.transaction():
            cursor = as_user(admin_connection, alice.user_id)
            cursor.execute("SELECT id FROM public.workspaces")
            visible = {row[0] for row in cursor.fetchall()}

        # With the policy gone, alice reaches bob's workspace. This is the
        # breach the migration prevents, demonstrated rather than asserted
        # about.
        assert visible == {alice.workspace_id, bob.workspace_id}
    finally:
        with admin_connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY")

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT id FROM public.workspaces")

        assert {row[0] for row in cursor.fetchall()} == {alice.workspace_id}


def test_membership_policy_does_not_recurse(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """Guard the SECURITY DEFINER indirection against a well-meaning "cleanup".

    A policy on `workspace_members` that queries `workspace_members` directly
    raises "infinite recursion detected in policy for relation". Inlining the
    helper function would look like a simplification and would break every
    authenticated query on this table.
    """
    alice, _bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT count(*) FROM public.workspace_members")
        row = cursor.fetchone()

    assert row is not None and row[0] == 1


def test_definer_function_is_not_executable_by_anon(
    admin_connection: psycopg.Connection,
) -> None:
    """`app_current_user_workspaces()` reads memberships with RLS bypassed.

    Supabase's default privileges grant EXECUTE on new public functions to
    `anon`, `authenticated` and `service_role` by name, so revoking from PUBLIC
    is not enough -- observed during STEP-09 validation. This test fails if that
    revoke is ever dropped from the migration.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
            ("anon", "public.app_current_user_workspaces()"),
        )
        anon_may_execute = cursor.fetchone()

        cursor.execute(
            "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
            ("authenticated", "public.app_current_user_workspaces()"),
        )
        authenticated_may_execute = cursor.fetchone()

    assert anon_may_execute is not None and anon_may_execute[0] is False
    assert authenticated_may_execute is not None and authenticated_may_execute[0] is True


def test_every_application_table_has_rls_enabled_and_forced(
    admin_connection: psycopg.Connection,
) -> None:
    """Catch a future table shipped without RLS (CLAUDE.md §16).

    Queries the catalog rather than a hardcoded list, so a table added later
    without a policy fails this test instead of being silently unprotected.
    `alembic_version` is Alembic's own bookkeeping, not application data.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND c.relname <> 'alembic_version'
            ORDER BY c.relname
            """
        )
        tables = cursor.fetchall()

    assert tables, "expected application tables to exist"

    unprotected = [name for name, enabled, forced in tables if not (enabled and forced)]

    assert unprotected == [], f"tables without RLS enabled and forced: {unprotected}"
