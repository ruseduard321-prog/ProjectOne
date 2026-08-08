"""Reads and writes `projects` and `assets`.

**Every method here runs over the tenant connection** (`TenantConnectionDep`), so
RLS is what enforces the workspace boundary rather than a `WHERE workspace_id =
...` clause this code could forget. The workspace id still appears in queries,
but as a *filter*, never as the security control: a bug in it narrows results, it
does not widen them past the policy.

That distinction is why this repository takes a connection rather than a DSN. A
repository holding the privileged DSN would look identical at the call site and
have no isolation at all ([[RLS Policy Pattern]] -- "The Two Connections").

## Every query states `deleted_at IS NULL` itself

Neither table's SELECT policy filters liveness, because a SELECT policy that
does makes soft-deleting the table impossible ([[RLS Policy Pattern]]). The
consequence is that liveness is this layer's job on **every** read, and a query
that forgets it returns soft-deleted rows rather than failing -- a silent wrong
answer, which is why it is stated explicitly in each one rather than centralized
in a helper that a future query could bypass.

## No transition logic lives here

`update_status` writes whatever status it is given. Whether that transition was
legal is `ProjectService`'s decision, made before this is called. A repository
that also enforced rules would be a second place the state machine lives, and
two copies of a rule diverge.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import psycopg


@dataclass(frozen=True)
class Project:
    """One project, as stored.

    Frozen because a repository result is a snapshot of what was read. A mutable
    row invites a caller to edit it and expect the database to notice.
    """

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True)
class Asset:
    """One asset belonging to one project."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    kind: str
    storage_path: str | None
    created_by: uuid.UUID
    created_at: datetime


# Stated once rather than repeated in four queries, so a column added to the
# dataclass and forgotten in one of them is impossible. Column order matches
# `_project_from_row` positionally.
_PROJECT_COLUMNS = (
    "id, workspace_id, name, description, status, created_by, created_at, updated_at, version"
)

_ASSET_COLUMNS = "id, workspace_id, project_id, name, kind, storage_path, created_by, created_at"


def _project_from_row(row: tuple[object, ...]) -> Project:
    """Build a `Project` from a row selected with `_PROJECT_COLUMNS`."""
    return Project(
        id=row[0],  # type: ignore[arg-type]
        workspace_id=row[1],  # type: ignore[arg-type]
        name=row[2],  # type: ignore[arg-type]
        description=row[3],  # type: ignore[arg-type]
        status=row[4],  # type: ignore[arg-type]
        created_by=row[5],  # type: ignore[arg-type]
        created_at=row[6],  # type: ignore[arg-type]
        updated_at=row[7],  # type: ignore[arg-type]
        version=row[8],  # type: ignore[arg-type]
    )


def _asset_from_row(row: tuple[object, ...]) -> Asset:
    """Build an `Asset` from a row selected with `_ASSET_COLUMNS`."""
    return Asset(
        id=row[0],  # type: ignore[arg-type]
        workspace_id=row[1],  # type: ignore[arg-type]
        project_id=row[2],  # type: ignore[arg-type]
        name=row[3],  # type: ignore[arg-type]
        kind=row[4],  # type: ignore[arg-type]
        storage_path=row[5],  # type: ignore[arg-type]
        created_by=row[6],  # type: ignore[arg-type]
        created_at=row[7],  # type: ignore[arg-type]
    )


class ProjectRepository:
    """Reaches `projects` and `assets` over an RLS-subject connection."""

    def __init__(self, connection: psycopg.Connection) -> None:
        """Store the tenant-scoped connection every query runs on."""
        self._connection = connection

    # ----------------------------------------------------------- projects --

    def create(
        self,
        workspace_id: uuid.UUID,
        name: str,
        description: str | None,
        status: str,
        created_by: uuid.UUID,
    ) -> Project:
        """Insert a project and return it as stored.

        `status` is supplied by the service rather than defaulted here, so the
        initial state is the state machine's decision and appears in one place.

        Returns:
            The created project, read back so trigger-maintained columns
            (`updated_at`, `version`) and database defaults are the real values
            rather than this layer's guess at them.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO public.projects
                    (workspace_id, name, description, status, created_by)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING {_PROJECT_COLUMNS}
                """,  # noqa: S608 - _PROJECT_COLUMNS is a module constant, not input
                (workspace_id, name, description, status, created_by),
            )
            row = cursor.fetchone()

        # RLS refusing an INSERT raises rather than returning no row, so this is
        # genuinely defensive. Asserting it keeps the return type honest instead
        # of `Project | None` propagating through every caller.
        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Project insert returned no row")

        return _project_from_row(row)

    def get(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        """Return one live project, or None.

        Returns None both when no project exists and when RLS hid it. The two are
        indistinguishable here by design -- a repository that could tell them
        apart would be one capable of seeing across the tenant boundary.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_PROJECT_COLUMNS}
                FROM public.projects
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """,  # noqa: S608 - _PROJECT_COLUMNS is a module constant, not input
                (project_id, workspace_id),
            )
            row = cursor.fetchone()

        return None if row is None else _project_from_row(row)

    def list_for_workspace(self, workspace_id: uuid.UUID) -> tuple[Project, ...]:
        """Return every live project in a workspace, newest first.

        Ordered by `created_at DESC, id DESC`: the timestamp is what a user
        expects to sort by, and `id` breaks ties so two projects created in the
        same transaction have a stable order rather than one PostgreSQL is free
        to vary between calls.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_PROJECT_COLUMNS}
                FROM public.projects
                WHERE workspace_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                """,  # noqa: S608 - _PROJECT_COLUMNS is a module constant, not input
                (workspace_id,),
            )
            rows = cursor.fetchall()

        return tuple(_project_from_row(row) for row in rows)

    def update_status(
        self, workspace_id: uuid.UUID, project_id: uuid.UUID, status: str
    ) -> Project | None:
        """Write a project's status, returning the updated row.

        Writes whatever it is given: legality is decided by `ProjectService`
        before this is called (see the module docstring).

        Returns:
            The updated project, or None when no live row matched -- which
            covers both "no such project" and "RLS hid it".
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE public.projects
                SET status = %s
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                RETURNING {_PROJECT_COLUMNS}
                """,  # noqa: S608 - _PROJECT_COLUMNS is a module constant, not input
                (status, project_id, workspace_id),
            )
            row = cursor.fetchone()

        return None if row is None else _project_from_row(row)

    def rename(
        self,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        description: str | None,
    ) -> Project | None:
        """Update a project's name and description.

        Returns:
            The updated project, or None when no live row matched.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE public.projects
                SET name = %s, description = %s
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                RETURNING {_PROJECT_COLUMNS}
                """,  # noqa: S608 - _PROJECT_COLUMNS is a module constant, not input
                (name, description, project_id, workspace_id),
            )
            row = cursor.fetchone()

        return None if row is None else _project_from_row(row)

    def soft_delete(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        """Soft-delete a project.

        An `UPDATE`, never a `DELETE` -- neither table has a DELETE policy and
        `authenticated` holds no DELETE grant, both deliberately.

        This is the operation that would be impossible if the SELECT policy
        filtered `deleted_at IS NULL`, which is why it does not
        ([[RLS Policy Pattern]]). `test_soft_deleting_a_project_succeeds` guards
        it against recurrence.

        Returns:
            True when a project was removed, False when there was none to
            remove. RLS makes "not yours" and "not there" identical here, which
            is correct.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.projects
                SET deleted_at = now()
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """,
                (project_id, workspace_id),
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------- assets --

    def add_asset(
        self,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        kind: str,
        storage_path: str | None,
        created_by: uuid.UUID,
    ) -> Asset:
        """Attach an asset to a project.

        The composite foreign key means an asset naming a project in another
        workspace is refused by the database, not merely by this query's
        `workspace_id` filter -- see the migration's docstring.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO public.assets
                    (workspace_id, project_id, name, kind, storage_path, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING {_ASSET_COLUMNS}
                """,  # noqa: S608 - _ASSET_COLUMNS is a module constant, not input
                (workspace_id, project_id, name, kind, storage_path, created_by),
            )
            row = cursor.fetchone()

        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Asset insert returned no row")

        return _asset_from_row(row)

    def list_assets(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> tuple[Asset, ...]:
        """Return every live asset attached to a project, oldest first.

        Ascending rather than descending, unlike the project listing: assets
        accumulate as a project progresses, so their creation order is the order
        the work happened in and is the useful one to read.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_ASSET_COLUMNS}
                FROM public.assets
                WHERE project_id = %s AND workspace_id = %s AND deleted_at IS NULL
                ORDER BY created_at, id
                """,  # noqa: S608 - _ASSET_COLUMNS is a module constant, not input
                (project_id, workspace_id),
            )
            rows = cursor.fetchall()

        return tuple(_asset_from_row(row) for row in rows)

    def soft_delete_asset(self, workspace_id: uuid.UUID, asset_id: uuid.UUID) -> bool:
        """Soft-delete one asset.

        Returns:
            True when an asset was removed, False when there was none.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.assets
                SET deleted_at = now()
                WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """,
                (asset_id, workspace_id),
            )
            return cursor.rowcount > 0
