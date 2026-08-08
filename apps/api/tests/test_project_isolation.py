"""Tenant isolation for `projects` and `assets` (STEP-20).

Follows `test_provider_credential_isolation.py` exactly rather than inventing a
third style: same `as_user` helper, same two-tenant fixture, same "prove the
policies are what makes this pass" negative control. A security suite whose
shape differs from the established one is a suite whose gaps are hard to see.

**These run against the request-path role indirectly** -- `as_user` drops to
`authenticated`, which is what `RequestSessionFactory` does per transaction. The
separate proof that the *application* connects as a non-bypassing role lives in
`test_request_session.py`.

Two things here are not isolation tests and are here anyway, because they can
only be proven against a real database:

- **The soft delete actually succeeds.** The defect STEP-11a and STEP-19 each
  paid for -- a SELECT policy filtering `deleted_at IS NULL` making the soft
  delete impossible -- is invisible to every offline test and to code review.
- **The status vocabulary matches the CHECK constraint.** Two lists edited in
  different files, which is the shape that drifts.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from app.repositories.projects import ProjectRepository
from app.services.project_service import ProjectService, ProjectStatus
from tests.conftest import Identity, seed_identity

# Every test in this module needs a database, and skips without one.
pytestmark = pytest.mark.usefixtures("migrated_database")


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
def seeded_projects(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> Iterator[tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]]]:
    """Give each tenant one project holding one asset.

    Seeded over the owner connection, like every other fixture here: arranging
    state is not what these tests assert on.

    Returns the two identities plus a workspace -> project id mapping, so a test
    can name the *other* tenant's project without a second query.
    """
    alice, bob = tenants
    projects: dict[uuid.UUID, uuid.UUID] = {}

    with admin_connection.cursor() as cursor:
        for identity in (alice, bob):
            cursor.execute(
                """
                INSERT INTO public.projects (workspace_id, name, status, created_by)
                VALUES (%s, %s, 'idea', %s)
                RETURNING id
                """,
                (identity.workspace_id, f"Project {identity.email}", identity.user_id),
            )
            row = cursor.fetchone()
            assert row is not None
            project_id = row[0]
            projects[identity.workspace_id] = project_id

            cursor.execute(
                """
                INSERT INTO public.assets
                    (workspace_id, project_id, name, kind, created_by)
                VALUES (%s, %s, 'brief.md', 'document', %s)
                """,
                (identity.workspace_id, project_id, identity.user_id),
            )

    yield alice, bob, projects

    with admin_connection.cursor() as cursor:
        cursor.execute("DELETE FROM public.assets")
        cursor.execute("DELETE FROM public.projects")


# --------------------------------------------------------------------- read --


def test_a_tenant_reads_only_its_own_projects(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """Alice's project listing contains her workspace and not Bob's."""
    alice, bob, _ = seeded_projects

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT workspace_id FROM public.projects")
        visible = {row[0] for row in cursor.fetchall()}

    assert alice.workspace_id in visible
    assert bob.workspace_id not in visible


def test_a_tenant_reads_only_its_own_assets(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """The same boundary holds on `assets`, which has its own policy.

    Asserted separately rather than assumed from the `projects` result: `assets`
    carries its own `workspace_id` and its own policy, so its isolation is a
    distinct property and not a consequence of the project one.
    """
    alice, bob, _ = seeded_projects

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT workspace_id FROM public.assets")
        visible = {row[0] for row in cursor.fetchall()}

    assert alice.workspace_id in visible
    assert bob.workspace_id not in visible


def test_naming_another_tenants_project_id_returns_nothing(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """Knowing the id is not access.

    The strongest read assertion available: a listing being filtered could be an
    accident of a `WHERE` clause, while a direct lookup by primary key removes
    every filter except the policy.
    """
    alice, bob, projects = seeded_projects

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "SELECT id FROM public.projects WHERE id = %s", (projects[bob.workspace_id],)
        )

        assert cursor.fetchone() is None


# -------------------------------------------------------------------- write --


def test_a_tenant_cannot_update_another_tenants_project(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """A cross-tenant UPDATE affects zero rows.

    Silently, which is the documented `USING` failure mode -- a `WITH CHECK`
    violation raises instead. Asserting the rowcount rather than expecting an
    exception is what makes this test correct rather than accidentally passing
    on the wrong error.
    """
    alice, bob, projects = seeded_projects

    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.projects SET name = 'seized' WHERE id = %s",
            (projects[bob.workspace_id],),
        )

        assert cursor.rowcount == 0


def test_a_tenant_cannot_move_its_project_into_another_workspace(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """The `WITH CHECK` half: a row may not *become* another tenant's.

    Without `WITH CHECK` on the UPDATE policy this would succeed -- the row is
    visible, so the update proceeds, and the result belongs to Bob. This is a
    cross-tenant write dressed as an edit, and it raises rather than affecting
    zero rows.
    """
    alice, bob, projects = seeded_projects

    with admin_connection.transaction(), pytest.raises(psycopg.errors.Error):
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            "UPDATE public.projects SET workspace_id = %s WHERE id = %s",
            (bob.workspace_id, projects[alice.workspace_id]),
        )


def test_a_tenant_cannot_insert_a_project_into_another_workspace(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """The INSERT policy refuses a row naming a workspace the caller is not in."""
    alice, bob = tenants

    with admin_connection.transaction(), pytest.raises(psycopg.errors.Error):
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            """
            INSERT INTO public.projects (workspace_id, name, status, created_by)
            VALUES (%s, 'planted', 'idea', %s)
            """,
            (bob.workspace_id, alice.user_id),
        )


def test_an_asset_cannot_claim_a_project_from_another_workspace(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """The composite foreign key closes the hole denormalization would open.

    This is the attack the `(project_id, workspace_id)` foreign key exists for:
    Alice inserts an asset naming **her own** workspace -- satisfying the RLS
    policy, which only tests `workspace_id` -- while pointing `project_id` at
    Bob's project. Without the composite key the row would be accepted and Bob's
    project would silently accumulate an asset belonging to another tenant.

    It fails on the foreign key rather than on RLS, and that is the point: RLS
    cannot see the mismatch, so a second mechanism has to.
    """
    alice, bob, projects = seeded_projects

    with admin_connection.transaction(), pytest.raises(psycopg.errors.ForeignKeyViolation):
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute(
            """
            INSERT INTO public.assets
                (workspace_id, project_id, name, kind, created_by)
            VALUES (%s, %s, 'smuggled', 'document', %s)
            """,
            (alice.workspace_id, projects[bob.workspace_id], alice.user_id),
        )


def test_delete_is_refused_on_both_tables(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """No DELETE policy and no DELETE grant, on either table.

    Refused even on the caller's *own* rows: removal is a soft delete, and a
    DELETE path would be a second, unaudited one bypassing it entirely.
    """
    alice, _, projects = seeded_projects

    for table in ("public.assets", "public.projects"):
        with admin_connection.transaction(), pytest.raises(psycopg.errors.Error):
            cursor = as_user(admin_connection, alice.user_id)
            cursor.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed literals

    # The rows survived, which is the assertion the refusals above imply but do
    # not prove on their own.
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM public.projects WHERE id = %s",
            (projects[alice.workspace_id],),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == 1


# ------------------------------------------------------------- soft delete --


def test_soft_deleting_a_project_succeeds(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """**The step's headline validation**, and a guard against a twice-paid defect.

    Soft-deleting a row is impossible when the table's SELECT policy filters
    `deleted_at IS NULL`: the UPDATE produces a row the policy no longer
    matches, and PostgreSQL refuses it with an error naming row-level security
    while pointing at the UPDATE policy, where nothing is wrong.

    [[STEP-11a Membership Removal Policy]] paid for this on `workspace_members`
    and [[STEP-19 Settings and BYOK UI]] paid for it again on
    `provider_credentials`, where `erase` had been silently failing since
    STEP-17 -- a CLAUDE.md §16 obligation broken with nothing covering it.

    Asserted **through the service**, as the step's Validation section requires,
    so it covers the real path rather than a hand-written UPDATE that happens to
    work.
    """
    alice, _, projects = seeded_projects

    with admin_connection.transaction():
        as_user(admin_connection, alice.user_id)
        service = ProjectService(ProjectRepository(admin_connection))

        service.delete(alice.workspace_id, projects[alice.workspace_id])

        # Gone from the live listing...
        assert service.list_for_workspace(alice.workspace_id) == ()

    # ...and marked rather than removed, verified as the owner so the check is
    # not itself subject to the policy under test.
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT deleted_at FROM public.projects WHERE id = %s",
            (projects[alice.workspace_id],),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] is not None, "the project was hard-deleted rather than soft-deleted"


def test_soft_deleting_an_asset_succeeds(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """The same property on `assets`, which has its own SELECT policy."""
    alice, _, projects = seeded_projects

    with admin_connection.transaction():
        as_user(admin_connection, alice.user_id)
        repository = ProjectRepository(admin_connection)

        assets = repository.list_assets(alice.workspace_id, projects[alice.workspace_id])
        assert len(assets) == 1

        assert repository.soft_delete_asset(alice.workspace_id, assets[0].id) is True
        assert repository.list_assets(alice.workspace_id, projects[alice.workspace_id]) == ()


def test_a_tenant_cannot_soft_delete_another_tenants_project(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """Soft deletion works, and stops at the tenant boundary.

    The pair matters: the previous test proves the policy is permissive enough
    to allow a soft delete, and this proves that permissiveness did not widen
    past the workspace. Either one alone is half the property.
    """
    alice, bob, projects = seeded_projects

    with admin_connection.transaction():
        as_user(admin_connection, alice.user_id)
        repository = ProjectRepository(admin_connection)

        assert repository.soft_delete(bob.workspace_id, projects[bob.workspace_id]) is False

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT deleted_at FROM public.projects WHERE id = %s",
            (projects[bob.workspace_id],),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] is None, "alice soft-deleted bob's project"


# -------------------------------------------------------- schema agreement --


def test_status_vocabulary_matches_the_database(
    admin_connection: psycopg.Connection,
) -> None:
    """`ProjectStatus` and `ck_projects_status_valid` list the same nine values.

    Two lists in two files, which is the shape that drifts. A value in the enum
    but not the constraint is a status the service will offer and the database
    will refuse; the reverse is a state nothing can ever reach.

    Asserted by writing each value rather than by parsing the constraint's
    source text: a regex over `pg_get_constraintdef` would pass against a
    constraint that had been dropped and recreated wrongly, while an INSERT
    proves the database genuinely accepts it.
    """
    identity = seed_identity(admin_connection, "vocabulary")

    for status in ProjectStatus:
        with admin_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.projects (workspace_id, name, status, created_by)
                VALUES (%s, %s, %s, %s)
                """,
                (identity.workspace_id, f"p-{status}", str(status), identity.user_id),
            )

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(DISTINCT status) FROM public.projects WHERE workspace_id = %s",
            (identity.workspace_id,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == len(ProjectStatus)

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM public.projects WHERE workspace_id = %s",
            (identity.workspace_id,),
        )


def test_a_status_outside_the_vocabulary_is_refused(
    admin_connection: psycopg.Connection, tenants: tuple[Identity, Identity]
) -> None:
    """The CHECK constraint is what makes the enum's guarantee real.

    Without it the service could reason about nine states while the column held
    anything, and `ProjectStatus(project.status)` would raise on read rather
    than on write -- a corruption discovered by the next reader instead of the
    writer who caused it.
    """
    alice, _ = tenants

    with admin_connection.transaction(), pytest.raises(psycopg.errors.CheckViolation):
        with admin_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.projects (workspace_id, name, status, created_by)
                VALUES (%s, 'bad', 'shipped', %s)
                """,
                (alice.workspace_id, alice.user_id),
            )


def test_both_tables_have_rls_enabled_and_forced(
    admin_connection: psycopg.Connection,
) -> None:
    """ENABLE alone lets the table owner bypass its own policies; FORCE closes it.

    `test_every_application_table_has_rls_enabled_and_forced` covers this across
    the schema; asserting it here too means a failure names these tables rather
    than surfacing as one entry in a catalog-wide list.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('projects', 'assets') "
            "AND relnamespace = 'public'::regnamespace"
        )
        rows = cursor.fetchall()

    assert len(rows) == 2

    for name, enabled, forced in rows:
        assert enabled, f"RLS is not enabled on {name}"
        assert forced, f"RLS is not forced on {name}"


# --------------------------------------------------------- negative control --


def test_policies_are_what_makes_these_tests_pass(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """Prove the isolation above comes from RLS and not from an accident.

    Every read assertion in this module has the shape "the other tenant's rows
    are absent", which passes just as happily against an empty table, a broken
    fixture, or a policy that was never created. This disables RLS on both
    tables, shows the same queries then return *both* tenants, and restores it.

    Required by [[RLS Policy Pattern]] step 8: confirm the test fails when the
    policy is removed. A test that passes either way is asserting nothing.
    """
    alice, bob, _ = seeded_projects

    with admin_connection.cursor() as cursor:
        cursor.execute("ALTER TABLE public.projects DISABLE ROW LEVEL SECURITY")
        cursor.execute("ALTER TABLE public.assets DISABLE ROW LEVEL SECURITY")

    try:
        with admin_connection.transaction():
            cursor = as_user(admin_connection, alice.user_id)
            cursor.execute("SELECT workspace_id FROM public.projects")
            projects_visible = {row[0] for row in cursor.fetchall()}
            cursor.execute("SELECT workspace_id FROM public.assets")
            assets_visible = {row[0] for row in cursor.fetchall()}

        # The breach, observed. With RLS off, alice reads bob's rows.
        assert bob.workspace_id in projects_visible, (
            "Disabling RLS did not widen the project result set -- these tests are "
            "not actually proving that the policies are what isolates tenants"
        )
        assert bob.workspace_id in assets_visible, (
            "Disabling RLS did not widen the asset result set -- the assets tests "
            "are not proving isolation"
        )
    finally:
        with admin_connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY")
            cursor.execute("ALTER TABLE public.projects FORCE ROW LEVEL SECURITY")
            cursor.execute("ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY")
            cursor.execute("ALTER TABLE public.assets FORCE ROW LEVEL SECURITY")

    # Restored, and verified rather than assumed -- a negative control that left
    # RLS off would silently disarm every test that runs after it.
    with admin_connection.transaction():
        cursor = as_user(admin_connection, alice.user_id)
        cursor.execute("SELECT workspace_id FROM public.projects")

        assert bob.workspace_id not in {row[0] for row in cursor.fetchall()}


# ------------------------------------------------------- export and erasure --


def test_a_workspace_erasure_reports_both_new_stores(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """Registration proven by a non-zero count, not by reading the registry.

    The step's Validation requires this specifically, because the failure it
    catches is silent: an unregistered store leaves a workspace erasure
    reporting success while the data remains (CLAUDE.md §16). STEP-18 found that
    on `provider_credentials`, and STEP-19 found the erase path broken again.

    Uses the stores directly rather than through `DataOwnershipService`, which
    would additionally require an `AuthorizationService` and a membership
    lookup -- neither of which is what this asserts.
    """
    from app.services.data_ownership_service import AssetStore, ProjectStore

    alice, _, _ = seeded_projects

    with admin_connection.transaction():
        as_user(admin_connection, alice.user_id)

        assert len(ProjectStore().export(admin_connection, alice.workspace_id)) == 1
        assert len(AssetStore().export(admin_connection, alice.workspace_id)) == 1

        assert AssetStore().erase(admin_connection, alice.workspace_id) == 1
        assert ProjectStore().erase(admin_connection, alice.workspace_id) == 1

        # Erased, and therefore absent from a subsequent export.
        assert ProjectStore().export(admin_connection, alice.workspace_id) == []
        assert AssetStore().export(admin_connection, alice.workspace_id) == []


def test_an_export_cannot_reach_another_tenants_projects(
    admin_connection: psycopg.Connection,
    seeded_projects: tuple[Identity, Identity, dict[uuid.UUID, uuid.UUID]],
) -> None:
    """An export handed the wrong workspace id returns nothing.

    The stores run over the tenant connection, so RLS decides what they can
    reach -- an export cannot become a cross-tenant read path by being called
    with another workspace's id.
    """
    from app.services.data_ownership_service import AssetStore, ProjectStore

    alice, bob, _ = seeded_projects

    with admin_connection.transaction():
        as_user(admin_connection, alice.user_id)

        assert ProjectStore().export(admin_connection, bob.workspace_id) == []
        assert AssetStore().export(admin_connection, bob.workspace_id) == []
