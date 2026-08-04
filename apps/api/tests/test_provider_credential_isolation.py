"""Tenant isolation for stored BYOK provider keys (STEP-17).

The highest-stakes isolation surface in the project so far. A cross-tenant read
of `workspaces` discloses a name; a cross-tenant read of this table discloses a
**credential that authorizes spend on another customer's account**. So it gets
the full [[RLS Policy Pattern]] treatment plus its own negative control.

Follows `test_rls_isolation.py` exactly rather than inventing a second style:
same `as_user` helper, same two-tenant fixture, same "prove the policies are
what makes this pass" test. A security suite whose shape differs from the
established one is a suite whose gaps are hard to see.

**These run against the request-path role indirectly** -- `as_user` drops to
`authenticated`, which is what `RequestSessionFactory` does per transaction. The
separate proof that the *application* connects as a non-bypassing role lives in
`test_request_session.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from app.repositories.provider_credentials import ProviderCredentialRepository
from tests.conftest import Identity, seed_identity

# Every test in this module needs a database, and skips without one.
pytestmark = pytest.mark.usefixtures("migrated_database")

CIPHERTEXT = "not-a-real-ciphertext-but-opaque"


def as_user(connection: psycopg.Connection, user_id: uuid.UUID) -> psycopg.Cursor:
    """Return a cursor acting as `authenticated` with the given identity."""
    cursor = connection.cursor()
    cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))
    cursor.execute("SET LOCAL ROLE authenticated")

    return cursor


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[tuple[Identity, Identity]]:
    """Seed two unrelated tenants, each owning one workspace."""
    yield seed_identity(admin_connection, "alice"), seed_identity(admin_connection, "bob")


@pytest.fixture
def seeded_credentials(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> Iterator[tuple[Identity, Identity]]:
    """Give each tenant one stored credential.

    Seeded over the owner connection, like every other fixture here: the INSERT
    policy requires owner/admin membership, and arranging state is not what these
    tests assert on.
    """
    alice, bob = tenants

    with admin_connection.cursor() as cursor:
        for identity in (alice, bob):
            cursor.execute(
                """
                INSERT INTO public.provider_credentials
                    (workspace_id, provider, encrypted_key, last_four, created_by)
                VALUES (%s, 'openai', %s, '1234', %s)
                """,
                (identity.workspace_id, f"{CIPHERTEXT}-{identity.workspace_id}", identity.user_id),
            )

    yield alice, bob

    with admin_connection.cursor() as cursor:
        cursor.execute("DELETE FROM public.provider_credentials")


# --------------------------------------------------------------------- read --


def test_a_tenant_reads_only_its_own_credential(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    alice, bob = seeded_credentials

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT workspace_id FROM public.provider_credentials")
        visible = {row[0] for row in cursor.fetchall()}

    assert visible == {alice.workspace_id}
    assert bob.workspace_id not in visible


def test_a_tenant_cannot_read_another_tenants_ciphertext(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """The disclosure that matters: the encrypted key itself.

    Even though the value is encrypted, reading it is a breach -- encryption is
    defence in depth behind RLS, not a substitute for it. A leaked encryption
    key would otherwise turn one policy gap into every workspace's credentials.
    """
    alice, bob = seeded_credentials

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "SELECT encrypted_key FROM public.provider_credentials WHERE workspace_id = %s",
            (bob.workspace_id,),
        )
        rows = cursor.fetchall()

    assert rows == []


def test_an_unauthenticated_session_reads_nothing(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """`auth.uid()` is NULL with no claim, so every policy must deny."""
    with admin_connection.transaction():
        cursor = admin_connection.cursor()
        cursor.execute("SET LOCAL ROLE authenticated")
        cursor.execute("SELECT count(*) FROM public.provider_credentials")
        count = cursor.fetchone()

    assert count is not None
    assert count[0] == 0


def test_a_soft_deleted_credential_is_invisible(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """A revoked key must stop being returned by every query that reads one.

    **Liveness is enforced in the queries, not in the SELECT policy**, since
    migration `d1f70a4c62be` ([[STEP-19 Settings and BYOK UI]]). A policy that
    filtered `deleted_at IS NULL` made revocation impossible for every role
    including `owner`: the `UPDATE` setting `deleted_at` produces a row the
    policy no longer matches, so PostgreSQL refused the write via the *read*
    policy. That is the same defect [[STEP-11a Membership Removal Policy]] fixed
    on `workspace_members`.

    So this asserts the guarantee at the layer that now owns it -- every
    repository method -- rather than at the layer that used to. Asserting a raw
    `SELECT count(*)` here would be asserting the defect: it would pass only
    while revocation was broken.

    The tenant boundary is unchanged and still proven by the policy, in
    `test_a_soft_deleted_credential_stays_within_its_tenant` below.
    """
    alice, _ = seeded_credentials

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.provider_credentials SET deleted_at = now() WHERE workspace_id = %s",
            (alice.workspace_id,),
        )

    repository = ProviderCredentialRepository(admin_connection)

    # Each of the three read paths, because "invisible" that holds for one query
    # and not another is exactly how a revoked key comes back to life.
    assert repository.credential_for(alice.workspace_id, "openai") is None
    assert repository.configured_providers(alice.workspace_id) == ()
    assert repository.list_summaries(alice.workspace_id) == ()


def test_a_soft_deleted_credential_stays_within_its_tenant(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """Widening liveness must not have widened *visibility*.

    The policy stopped filtering `deleted_at`, so a soft-deleted row is now
    reachable by the policy. This pins the property that actually matters: it is
    reachable by its **own** tenant only. If this ever passes for Bob, the
    revocation fix leaked another workspace's rows.
    """
    alice, bob = seeded_credentials

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.provider_credentials SET deleted_at = now() WHERE workspace_id = %s",
            (alice.workspace_id,),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, bob.user_id)
        cursor.execute(
            "SELECT count(*) FROM public.provider_credentials WHERE workspace_id = %s",
            (alice.workspace_id,),
        )
        count = cursor.fetchone()

    assert count is not None
    assert count[0] == 0


# -------------------------------------------------------------------- write --


def test_a_tenant_cannot_write_a_credential_into_another_workspace(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """Testing read alone is the common, insufficient version.

    A caller who cannot *see* another tenant's row could still plant one in
    their workspace without an INSERT policy that checks the target -- pointing
    that workspace's AI spend at an attacker-controlled account.
    """
    alice, bob = tenants

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                """
                INSERT INTO public.provider_credentials
                    (workspace_id, provider, encrypted_key, last_four, created_by)
                VALUES (%s, 'openai', 'planted', '9999', %s)
                """,
                (bob.workspace_id, alice.user_id),
            )


def test_a_tenant_cannot_update_another_tenants_credential(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """A USING mismatch affects zero rows silently, so the count is asserted."""
    alice, bob = seeded_credentials

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.provider_credentials SET encrypted_key = 'hijacked' "
            "WHERE workspace_id = %s",
            (bob.workspace_id,),
        )
        affected = cursor.rowcount

    assert affected == 0

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT encrypted_key FROM public.provider_credentials WHERE workspace_id = %s",
            (bob.workspace_id,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] != "hijacked"


def test_a_member_without_privilege_cannot_store_a_credential(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """Writes require owner or admin, not mere membership.

    A provider key authorizes spend on the workspace's upstream account, so it
    belongs with the roles that control billing-adjacent settings -- consistent
    with the role-aware policies STEP-11 established.
    """
    alice, bob = tenants

    # Make bob an ordinary member of alice's workspace.
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (alice.workspace_id, bob.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, bob.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                """
                INSERT INTO public.provider_credentials
                    (workspace_id, provider, encrypted_key, last_four, created_by)
                VALUES (%s, 'anthropic', 'member-written', '0000', %s)
                """,
                (alice.workspace_id, bob.user_id),
            )


def test_a_member_can_still_read_their_workspaces_credentials(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """SELECT is membership-scoped, not role-scoped.

    The router runs as whoever made the request, so an ordinary member making an
    AI call must be able to read the workspace's key. Requiring owner/admin to
    *read* would mean only admins could use AI at all.
    """
    alice, bob = seeded_credentials

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (alice.workspace_id, bob.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, bob.user_id)
        cursor.execute(
            "SELECT count(*) FROM public.provider_credentials WHERE workspace_id = %s",
            (alice.workspace_id,),
        )
        count = cursor.fetchone()

    assert count is not None
    assert count[0] == 1


def test_no_one_may_delete_a_credential_row(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """DELETE is granted to no one; removal is a soft delete.

    A DELETE path would be a second, unaudited removal route bypassing soft
    deletion entirely.
    """
    alice, _ = seeded_credentials

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                "DELETE FROM public.provider_credentials WHERE workspace_id = %s",
                (alice.workspace_id,),
            )


# ------------------------------------------------------------------ schema --


def test_the_table_has_rls_enabled_and_forced(admin_connection: psycopg.Connection) -> None:
    """ENABLE alone exempts the table owner; FORCE closes that gap."""
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = 'public.provider_credentials'::regclass"
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] is True, "RLS is not enabled"
    assert row[1] is True, "RLS is not forced -- the owner would bypass its own policies"


def test_anon_holds_no_grant_on_the_table(admin_connection: psycopg.Connection) -> None:
    """Grants are an independent gate from policies, and `anon` needs none."""
    with admin_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT privilege_type FROM information_schema.role_table_grants
            WHERE table_name = 'provider_credentials' AND grantee = 'anon'
            """
        )
        grants = cursor.fetchall()

    assert grants == []


def test_authenticated_holds_no_delete_or_truncate(
    admin_connection: psycopg.Connection,
) -> None:
    """TRUNCATE matters most: it is not subject to RLS at all.

    A role holding it could empty this table regardless of every policy above.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT privilege_type FROM information_schema.role_table_grants
            WHERE table_name = 'provider_credentials' AND grantee = 'authenticated'
            """
        )
        grants = {row[0] for row in cursor.fetchall()}

    assert "DELETE" not in grants
    assert "TRUNCATE" not in grants
    assert grants == {"SELECT", "INSERT", "UPDATE"}


def test_one_live_credential_per_workspace_and_provider(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """The partial unique index, and that it does not block rotation."""
    alice, _ = seeded_credentials

    with admin_connection.cursor() as cursor, pytest.raises(psycopg.errors.UniqueViolation):
        cursor.execute(
            """
            INSERT INTO public.provider_credentials
                (workspace_id, provider, encrypted_key, last_four, created_by)
            VALUES (%s, 'openai', 'second-live-key', '5678', %s)
            """,
            (alice.workspace_id, alice.user_id),
        )


def test_rotation_is_possible_after_a_soft_delete(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """The index is partial for this reason.

    Without the `deleted_at IS NULL` predicate, rotating a key twice would fail
    with a constraint violation that reads as a bug.
    """
    alice, _ = seeded_credentials

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.provider_credentials SET deleted_at = now() WHERE workspace_id = %s",
            (alice.workspace_id,),
        )
        cursor.execute(
            """
            INSERT INTO public.provider_credentials
                (workspace_id, provider, encrypted_key, last_four, created_by)
            VALUES (%s, 'openai', 'rotated-key', '5678', %s)
            """,
            (alice.workspace_id, alice.user_id),
        )
        cursor.execute(
            "SELECT count(*) FROM public.provider_credentials "
            "WHERE workspace_id = %s AND deleted_at IS NULL",
            (alice.workspace_id,),
        )
        count = cursor.fetchone()

    assert count is not None
    assert count[0] == 1


def test_the_touch_trigger_maintains_version(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """Regression guard for a defect caught during implementation.

    `touch_row()` sets `NEW.version = OLD.version + 1`. The first draft of the
    migration attached that trigger to a table with no `version` column, which
    would have failed **every** UPDATE -- including every key rotation and every
    revocation -- with "record new has no field version".
    """
    alice, _ = seeded_credentials

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.provider_credentials SET last_four = '4321' WHERE workspace_id = %s",
            (alice.workspace_id,),
        )
        cursor.execute(
            "SELECT version FROM public.provider_credentials WHERE workspace_id = %s",
            (alice.workspace_id,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == 2


# --------------------------------------------------------- negative control --


def test_policies_are_what_makes_these_tests_pass(
    admin_connection: psycopg.Connection, seeded_credentials: tuple[Identity, Identity]
) -> None:
    """Prove the isolation above comes from RLS and not from an accident.

    Every read assertion in this module has the shape "the other tenant's rows
    are absent", which passes just as happily against an empty table, a broken
    fixture, or a policy that was never created. This disables RLS, shows the
    same query then returns *both* tenants, and restores it.

    Required by [[RLS Policy Pattern]] step 8: confirm the test fails when the
    policy is removed. A test that passes either way is asserting nothing.
    """
    alice, bob = seeded_credentials

    with admin_connection.cursor() as cursor:
        cursor.execute("ALTER TABLE public.provider_credentials DISABLE ROW LEVEL SECURITY")

    try:
        with admin_connection.transaction():
            cursor = as_user(admin_connection, alice.user_id)
            cursor.execute("SELECT workspace_id FROM public.provider_credentials")
            visible = {row[0] for row in cursor.fetchall()}

        # The breach, observed. With RLS off, alice reads bob's credential row.
        assert bob.workspace_id in visible, (
            "Disabling RLS did not widen the result set -- these tests are not "
            "actually proving that the policies are what isolates tenants"
        )
    finally:
        with admin_connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public.provider_credentials ENABLE ROW LEVEL SECURITY")
            cursor.execute("ALTER TABLE public.provider_credentials FORCE ROW LEVEL SECURITY")

    # And restored: the same query is isolated again.
    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT workspace_id FROM public.provider_credentials")
        visible_again = {row[0] for row in cursor.fetchall()}

    assert visible_again == {alice.workspace_id}
