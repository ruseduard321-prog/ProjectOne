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

    def erase(self, connection: psycopg.Connection, workspace_id: uuid.UUID) -> int:
        """Soft-delete every membership row of a workspace except the actor's.

        Returned 0 unconditionally until STEP-11a: soft-deleting *any*
        `workspace_members` row was impossible for every role, because the SELECT
        policy filtered `deleted_at IS NULL` and the row vanished from the
        statement writing it. That policy no longer carries the filter, so this
        works.

        An `UPDATE`, never a `DELETE` -- no table has a DELETE policy and
        `authenticated` holds no DELETE grant, both deliberately
        ([[RLS Policy Pattern]]).

        **The actor's own row is excluded**, and this time for a rule rather than
        a defect: they are necessarily an `owner` to have reached here
        (`DELETE_WORKSPACE`), and the last-owner trigger would refuse the
        statement outright, failing the whole erasure. Excluding it erases
        everything erasable and leaves the workspace with the single owner who
        asked for it -- who can then transfer or leave deliberately, rather than
        having the choice made for them by a bulk operation.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL "
                "AND user_id <> auth.uid()",
                (workspace_id,),
            )

            return cursor.rowcount


class AuditLogStore:
    """A workspace's audit trail: exportable, deliberately **not** erasable.

    Registered so the trail appears in an export -- a user is entitled to a copy
    of the record of what was done in their workspace -- while `erase` is a
    documented no-op.

    **This is the one store that deliberately does not erase, and it is a legal
    exception rather than an oversight.** CLAUDE.md §16 states that audit logs
    are retained on their own schedule, independent of user deletion requests,
    "because audit trails exist precisely to survive the events they record".
    An erasure that wiped the audit log would let anyone with `DELETE_WORKSPACE`
    destroy the evidence of what they did on the way out, which is the single
    outcome an audit log exists to prevent.

    It could not erase even if it wanted to: `audit_log` has no `deleted_at`
    column, no UPDATE policy and no UPDATE grant (migration `a3c07d5e91f4`).
    Returning 0 here is the honest report of that, and the per-store count makes
    the exception **visible in the erasure response** rather than silent -- a
    caller sees `"audit_log": 0` and can ask why, which is exactly the
    transparency CLAUDE.md §16 requires when disclosing a retention exception.
    """

    name = "audit_log"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return the workspace's audit trail.

        Subject to `audit_log_select_same_workspace` like every other read, so
        an export cannot reach another tenant's trail by being handed the wrong
        workspace id.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT created_at, action, actor_id, actor_email, target_id, detail "
                "FROM public.audit_log WHERE workspace_id = %s ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {
                    "created_at": row[0].isoformat(),
                    "action": row[1],
                    "actor_id": str(row[2]),
                    "actor_email": row[3],
                    "target_id": str(row[4]) if row[4] else None,
                    "detail": row[5],
                }
                for row in cursor
            ]

    def erase(self, _connection: psycopg.Connection, _workspace_id: uuid.UUID) -> int:
        """Erase nothing, and report that plainly.

        See the class docstring: this is a documented retention exception, not a
        gap. Returning 0 rather than raising keeps a whole-workspace erasure
        succeeding for every other store -- the alternative would be an erasure
        that fails entirely because one store is legally required to persist.
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
#
# `AuditLogStore` is registered for export but erases nothing, by design -- see
# its docstring. It is in this tuple rather than omitted from it precisely so
# the exception is visible: a store absent from the registry is invisible, while
# one reporting `"audit_log": 0` in every erasure result is a disclosed
# retention exception a reader can question.
REGISTERED_STORES: tuple[ExportableStore, ...] = (WorkspaceMembersStore(), AuditLogStore())
