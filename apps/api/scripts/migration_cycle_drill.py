"""FA-02 — prove the migrations reverse, by executing the full cycle.

The STEP-25 audit confirmed by inspection that all 18 migrations have non-empty
`downgrade()` bodies and that the revision history is strictly linear. Neither
fact proves a downgrade *works*: a dropped object another migration depends on,
or an ordering error, fails only at runtime. No environment exercised the
reverse direction — CI applies migrations forward to set the schema up and stops
there — which is why the finding stayed High while FA-01 was reduced.

This drill closes that gap by running the cycle:

    upgrade head -> downgrade base -> upgrade head

and then asserting the twice-migrated schema is *identical* to the once-migrated
one. The comparison is the point. A downgrade that silently leaves a table
behind, or an upgrade that rebuilds a column with a different type, completes
without error and corrupts the next deployment — so "both commands exited zero"
is not the claim worth making.

**Disposable databases only.** This drops every object in the schema. It refuses
to run against anything that looks like a managed or shared host, and CI points
it at a per-run throwaway container. It must never be aimed at the shared
Supabase development database.

Run it directly:

    PROJECTONE_TEST_DATABASE_URL=postgresql://... python scripts/migration_cycle_drill.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

import psycopg

# Hosts that are never disposable. A drill that drops every object in the schema
# has no business connecting to a managed project, and a typo in an environment
# variable is exactly how that happens.
_FORBIDDEN_HOST_FRAGMENTS = ("supabase.co", "supabase.in", "rds.amazonaws.com", "azure.com")

#: The schema facts compared before and after the cycle.
#:
#: Chosen so a downgrade that leaves an object behind, or an upgrade that
#: rebuilds one differently, shows up as a difference rather than as silence.
#: Column types and nullability catch a rebuilt column; constraints catch a lost
#: foreign key; RLS flags catch the security property that matters most here,
#: because a table that comes back without `FORCE` is a tenant-isolation defect
#: that no forward-only test would notice (CLAUDE.md §16).
_SCHEMA_QUERIES: dict[str, str] = {
    "tables": """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """,
    "columns": """
        SELECT table_name, column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, column_name
    """,
    "constraints": """
        SELECT tc.table_name, tc.constraint_name, tc.constraint_type
        FROM information_schema.table_constraints AS tc
        WHERE tc.table_schema = 'public'
          -- Names generated per-run would differ between the two passes without
          -- indicating a real difference; every constraint this schema declares
          -- is explicitly named.
        ORDER BY tc.table_name, tc.constraint_name, tc.constraint_type
    """,
    "indexes": """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """,
    "rls": """
        SELECT relname, relrowsecurity, relforcerowsecurity
        FROM pg_class
        JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
        WHERE pg_namespace.nspname = 'public' AND relkind = 'r'
        ORDER BY relname
    """,
    "policies": """
        SELECT tablename, policyname, cmd, qual, with_check
        FROM pg_policies
        WHERE schemaname = 'public'
        ORDER BY tablename, policyname, cmd
    """,
    "functions": """
        SELECT routine_name, data_type
        FROM information_schema.routines
        WHERE routine_schema = 'public'
        ORDER BY routine_name
    """,
}


def _require_disposable(url: str) -> None:
    """Refuse to run against anything that is not obviously throwaway."""
    lowered = url.lower()

    for fragment in _FORBIDDEN_HOST_FRAGMENTS:
        if fragment in lowered:
            raise SystemExit(
                f"refusing to run the migration drill against '{fragment}'. "
                "This drops every object in the schema and is for disposable "
                "databases only."
            )


def _alembic_config(url: str) -> Any:  # noqa: ANN401 - alembic's Config, imported lazily
    """Build an Alembic config pointed at `url` rather than at the environment.

    Overriding the URL here is what stops `migrations/env.py` resolving
    `DATABASE_URL` and migrating whatever that happens to name.
    """
    from alembic.config import Config

    api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    config = Config(os.path.join(api_root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(api_root, "migrations"))
    config.set_main_option(
        "sqlalchemy.url", url.replace("postgresql://", "postgresql+psycopg://", 1)
    )

    return config


def _capture_schema(url: str) -> dict[str, list[tuple[Any, ...]]]:
    """Return the schema facts this drill compares."""
    captured: dict[str, list[tuple[Any, ...]]] = {}

    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        for name, query in _SCHEMA_QUERIES.items():
            cursor.execute(query)
            captured[name] = [tuple(row) for row in cursor.fetchall()]

    return captured


def _report_difference(
    name: str,
    before: list[tuple[Any, ...]],
    after: list[tuple[Any, ...]],
) -> list[str]:
    """Describe what changed, so a failure names the object rather than a count."""
    missing = [row for row in before if row not in after]
    added = [row for row in after if row not in before]

    lines: list[str] = []

    for row in missing[:20]:
        lines.append(f"  {name}: MISSING after the cycle: {row}")
    for row in added[:20]:
        lines.append(f"  {name}: UNEXPECTEDLY ADDED by the cycle: {row}")

    return lines


def main() -> int:
    """Execute the cycle and compare the schema either side of it."""
    url = os.environ.get("PROJECTONE_TEST_DATABASE_URL")

    if not url:
        print(
            "PROJECTONE_TEST_DATABASE_URL is not set. This drill needs a "
            "disposable PostgreSQL database — never a shared or managed one.",
            file=sys.stderr,
        )
        return 2

    _require_disposable(url)

    from alembic import command

    config = _alembic_config(url)

    print("==> upgrade head (first pass)")
    command.upgrade(config, "head")
    before = _capture_schema(url)
    print(f"    captured {sum(len(rows) for rows in before.values())} schema facts")

    print("==> downgrade base")
    # The direction nothing has ever exercised. A failure here is the finding,
    # so it is reported as one rather than as a raw traceback: job logs on this
    # repository need admin rights to download, so an unexplained stack trace
    # is close to no diagnostic at all for whoever has to fix it.
    try:
        command.downgrade(config, "base")
    except Exception as error:
        with psycopg.connect(url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            stuck = [row[0] for row in cursor.fetchall()]

        print("\n" + "=" * 68, file=sys.stderr)
        print("FA-02: the downgrade path is BROKEN. This is the finding.", file=sys.stderr)
        print("=" * 68, file=sys.stderr)
        print(f"  stopped at revision: {stuck or '<none>'}", file=sys.stderr)
        print(f"  {type(error).__name__}: {error}", file=sys.stderr)
        print(
            "\n  A downgrade body can be non-empty and still fail at runtime — "
            "which is exactly\n  what static inspection could not tell us, and "
            "why this drill exists.",
            file=sys.stderr,
        )
        return 1

    remaining = _capture_schema(url)["tables"]
    # `alembic_version` is Alembic's own bookkeeping table and correctly
    # survives a downgrade to base; anything else surviving is a migration that
    # did not clean up after itself.
    leftovers = [row for row in remaining if row[0] != "alembic_version"]
    if leftovers:
        print("downgrade base left objects behind:", file=sys.stderr)
        for row in leftovers:
            print(f"  {row[0]}", file=sys.stderr)
        return 1
    print("    schema is empty, as a downgrade to base must leave it")

    print("==> upgrade head (second pass)")
    command.upgrade(config, "head")
    after = _capture_schema(url)

    print("==> comparing the twice-migrated schema against the once-migrated one")
    differences: list[str] = []
    for name in _SCHEMA_QUERIES:
        if before[name] != after[name]:
            differences.extend(_report_difference(name, before[name], after[name]))

    if differences:
        print("the migration cycle is NOT idempotent:", file=sys.stderr)
        for line in differences:
            print(line, file=sys.stderr)
        return 1

    counts = ", ".join(f"{name}={len(rows)}" for name, rows in sorted(before.items()))
    print(f"    identical: {counts}")
    print("\nFA-02: migrations reverse and re-apply cleanly.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
