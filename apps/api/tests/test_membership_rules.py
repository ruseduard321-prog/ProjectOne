"""The membership removal rules (STEP-11a).

The five rules the project owner supplied on 2026-08-01, asserted against a real
database because they are enforced by RLS policies and a trigger:

1. The last owner may never leave or be removed.
2. An owner may remove admins and members.
3. An owner may transfer ownership before leaving.
4. An admin may remove members only.
5. A member may only leave the workspace themselves.

**Every rule is tested in both directions.** A predicate denying everyone passes
every denial test ever written; only the permitted case catches it. Rule 1 gets
three tests rather than one, because leaving, being removed, and being demoted
are three separate routes to the same broken state -- an ownerless workspace --
and closing two of them is not closing the hole.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from tests.conftest import Identity, seed_identity
from tests.test_rls_isolation import as_user

pytestmark = pytest.mark.usefixtures("migrated_database")


class Workspace:
    """One workspace holding an owner, an admin and a plain member."""

    def __init__(self, owner: Identity, admin: Identity, member: Identity) -> None:
        """Record the three identities sharing a single workspace."""
        self.owner = owner
        self.admin = admin
        self.member = member
        self.id = owner.workspace_id


@pytest.fixture
def workspace(admin_connection: psycopg.Connection) -> Iterator[Workspace]:
    """Seed one workspace containing all three roles."""
    owner = seed_identity(admin_connection, "rm-owner")
    admin = seed_identity(admin_connection, "rm-admin")
    member = seed_identity(admin_connection, "rm-member")

    with admin_connection.cursor() as cursor:
        for identity, role in ((admin, "admin"), (member, "member")):
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, %s)",
                (owner.workspace_id, identity.user_id, role),
            )

    yield Workspace(owner, admin, member)


def live_role(
    connection: psycopg.Connection, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    """Return a member's role, or None when their row is soft-deleted.

    Read over the owner connection, which bypasses RLS, so an assertion reflects
    what the table actually holds rather than what a policy chose to show.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT role FROM public.workspace_members "
            "WHERE workspace_id = %s AND user_id = %s AND deleted_at IS NULL",
            (workspace_id, user_id),
        )
        row = cursor.fetchone()

    return None if row is None else str(row[0])


# ------------------------------------------- rule 1: the last owner is pinned --


def test_the_last_owner_cannot_leave(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Route one to an ownerless workspace: the owner departs voluntarily."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)

        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, workspace.owner.user_id),
            )

    assert live_role(admin_connection, workspace.id, workspace.owner.user_id) == "owner"


def test_the_last_owner_cannot_be_demoted(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Route two, and the one that is easy to forget.

    Demotion empties the owner slot exactly as removal does. A guard that only
    watched `deleted_at` would let an owner rename themselves `member` and leave
    the workspace ownerless with every row still live.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)

        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                "UPDATE public.workspace_members SET role = 'admin' "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, workspace.owner.user_id),
            )

    assert live_role(admin_connection, workspace.id, workspace.owner.user_id) == "owner"


def test_the_last_owner_cannot_be_removed_by_anyone_else(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Route three: an admin tries to remove the owner.

    Denied twice over -- by the ranked USING clause and by the trigger -- so the
    test accepts either. Asserting the specific mechanism would make this fail
    whenever the defence got stronger.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.admin.user_id)

        try:
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, workspace.owner.user_id),
            )
            assert cursor.rowcount == 0
        except (psycopg.errors.CheckViolation, psycopg.errors.InsufficientPrivilege):
            pass

    assert live_role(admin_connection, workspace.id, workspace.owner.user_id) == "owner"


def test_an_owner_may_leave_once_a_second_owner_exists(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The permitted direction of rule 1.

    Without this, a trigger that refused *every* owner departure would pass all
    three tests above while making ownership permanent.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.workspace_members SET role = 'owner' "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.admin.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.owner.user_id),
        )

        assert cursor.rowcount == 1

    assert live_role(admin_connection, workspace.id, workspace.owner.user_id) is None
    assert live_role(admin_connection, workspace.id, workspace.admin.user_id) == "owner"


# ---------------------------------------------- rules 2 and 4: ranked removal --


def test_an_owner_may_remove_an_admin(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Rule 2."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.admin.user_id),
        )

        assert cursor.rowcount == 1

    assert live_role(admin_connection, workspace.id, workspace.admin.user_id) is None


def test_an_owner_may_remove_a_member(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Rule 2, the other half."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

        assert cursor.rowcount == 1


def test_an_admin_may_remove_a_member(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Rule 4, the permitted half."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.admin.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

        assert cursor.rowcount == 1

    assert live_role(admin_connection, workspace.id, workspace.member.user_id) is None


def test_an_admin_may_not_remove_another_admin(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Rule 4 states this by omission; the strict rank comparison states it outright.

    The most likely way to get this wrong is a `>=` where a `>` belongs, which
    reads identically and quietly lets admins purge each other.
    """
    second_admin = seed_identity(admin_connection, "rm-admin2")

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'admin')",
            (workspace.id, second_admin.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.admin.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, second_admin.user_id),
        )

        assert cursor.rowcount == 0

    assert live_role(admin_connection, workspace.id, second_admin.user_id) == "admin"


def test_a_member_may_not_remove_anyone(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Rule 5 by exclusion: a member outranks nobody."""
    for target in (workspace.owner, workspace.admin):
        with admin_connection.transaction():
            cursor = as_user(admin_connection, workspace.member.user_id)
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, target.user_id),
            )

            assert cursor.rowcount == 0

    assert live_role(admin_connection, workspace.id, workspace.owner.user_id) == "owner"
    assert live_role(admin_connection, workspace.id, workspace.admin.user_id) == "admin"


# --------------------------------------------------------- rule 5: leaving --


def test_a_member_may_leave(admin_connection: psycopg.Connection, workspace: Workspace) -> None:
    """Rule 5, and the operation STEP-11 proved was impossible.

    This is the test that would have failed before STEP-11a, for every role
    including the owner.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

        assert cursor.rowcount == 1

    assert live_role(admin_connection, workspace.id, workspace.member.user_id) is None


def test_an_admin_may_leave(admin_connection: psycopg.Connection, workspace: Workspace) -> None:
    """Nobody is kept in a workspace against their will except the last owner."""
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.admin.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.admin.user_id),
        )

        assert cursor.rowcount == 1


def test_a_departing_member_loses_access_immediately(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Leaving must actually revoke access, not merely mark a row.

    `app_current_user_workspaces()` still filters `deleted_at IS NULL`, which is
    what makes the soft delete a real removal. The SELECT policy dropping that
    filter (STEP-11a) must not have weakened it.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.member.user_id)
        cursor.execute("SELECT id FROM public.workspaces WHERE id = %s", (workspace.id,))

        assert cursor.fetchall() == []


# ------------------------------------------- rule 3: promotion and transfer --


def test_only_an_owner_may_create_another_owner(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The WITH CHECK half of rule 3.

    An admin holds MANAGE_MEMBERS and may edit a member's row -- so without this
    clause they could promote that member to `owner`, or promote themselves via
    a second admin. Ownership would stop being an owner-controlled act.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.admin.user_id)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                "UPDATE public.workspace_members SET role = 'owner' "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, workspace.member.user_id),
            )

    assert live_role(admin_connection, workspace.id, workspace.member.user_id) == "member"


def test_an_owner_may_transfer_ownership_atomically(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Rule 3, as the service performs it: promote then demote, one transaction.

    The deferrable trigger is what permits the intermediate two-owner state. A
    non-deferrable constraint would make this depend on statement order, which
    is a correctness trap disguised as a detail.
    """
    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute(
            "UPDATE public.workspace_members SET role = 'owner' "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.admin.user_id),
        )
        cursor.execute(
            "UPDATE public.workspace_members SET role = 'admin' "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.owner.user_id),
        )

    assert live_role(admin_connection, workspace.id, workspace.admin.user_id) == "owner"
    assert live_role(admin_connection, workspace.id, workspace.owner.user_id) == "admin"

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM public.workspace_members "
            "WHERE workspace_id = %s AND role = 'owner' AND deleted_at IS NULL",
            (workspace.id,),
        )
        owners = cursor.fetchone()

    assert owners is not None
    assert owners[0] == 1, "transfer must leave exactly one owner"


# ------------------------------------ the SELECT policy change, specifically --


def test_removed_members_remain_visible_to_the_workspace(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """What STEP-11a's SELECT policy change actually widened, asserted deliberately.

    A live member can now read the soft-deleted membership rows of their own
    workspace. That is the price of making removal possible at all, and it is
    bounded: it is a list of who used to be in a workspace you are in, never
    another tenant's data.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute(
            "SELECT user_id FROM public.workspace_members WHERE workspace_id = %s",
            (workspace.id,),
        )
        visible = {row[0] for row in cursor.fetchall()}

    assert workspace.member.user_id in visible


def test_removed_members_are_excluded_from_listings(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The filter moved from the policy into the queries, so the queries must carry it.

    This is the regression the SELECT policy change risks: a listing that
    inherited `deleted_at IS NULL` from the policy and never said so now shows
    removed members. Every application query that must exclude them says so
    explicitly, and this asserts the shape they all use.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)
        cursor.execute(
            "SELECT user_id FROM public.workspace_members "
            "WHERE workspace_id = %s AND deleted_at IS NULL",
            (workspace.id,),
        )
        live = {row[0] for row in cursor.fetchall()}

    assert workspace.member.user_id not in live
    assert live == {workspace.owner.user_id, workspace.admin.user_id}


def test_the_select_policy_still_blocks_the_other_tenant(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """The change dropped `deleted_at`, never the tenant predicate.

    The one thing this step must not have done is widen the workspace boundary
    while widening visibility inside it. A stranger sees nothing, deleted or
    otherwise.
    """
    stranger = seed_identity(admin_connection, "rm-stranger")

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.workspace_members SET deleted_at = now() "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace.id, workspace.member.user_id),
        )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, stranger.user_id)
        cursor.execute(
            "SELECT user_id FROM public.workspace_members WHERE workspace_id = %s",
            (workspace.id,),
        )

        assert cursor.fetchall() == []


# ------------------------------------------- the tests testing the tests --


def test_the_trigger_is_what_pins_the_last_owner(
    admin_connection: psycopg.Connection, workspace: Workspace
) -> None:
    """Prove rule 1's denials come from the trigger and not from an accident.

    Disables the trigger, shows the last owner can then leave and orphan the
    workspace, and restores it. Without this, every rule 1 test above would pass
    just as happily against a policy that denied the update for some unrelated
    reason.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE public.workspace_members "
            "DISABLE TRIGGER trg_workspace_members_protect_last_owner"
        )

    try:
        with admin_connection.transaction():
            cursor = as_user(admin_connection, workspace.owner.user_id)
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, workspace.owner.user_id),
            )

            # With the trigger gone the workspace is orphaned. This is the state
            # rule 1 exists to prevent, demonstrated rather than asserted about.
            assert cursor.rowcount == 1
    finally:
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = NULL "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, workspace.owner.user_id),
            )
            cursor.execute(
                "ALTER TABLE public.workspace_members "
                "ENABLE TRIGGER trg_workspace_members_protect_last_owner"
            )

    with admin_connection.transaction():
        cursor = as_user(admin_connection, workspace.owner.user_id)

        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace.id, workspace.owner.user_id),
            )


def test_role_resolution_function_is_not_executable_by_anon(
    admin_connection: psycopg.Connection,
) -> None:
    """The third SECURITY DEFINER function must be locked down like the first two.

    Supabase grants EXECUTE to `anon` **by name** at creation time, and a revoke
    from PUBLIC does not remove it. Each new definer function has to revoke by
    name or it is reachable unauthenticated.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_function_privilege('anon', 'public.app_workspace_role(uuid)', 'EXECUTE')"
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] is False, "anon can execute the role-resolution definer function"
