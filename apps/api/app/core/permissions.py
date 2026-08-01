"""The role model: what `owner`, `admin` and `member` are actually allowed to do.

`workspace_members.role` has existed since STEP-08 constrained to three values,
and until this module nothing read it. Three names with no semantics are not an
authorization model -- they are a vocabulary that drifts, with each endpoint
inventing its own idea of what "admin" means.

**This module is the single definition.** The matrix below is the whole model;
the RLS policies (migration `9f4d2c7a1b83`) and the API's permission dependency
both enforce *this*, and neither may enforce anything it does not state.

Why an enum and a matrix rather than `if role == "owner"` at each call site:
a scattered rule cannot be reviewed, and a reader cannot answer "what can an
admin do" without reading every route. Here the answer is one table.
"""

from enum import StrEnum


class WorkspaceRole(StrEnum):
    """A member's role within one workspace.

    The values match the `ck_workspace_members_role_valid` check constraint
    exactly. `StrEnum` so a value compares equal to the string the database
    stores, which keeps the boundary between the two layers free of conversions
    that could silently disagree.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class WorkspacePermission(StrEnum):
    """A distinct capability inside a workspace.

    Deliberately *actions*, not endpoints. A permission named after a route
    (`can_call_patch_workspace`) has to be reinvented the moment a second route
    performs the same action, and the two copies then drift.
    """

    #: Read the workspace and its members. Every live member holds this -- RLS
    #: already enforces it, and this exists so the matrix is complete rather
    #: than silent about the most common action.
    VIEW_WORKSPACE = "workspace:view"

    #: Rename the workspace or change its settings.
    UPDATE_WORKSPACE = "workspace:update"

    #: Add a member, remove one, or change someone's role.
    MANAGE_MEMBERS = "workspace:manage_members"

    #: Export every record the workspace holds (Privacy and Data Protection --
    #: users retain ownership of their data and can export it).
    EXPORT_WORKSPACE_DATA = "workspace:export"

    #: Soft-delete the workspace itself. Owner only, and separate from
    #: UPDATE_WORKSPACE precisely because it is not a reversible edit.
    DELETE_WORKSPACE = "workspace:delete"

    #: Remove *another* member from the workspace. Distinct from MANAGE_MEMBERS
    #: because removal is ranked: holding this does not mean holding it over
    #: everyone (see `may_remove`). Owner and admin hold it; who each may
    #: actually remove differs.
    REMOVE_MEMBER = "workspace:remove_member"

    #: Leave the workspace. Every role holds it -- nobody can be kept in a
    #: workspace against their will -- but the last owner is still blocked, by
    #: the database rather than by this matrix (see `may_remove`).
    LEAVE_WORKSPACE = "workspace:leave"

    #: Hand ownership to another member. Owner only: it is the one act that
    #: changes who holds DELETE_WORKSPACE, so anyone else holding it could
    #: manufacture themselves an owner.
    TRANSFER_OWNERSHIP = "workspace:transfer_ownership"


# The role model, stated once.
#
# Read as: an owner may do anything; an admin runs the workspace day to day but
# cannot destroy it or take it over; a member participates and reads.
#
# Two lines carry the most weight and are worth naming explicitly:
#
# - **`admin` does not hold DELETE_WORKSPACE.** Deleting a workspace destroys
#   every member's work, not only the actor's. Concentrating that in the single
#   role that is also the `workspaces.owner_id` foreign key keeps "who can
#   destroy this" answerable by looking at one column.
# - **`admin` holds EXPORT_WORKSPACE_DATA but `member` does not.** An export is
#   a bulk copy of everyone's data in the workspace, which is a materially
#   different act from reading the screens one has access to. Treating it as
#   ordinary read access is how a data-exfiltration path gets built by accident.
_ROLE_PERMISSIONS: dict[WorkspaceRole, frozenset[WorkspacePermission]] = {
    WorkspaceRole.OWNER: frozenset(WorkspacePermission),
    WorkspaceRole.ADMIN: frozenset(
        {
            WorkspacePermission.VIEW_WORKSPACE,
            WorkspacePermission.UPDATE_WORKSPACE,
            WorkspacePermission.MANAGE_MEMBERS,
            WorkspacePermission.EXPORT_WORKSPACE_DATA,
            WorkspacePermission.REMOVE_MEMBER,
            WorkspacePermission.LEAVE_WORKSPACE,
        }
    ),
    WorkspaceRole.MEMBER: frozenset(
        {
            WorkspacePermission.VIEW_WORKSPACE,
            WorkspacePermission.LEAVE_WORKSPACE,
        }
    ),
}

# Roles whose members may write to the workspace row, in the order the database
# stores them. Kept here rather than in the migration so the SQL predicate and
# the Python check are derived from the same source instead of being two lists
# someone has to remember to edit together.
WRITE_ROLES: tuple[WorkspaceRole, ...] = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


# Removal rights are **ranked**, which a flat permission set cannot express:
# `REMOVE_MEMBER` says an admin may remove someone, not that they may remove
# *anyone*. Rules 2 and 4 (owner removes admins and members; admin removes
# members only) are a comparison between the actor's role and the target's.
#
# Higher number outranks lower. The values themselves are meaningless -- only
# the ordering is -- so they are never stored or serialized.
_REMOVAL_RANK: dict[WorkspaceRole, int] = {
    WorkspaceRole.OWNER: 3,
    WorkspaceRole.ADMIN: 2,
    WorkspaceRole.MEMBER: 1,
}


def permissions_for(role: WorkspaceRole) -> frozenset[WorkspacePermission]:
    """Return everything a role may do."""
    return _ROLE_PERMISSIONS[role]


def may_remove(actor: WorkspaceRole, target: WorkspaceRole) -> bool:
    """Return whether `actor` may remove a member holding `target`.

    Encodes the owner's rules 2 and 4 as a strict rank comparison:

    - An **owner** outranks admins and members, so removes both.
    - An **admin** outranks members only -- never another admin, never an owner.
      Rule 4 states this by omission; the strict `>` states it outright.
    - A **member** outranks nobody and can remove no one.

    Strict rather than `>=` deliberately: `>=` would let an admin remove another
    admin and an owner remove a co-owner, neither of which the rules permit.
    Removing *oneself* is leaving, a separate act with its own permission --
    routing it through this function is what would quietly re-introduce co-owner
    removal.

    This is the application-layer copy of the `workspace_members_update_privileged`
    USING clause. The policy remains authoritative ([[Authorization Model]]);
    this exists so the API can answer 403 rather than silently affecting no rows.
    """
    return _REMOVAL_RANK[actor] > _REMOVAL_RANK[target]


def role_allows(role: WorkspaceRole, permission: WorkspacePermission) -> bool:
    """Return whether a role holds a permission."""
    return permission in _ROLE_PERMISSIONS[role]
