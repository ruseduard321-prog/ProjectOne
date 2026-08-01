"""The role model itself (STEP-11).

Offline and fast: this asserts the matrix in `app/core/permissions.py`, which is
the single statement of what each role may do. The database and API tests then
prove the two enforcement layers agree with it.

These tests exist because the matrix is the kind of thing that is edited in a
hurry. A widened role is a security change that looks like a one-line data edit,
and the tests below are what makes it show up as a failing assertion rather than
as a quiet grant.
"""

import pytest

from app.core.permissions import (
    WRITE_ROLES,
    WorkspacePermission,
    WorkspaceRole,
    permissions_for,
    role_allows,
)


def test_every_role_has_an_entry() -> None:
    """A role with no entry would raise a KeyError inside an authorization check.

    Failing closed is better than failing open, but a KeyError surfacing as a
    500 during an authorization decision is neither -- it is an outage. This
    catches a role added to the enum without a matching row in the matrix.
    """
    for role in WorkspaceRole:
        assert permissions_for(role), f"{role} holds no permissions at all"


def test_the_owner_holds_everything() -> None:
    assert permissions_for(WorkspaceRole.OWNER) == frozenset(WorkspacePermission)


def test_only_the_owner_may_delete_a_workspace() -> None:
    """Destroying a workspace destroys every member's work, not only the actor's."""
    holders = {
        role for role in WorkspaceRole if role_allows(role, WorkspacePermission.DELETE_WORKSPACE)
    }

    assert holders == {WorkspaceRole.OWNER}


def test_a_member_cannot_export_the_workspace() -> None:
    """A bulk copy of everyone's data is not ordinary read access.

    Treating export as equivalent to viewing is how an exfiltration path gets
    built by accident, which is why this is asserted rather than left implicit
    in the matrix.
    """
    assert not role_allows(WorkspaceRole.MEMBER, WorkspacePermission.EXPORT_WORKSPACE_DATA)
    assert role_allows(WorkspaceRole.ADMIN, WorkspacePermission.EXPORT_WORKSPACE_DATA)


def test_a_member_may_only_view() -> None:
    """The narrowest role, pinned exactly.

    Asserting equality rather than a set of individual denials: a permission
    added to the enum later is silently granted to nobody by a denial-shaped
    test, and silently granted to `member` by a careless matrix edit. Equality
    catches the second.
    """
    assert permissions_for(WorkspaceRole.MEMBER) == frozenset({WorkspacePermission.VIEW_WORKSPACE})


def test_every_role_may_view() -> None:
    """RBAC narrows what a member may change, never what they may read."""
    for role in WorkspaceRole:
        assert role_allows(role, WorkspacePermission.VIEW_WORKSPACE)


def test_an_admin_cannot_do_everything_an_owner_can() -> None:
    """If these were equal, one of the two roles would be decoration."""
    assert permissions_for(WorkspaceRole.ADMIN) < permissions_for(WorkspaceRole.OWNER)


def test_role_values_match_the_database_check_constraint() -> None:
    """The enum and `ck_workspace_members_role_valid` are the same vocabulary.

    A divergence would surface as a `ValueError` deep inside a membership lookup
    on a live request, rather than here.
    """
    assert {role.value for role in WorkspaceRole} == {"owner", "admin", "member"}


def test_write_roles_are_exactly_those_holding_update() -> None:
    """The SQL predicate and the Python matrix must state the same rule.

    `WRITE_ROLES` is what migration `9f4d2c7a1b83`'s policy predicate mirrors. If
    the matrix grants UPDATE_WORKSPACE to a role missing from this tuple, the API
    would permit an action the database then silently refuses -- a 200 describing
    a change that never happened.
    """
    from_matrix = {
        role for role in WorkspaceRole if role_allows(role, WorkspacePermission.UPDATE_WORKSPACE)
    }

    assert from_matrix == set(WRITE_ROLES)


@pytest.mark.parametrize("role", list(WorkspaceRole))
def test_permissions_are_immutable(role: WorkspaceRole) -> None:
    """A caller cannot widen its own role by mutating what it was handed."""
    with pytest.raises(AttributeError):
        permissions_for(role).add(WorkspacePermission.DELETE_WORKSPACE)  # type: ignore[attr-defined]
