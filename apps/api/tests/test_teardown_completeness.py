"""The shared teardown list is complete, asserted against the database's own catalog.

**Why this test exists.** `conftest._WORKSPACE_DEPENDANTS` is a hand-maintained
list of every table holding a foreign key to `public.workspaces`, and teardown
deletes from it before deleting workspaces. Every one of those foreign keys is
`ON DELETE RESTRICT` by deliberate design -- spend history, budgets, kill
switches, provider keys and the audit trail must not be cascaded away with the
workspace they describe.

That design has a maintenance cost, and it has already been paid once: STEP-18
added three tables referencing `workspaces` without updating the list, and CI
failed with `ForeignKeyViolation: fk_ai_spend_records_workspace_id_workspaces`.
The failure surfaced in teardown, so it appeared in whichever database test ran
last rather than in anything related to spend -- which is a slow way to find a
one-line omission. STEP-17's `provider_credentials` had the same gap and had
simply not been triggered yet.

**What this asserts, and why it is a catalog query rather than a second list.**
Restating the tables here would just create a second list to forget to update.
Instead it asks PostgreSQL which tables reference `workspaces` and requires the
teardown list to match exactly. Adding a table without updating teardown fails
*here*, naming the table, instead of failing later somewhere unrelated.

The match is exact in both directions on purpose: a missing entry breaks
teardown, and a stale entry (a table since dropped) would make teardown fail
with `UndefinedTable`.
"""

from __future__ import annotations

import psycopg

from tests.conftest import _WORKSPACE_DEPENDANTS

# Deleted explicitly by name in `admin_connection`, after every dependant above
# it has been cleared. Excluded from the comparison because they are the targets
# of the teardown order, not entries in the dependants list.
_DELETED_SEPARATELY = frozenset({"workspaces", "users"})


def _tables_referencing_workspaces(connection: psycopg.Connection) -> set[str]:
    """Return every table in `public` holding a foreign key to `public.workspaces`.

    Read from the catalog rather than from the migrations, so the answer reflects
    the schema that actually exists at head.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT source.relname
            FROM pg_constraint constraint_
            JOIN pg_class source ON source.oid = constraint_.conrelid
            JOIN pg_class target ON target.oid = constraint_.confrelid
            JOIN pg_namespace source_ns ON source_ns.oid = source.relnamespace
            JOIN pg_namespace target_ns ON target_ns.oid = target.relnamespace
            WHERE constraint_.contype = 'f'
              AND target.relname = 'workspaces'
              AND target_ns.nspname = 'public'
              AND source_ns.nspname = 'public'
            """
        )
        return {row[0] for row in cursor.fetchall()}


def test_teardown_covers_every_table_referencing_workspaces(
    migrated_database: str,
) -> None:
    """Every table with a foreign key to `workspaces` is cleared before it.

    The failure message names the specific tables, because the whole point is
    that whoever adds the next one learns exactly what to do from the failure.
    """
    with psycopg.connect(migrated_database) as connection:
        referencing = _tables_referencing_workspaces(connection)

    listed = set(_WORKSPACE_DEPENDANTS) | _DELETED_SEPARATELY

    missing = referencing - listed
    assert not missing, (
        f"These tables reference public.workspaces but are not cleared during teardown: "
        f"{sorted(missing)}. Add them to `_WORKSPACE_DEPENDANTS` in tests/conftest.py, "
        f"or every database test that seeds a workspace will fail teardown with a "
        f"ForeignKeyViolation."
    )

    stale = set(_WORKSPACE_DEPENDANTS) - referencing
    assert not stale, (
        f"`_WORKSPACE_DEPENDANTS` lists tables that no longer reference public.workspaces: "
        f"{sorted(stale)}. Remove them — teardown would fail with UndefinedTable if they "
        f"have been dropped."
    )


def test_teardown_list_matches_the_restrict_design(migrated_database: str) -> None:
    """Every workspace dependant is RESTRICT, which is why teardown must be explicit.

    If one of these ever became `ON DELETE CASCADE`, clearing it by hand would be
    redundant rather than required — and, more importantly, the production
    guarantee that an audit trail or spend ledger cannot be cascaded away with
    its workspace would have been silently dropped. That is worth failing on.
    """
    with psycopg.connect(migrated_database) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT source.relname, constraint_.confdeltype
            FROM pg_constraint constraint_
            JOIN pg_class source ON source.oid = constraint_.conrelid
            JOIN pg_class target ON target.oid = constraint_.confrelid
            JOIN pg_namespace source_ns ON source_ns.oid = source.relnamespace
            WHERE constraint_.contype = 'f'
              AND target.relname = 'workspaces'
              AND source_ns.nspname = 'public'
              AND source.relname <> 'workspace_members'
            """
        )
        rules: dict[str, str] = {row[0]: row[1] for row in cursor.fetchall()}

    # 'r' is RESTRICT in pg_constraint.confdeltype; 'c' would be CASCADE.
    not_restrict = {table: rule for table, rule in rules.items() if rule != "r"}

    assert not not_restrict, (
        f"These workspace foreign keys are no longer ON DELETE RESTRICT: {not_restrict}. "
        f"Spend history, budgets, kill switches, provider keys and the audit trail are "
        f"deliberately RESTRICT so they cannot be cascaded away with the workspace they "
        f"describe (CLAUDE.md §16). If this changed intentionally, that is an ADR."
    )
