"""Export and erasure of workspace-owned data.

Structural only. STEP-11's scope is the *mechanics*; the UI that drives them is
a later step. This exists now rather than later because retrofitting deletion is
expensive (CLAUDE.md §16): the shape a feature stores data in decides whether it
can be exported and erased at all, and every table added from here on will be
added against this contract instead of alongside it.

## Why a registry rather than a hardcoded query

Deletion has to be **end-to-end** (CLAUDE.md §16): the primary database, the AI
Memory System, analytics event logs, and search/cache layers. None of the latter
three exist yet. A service that hardcoded today's three tables would need
rewriting for each one, and -- far worse -- would silently keep succeeding while
missing them, reporting a completed erasure that erased two thirds of the data.

`ExportableStore` is therefore the contract a store registers under. A feature
that persists workspace data registers its store here, which is the Definition
of Done obligation CLAUDE.md §16 places on it. A store that is never registered
is visibly absent from this module rather than invisibly absent from a query.

## Erasure is a soft delete, and that is not a compromise

No table has a DELETE policy and `authenticated` holds no DELETE grant, both
deliberately (RLS Policy Pattern). Erasure sets `deleted_at`, which every RLS
policy filters on, so an erased row stops being reachable by any request at the
moment it is marked. What this does *not* do is remove the bytes, and the gap is
stated rather than glossed:

- **Reachability ends immediately.** No policy matches a soft-deleted row.
- **Hard removal is a separate, later concern** -- a scheduled purge running on
  the audited service path, with the 30-day SLA CLAUDE.md §16 sets. It is not in
  this step's scope, and this module deliberately does not pretend to it.
- **Backups age out; they are not purged on request.** A documented, bounded
  exception (CLAUDE.md §16).

Claiming a soft delete is a full erasure would be the kind of confident-sounding
falsehood this project treats as worse than a gap.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg

from app.core.permissions import WorkspacePermission
from app.services.authorization_service import AuthorizationService

# One exported record. `Any` for the values because each store defines its own
# shape, and an export must carry whatever a store actually holds -- narrowing
# it would mean every new store forces a change here, which is precisely the
# coupling the registry exists to avoid.
ExportedRecord = dict[str, Any]


class ExportableStore(Protocol):
    """A store holding workspace-owned data that must be exportable and erasable.

    Implemented by every store that persists workspace data. The two methods are
    a pair on purpose: a store that can be exported but not erased is a GDPR
    liability, and one that can be erased but not exported takes a user's data
    with no way for them to retain their own copy.
    """

    #: Stable identifier for this store in an export document. Stable because a
    #: user's exported archive should stay comparable across versions.
    name: str

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return every record this store holds for a workspace."""
        ...

    def erase(self, connection: psycopg.Connection, workspace_id: uuid.UUID) -> int:
        """Soft-delete this store's records for a workspace, returning the count."""
        ...


@dataclass(frozen=True)
class WorkspaceExport:
    """Everything a workspace holds, as one document.

    Frozen: an export is a snapshot of what was read, and a mutable one invites
    a caller to edit the record of what a user was actually given.
    """

    workspace_id: uuid.UUID
    stores: dict[str, list[ExportedRecord]]


@dataclass(frozen=True)
class ErasureResult:
    """What an erasure actually did, per store.

    Returns per-store counts rather than a boolean because "deletion succeeded"
    is not a useful claim to make about a multi-store erasure -- the user, and
    any later audit, needs to know which stores were touched and how much each
    one held. A store missing from this mapping is a store that was never
    registered, which is exactly the failure this shape makes visible.
    """

    workspace_id: uuid.UUID
    erased: dict[str, int]


class WorkspaceMembersStore:
    """The membership rows of a workspace.

    The first registered store, and the reference implementation for the ones
    that follow. It runs entirely over the tenant connection, so RLS is what
    decides which rows it can reach -- an export cannot become a cross-tenant
    read path by being handed the wrong workspace id.
    """

    name = "workspace_members"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return the live membership rows of a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, role, created_at FROM public.workspace_members "
                "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {"user_id": str(row[0]), "role": row[1], "created_at": row[2].isoformat()}
                for row in cursor
            ]

    def erase(self, _connection: psycopg.Connection, _workspace_id: uuid.UUID) -> int:
        """Report that membership rows cannot yet be erased, without pretending.

        > **This store is not erasable over the request path today, and the
        > blocker is STEP-09's SELECT policy, not authorization.**

        Erasure would be an UPDATE setting `deleted_at` -- there is no DELETE
        policy anywhere by design (RLS Policy Pattern). Every such statement is
        rejected, for *any* role and *any* row, because
        `workspace_members_select_same_workspace` filters `deleted_at IS NULL`:
        the soft-deleted row becomes invisible to the same statement writing it
        and PostgreSQL refuses the update. Reproduced against a live database
        during STEP-11 validation for a member erasing their own row, for a
        member erasing another's, and for an **owner** erasing a member's --
        all three fail identically.

        Returning 0 rather than attempting the UPDATE is the honest option, and
        the alternatives were rejected deliberately:

        - **Attempting it** raises `InsufficientPrivilege` on every call, so the
          endpoint is a guaranteed 500 rather than a working feature.
        - **Running it over the privileged connection** would work, and would
          make the erasure path the one component in the system exempt from the
          isolation it enforces (CLAUDE.md §16 -- admin tooling does not bypass
          RLS). That is precisely the bypass STEP-09 exists to prevent.
        - **Changing the SELECT policy** is the actual fix, and it is a Critical
          multi-tenancy decision belonging to its own step, not something an
          RBAC step folds in silently (CLAUDE.md §21/§29).

        The count is what makes this visible rather than hidden: a caller sees
        `{"workspace_members": 0}` and knows nothing was erased, instead of a
        success message over data that is still there. `ErasureResult` reports
        per-store counts for exactly this reason.
        """
        return 0


class DataOwnershipService:
    """Exports and erases everything a workspace owns."""

    def __init__(
        self,
        connection: psycopg.Connection,
        authorization: AuthorizationService,
        stores: tuple[ExportableStore, ...],
    ) -> None:
        """Store the tenant connection, the authorization gate, and the registry."""
        self._connection = connection
        self._authorization = authorization
        self._stores = stores

    def export_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceExport:
        """Return every record a workspace holds, if the caller may export it.

        `EXPORT_WORKSPACE_DATA` rather than `VIEW_WORKSPACE`: a bulk copy of
        every member's data is a materially different act from reading the
        screens one has access to, and `member` deliberately does not hold it
        (see `app/core/permissions.py`).

        Raises:
            AuthorizationError: The caller's role does not permit exporting.
            WorkspaceAccessError: The caller is not a live member.
        """
        self._authorization.require(
            workspace_id, user_id, WorkspacePermission.EXPORT_WORKSPACE_DATA
        )

        return WorkspaceExport(
            workspace_id=workspace_id,
            stores={
                store.name: store.export(self._connection, workspace_id) for store in self._stores
            },
        )

    def erase_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> ErasureResult:
        """Soft-delete everything a workspace owns, if the caller may delete it.

        `DELETE_WORKSPACE` is owner-only. Destroying a workspace destroys every
        member's work, not only the actor's, so it sits with the single role that
        is also `workspaces.owner_id`.

        Runs inside one transaction: a partial erasure -- some stores cleared,
        others not -- is the worst outcome available here, because it looks like
        a completed deletion to the user while leaving data reachable.

        Raises:
            AuthorizationError: The caller's role does not permit deletion.
            WorkspaceAccessError: The caller is not a live member.
        """
        self._authorization.require(workspace_id, user_id, WorkspacePermission.DELETE_WORKSPACE)

        with self._connection.transaction():
            erased = {
                store.name: store.erase(self._connection, workspace_id) for store in self._stores
            }

        return ErasureResult(workspace_id=workspace_id, erased=erased)


#: Every store holding workspace-owned data.
#
# A feature that persists workspace data adds itself here, and that registration
# is part of its Definition of Done (CLAUDE.md §16 -- a feature that writes user
# data anywhere is responsible for registering that store with the deletion
# process). The tuple is the checklist: a store absent from it is absent from
# every export and every erasure.
REGISTERED_STORES: tuple[ExportableStore, ...] = (WorkspaceMembersStore(),)
