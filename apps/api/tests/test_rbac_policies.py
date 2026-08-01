"""Role-aware RLS tests (STEP-11).

STEP-09's tests prove the *tenant* boundary: workspace A cannot reach workspace
B. These prove the boundary *inside* a workspace -- that `owner`, `admin` and
`member` are enforced rather than merely stored.

They are deliberately separate from `test_rls_isolation.py`. That module answers
"can an outsider get in", this one answers "what can an insider do", and the two
fail for entirely different reasons. Keeping them apart means a red test names
which of the two properties broke.

**Both directions are tested for every rule.** A permission check that denies
everything passes every one-sided test, and would be caught only by the
positive case. Each denial below therefore has a matching test showing the
privileged role succeeds at the same operation.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from tests.conftest import Identity, seed_identity
from tests.test_rls_isolation import as_user

pytestmark = pytest.mark.usefixtures("migrated_database")


class Workspace:
    """One workspace with an owner, an admin and a plain member in it."""

    def __init__(self, owner: Identity, admin: Identity, member: Identity) -> None:
        """Record the three identities sharing a single workspace."""
        self.owner = owner
        self.admin = admin
        self.member = member
        self.id = owner.workspace_id


@pytest.fixture
def workspace(admin_connection: psycopg.Connection) -> Iterator[Workspace]:
    """Seed one workspace holding all three roles.

    Seeded over the owner connection because the INSERT policies deliberately do
    not permit bootstrapping membership from a client -- the same reason
    `seed_identity` does (see `conftest.admin_connection`).
    """
    owner = seed_identity(admin_connection, "owner")
    admin = seed_identity(admin_connection, "admin")
    member = seed_identity(admin_connection, "member")

    with admin_connection.cursor() as cursor:
        for identity, role in ((admin, "admin"), (member, "member")):
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, %s)",
                (owner.workspace_id, identity.user_id, role),
            )

    yield Workspace(owner, admin, member)


# ---------------------------------------------------------- workspace update --


def test_member_cannot_rename_the_workspace(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The gap STEP-09 deliberately left open, now closed.

    Before this step a plain member could rename the workspace exactly like its
    owner: the policy asked only for membership. The failure is silent -- an
    UPDATE the USING clause excludes affects zero rows rather than raising --
    which is why the row is re-read below rather than trusting `rowcount` alone.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute(
            "UPDATE public.workspaces SET name = %s WHERE id = %s",
            ("renamed by a member", workspace.id),
        )

        assert cursor.rowcount == 0

    with admin_connection.cursor() as cursor:
        cursor.execute("SELECT name FROM public.workspaces WHERE id = %s", (workspace.id,))
        row = cursor.fetchone()

    assert row is not None
    assert row[0] != "renamed by a member"


def test_owner_can_rename_the_workspace(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The other direction. Without this, a policy denying everyone would pass."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute(
            "UPDATE public.workspaces SET name = %s WHERE id = %s",
            ("renamed by the owner", workspace.id),
        )

        assert cursor.rowcount == 1

    with admin_connection.cursor() as cursor:
        cursor.execute("SELECT name FROM public.workspaces WHERE id = %s", (workspace.id,))
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == "renamed by the owner"


def test_admin_can_rename_the_workspace(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """`admin` holds UPDATE_WORKSPACE. Asserted so the matrix is not owner-only."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.admin.user_id)
        cursor.execute(
            "UPDATE public.workspaces SET name = %s WHERE id = %s",
            ("renamed by an admin", workspace.id),
        )

        assert cursor.rowcount == 1


def test_member_still_reads_the_workspace(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Tightening UPDATE must not have narrowed SELECT.

    `VIEW_WORKSPACE` is held by every role. A role-aware predicate accidentally
    applied to the SELECT policy would break the product for ordinary members
    while every denial test above still passed.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute("SELECT id FROM public.workspaces WHERE id = %s", (workspace.id,))

        assert cursor.fetchall() == [(workspace.id,)]


# --------------------------------------------------------- membership update --


def test_member_cannot_change_another_members_role(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The privilege-escalation path this step exists to close."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET role = 'member' "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.admin.user_id),
        )

        assert cursor.rowcount == 0


def test_member_cannot_promote_themselves(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The own-row carve-out must not be a self-promotion route.

    A member may edit their own membership row -- that is how leaving a
    workspace works, since removal is a soft delete. The `WITH CHECK` pins the
    role to `member`, so the one thing they may not do to their own row is
    change what it grants them. A WITH CHECK violation raises rather than
    matching zero rows.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                "UPDATE public.workspace_members SET role = 'owner' "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, workspace.member.user_id),
            )

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT role FROM public.workspace_members WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == "member"


def test_member_can_edit_their_own_membership_row(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The own-row branch of the UPDATE policy admits the caller's own row.

    Asserted with a role-preserving write rather than a soft delete, because
    soft-deleting one's own row is blocked upstream -- see the test below.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET role = 'member' "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

        assert cursor.rowcount == 1


# `test_self_removal_is_blocked_by_the_step_09_select_policy` lived here and was
# deleted by STEP-11a, exactly as its own docstring instructed: it pinned a
# limitation that no longer exists. Leaving and removal are now governed by the
# owner's rules and covered by `tests/test_membership_rules.py`.


def test_member_cannot_hand_their_membership_to_someone_else(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """`user_id` is pinned by the WITH CHECK, so the row cannot be reassigned."""
    stranger = uuid.uuid4()

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                "UPDATE public.workspace_members SET user_id = %s "
                "WHERE workspace_id = %s AND user_id = %s",
                (stranger, workspace.id, workspace.member.user_id),
            )


def test_owner_can_change_a_members_role(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The positive case for membership management."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET role = 'admin' "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

        assert cursor.rowcount == 1


def test_admin_can_change_a_members_role(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """`admin` holds MANAGE_MEMBERS."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.admin.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET role = 'admin' "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

        assert cursor.rowcount == 1


# ------------------------------------------------- the tests testing the tests --


def test_role_predicate_is_what_denies_the_member(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Prove the denials above come from the role predicate, not an accident.

    Every denial in this module has the shape "rowcount == 0", which passes just
    as happily against a broken fixture, an empty table, or a policy that never
    matched anyone. This test restores STEP-09's role-blind predicate, shows the
    member *can* then rename the workspace, and puts the tightened policy back.

    Required by the step's Validation: *the new tests fail when the role
    predicate is removed.*
    """
    tightened = """
        CREATE POLICY workspaces_update_privileged ON public.workspaces
        FOR UPDATE TO authenticated
        USING (
            deleted_at IS NULL
            AND id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
        )
        WITH CHECK (
            id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
        );
    """

    role_blind = """
        CREATE POLICY workspaces_update_privileged ON public.workspaces
        FOR UPDATE TO authenticated
        USING (
            deleted_at IS NULL
            AND id IN (SELECT public.app_current_user_workspaces())
        )
        WITH CHECK (id IN (SELECT public.app_current_user_workspaces()));
    """

    with admin_connection.cursor() as cursor:
        cursor.execute("DROP POLICY workspaces_update_privileged ON public.workspaces")
        cursor.execute(role_blind)

    try:
        with admin_connection.transaction():
            cursor = as_user(admin_connection, workspace.member.user_id)
            cursor.execute(
                "UPDATE public.workspaces SET name = %s WHERE id = %s",
                ("renamed without the role predicate", workspace.id),
            )

            # With the predicate gone, a plain member renames the workspace.
            # This is the hole the migration closes, demonstrated rather than
            # asserted about.
            assert cursor.rowcount == 1
    finally:
        with admin_connection.cursor() as cursor:
            cursor.execute("DROP POLICY workspaces_update_privileged ON public.workspaces")
            cursor.execute(tightened)

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute(
            "UPDATE public.workspaces SET name = %s WHERE id = %s",
            ("renamed after restoring the predicate", workspace.id),
        )

        assert cursor.rowcount == 0


def test_role_function_is_not_executable_by_anon(admin_connection: psycopg.Connection) -> None:
    """The new SECURITY DEFINER function must be locked down like STEP-09's.

    Supabase's default privileges grant EXECUTE to `anon` **by name** at creation
    time, and `REVOKE ... FROM PUBLIC` does not remove a grant a named role holds
    explicitly -- observed on the live database during STEP-09. A new definer
    function that only revoked from PUBLIC would be reachable by an
    unauthenticated role.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_function_privilege("
            "  'anon', 'public.app_current_user_workspaces_as(text[])', 'EXECUTE')"
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] is False, "anon can execute the role-resolution definer function"


def test_role_function_only_ever_answers_about_the_caller(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The function's parameter selects roles, never whose access to inspect.

    STEP-09's helper takes no parameters precisely so a caller cannot ask what
    *another* user can see. This one takes a parameter, so the property has to be
    asserted rather than assumed: identity still comes from `auth.uid()`
    internally, so the answer is always about the caller.

    Asserted against **the shared workspace specifically** rather than against an
    empty result. `seed_identity` gives every identity a workspace of their own
    that they own, so the member legitimately appears as an owner *somewhere* --
    just not here. An `== []` assertion would fail for a reason that has nothing
    to do with the property under test.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute("SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin'])")
        privileged = {row[0] for row in cursor.fetchall()}

    # The member does not administer the shared workspace, and asking for
    # owner-level access does not produce the owner's answer.
    assert workspace.id not in privileged
    assert privileged == {workspace.member.workspace_id}

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute("SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin'])")

        assert workspace.id in {row[0] for row in cursor.fetchall()}
