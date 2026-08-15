"""FA-03 — prove ProjectOne can restore from a backup, by executing the drill.

The STEP-25 audit recorded this as the single largest unproven guarantee in the
Foundation: [[Backup and Disaster Recovery]] describes a strategy, no restore had
ever been performed, and RPO/RTO were stated as things that *should* be defined
rather than as values. Nothing here is provable by reading — either a dump can be
restored into an empty database and come back correct, or it cannot.

The drill:

1. migrates a disposable database to head,
2. seeds representative data across **two workspaces**, so the restore is
   verifiable as tenant-correct rather than merely non-empty,
3. takes a backup with `pg_dump`,
4. restores into a **separate, empty database** — restoring over the source
   proves far less, because a no-op would pass,
5. verifies schema *and* per-workspace data match the source,
6. reports measured backup and restore durations.

**Disposable databases only.** This creates and drops databases. It refuses to
run against a managed or shared host, and CI points it at a per-run throwaway
container. It must never target the shared Supabase development database.

Run it directly:

    PROJECTONE_TEST_DATABASE_URL=postgresql://... python scripts/backup_restore_drill.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from typing import IO, Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
from migration_cycle_drill import annotate

# Hosts that are never disposable — the same guard the migration drill applies.
_FORBIDDEN_HOST_FRAGMENTS = ("supabase.co", "supabase.in", "rds.amazonaws.com", "azure.com")

#: The database the dump is restored into. Created empty by this script and
#: dropped afterwards, so a rerun does not depend on the previous one's cleanup.
_RESTORE_DB_PREFIX = "projectone_restore_drill"


def _require_disposable(url: str) -> None:
    """Refuse to run against anything that is not obviously throwaway."""
    lowered = url.lower()

    for fragment in _FORBIDDEN_HOST_FRAGMENTS:
        if fragment in lowered:
            raise SystemExit(
                f"refusing to run the backup/restore drill against '{fragment}'. "
                "This creates and drops databases and is for disposable "
                "databases only."
            )


def _with_database(url: str, database: str) -> str:
    """Return `url` pointed at a different database on the same server."""
    parts = urlsplit(url)

    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _require_tooling() -> None:
    """Fail early and clearly when `pg_dump`/`psql` are missing.

    A drill that cannot find its tools must say so rather than fail obscurely
    three steps later — the audit environment had exactly this gap.
    """
    missing = [name for name in ("pg_dump", "psql") if shutil.which(name) is None]

    if missing:
        raise SystemExit(
            f"missing required tooling: {', '.join(missing)}. "
            "The restore drill needs the PostgreSQL client binaries."
        )


def _seed(url: str) -> dict[str, Any]:
    """Insert representative data across two workspaces.

    Two, deliberately. A single-workspace restore proves the rows came back; it
    cannot show that they came back *attached to the right tenant*, which is the
    property that matters for a multi-tenant product (CLAUDE.md §16).
    """
    seeded: dict[str, Any] = {"workspaces": [], "users": []}

    with psycopg.connect(url, autocommit=True) as connection, connection.cursor() as cursor:
        for index in (1, 2):
            user_id = uuid.uuid4()
            workspace_id = uuid.uuid4()
            email = f"drill-user-{index}-{user_id.hex[:8]}@example.test"
            name = f"Restore Drill Workspace {index}"

            cursor.execute(
                "INSERT INTO users (id, email, display_name) VALUES (%s, %s, %s)",
                (user_id, email, f"Drill User {index}"),
            )
            cursor.execute(
                "INSERT INTO workspaces (id, name, owner_id) VALUES (%s, %s, %s)",
                (workspace_id, name, user_id),
            )
            cursor.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (%s, %s, %s)",
                (workspace_id, user_id, "owner"),
            )

            # Per-workspace project rows, with distinct counts so a restore that
            # mixes tenants shows up as a count mismatch rather than passing.
            for project_index in range(index + 1):
                cursor.execute(
                    "INSERT INTO projects (workspace_id, name) VALUES (%s, %s)",
                    (workspace_id, f"Workspace {index} Project {project_index}"),
                )

            seeded["workspaces"].append(
                {
                    "id": str(workspace_id),
                    "name": name,
                    "owner_id": str(user_id),
                    "projects": index + 1,
                }
            )
            seeded["users"].append({"id": str(user_id), "email": email})

    return seeded


def _capture_verification(url: str) -> dict[str, Any]:
    """Capture the facts compared either side of the restore.

    Schema *and* data. A restore that rebuilds the tables and loses the rows is
    a failed restore; so is one that returns the rows without the RLS that
    protects them, which is why the security flags are captured here too.
    """
    captured: dict[str, Any] = {}

    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
        captured["tables"] = [row[0] for row in cursor.fetchall()]

        cursor.execute(
            "SELECT table_name, constraint_name, constraint_type "
            "FROM information_schema.table_constraints WHERE table_schema = 'public' "
            "ORDER BY table_name, constraint_name, constraint_type"
        )
        captured["constraints"] = [tuple(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace "
            "WHERE pg_namespace.nspname = 'public' AND relkind = 'r' ORDER BY relname"
        )
        captured["rls"] = [tuple(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT tablename, policyname, cmd FROM pg_policies "
            "WHERE schemaname = 'public' ORDER BY tablename, policyname, cmd"
        )
        captured["policies"] = [tuple(row) for row in cursor.fetchall()]

        # The migration pointer. A restore that loses it leaves a database no
        # future migration can safely touch.
        cursor.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
        captured["alembic_version"] = [row[0] for row in cursor.fetchall()]

        # Per-workspace data, which is what makes this a restore verification
        # rather than a schema comparison.
        cursor.execute(
            "SELECT w.id::text, w.name, w.owner_id::text, "
            "       (SELECT count(*) FROM projects p WHERE p.workspace_id = w.id) "
            "FROM workspaces w ORDER BY w.name"
        )
        captured["workspace_rows"] = [tuple(row) for row in cursor.fetchall()]

        cursor.execute("SELECT id::text, email FROM users ORDER BY email")
        captured["user_rows"] = [tuple(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT w.name, p.name FROM projects p "
            "JOIN workspaces w ON w.id = p.workspace_id ORDER BY w.name, p.name"
        )
        captured["project_rows"] = [tuple(row) for row in cursor.fetchall()]

    return captured


def _run(command: list[str], *, env: dict[str, str], stdout: IO[bytes] | None = None) -> None:
    """Run a subprocess, raising with its stderr when it fails."""
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        command,
        env=env,
        stdout=stdout,
        stderr=subprocess.PIPE,
        check=False,
        text=stdout is None,
    )

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        raise SystemExit(f"{command[0]} failed ({result.returncode}):\n{stderr}")


def main() -> int:  # noqa: C901 - a linear drill; splitting it would obscure the sequence
    """Execute the backup/restore drill and verify the result."""
    source_url = os.environ.get("PROJECTONE_TEST_DATABASE_URL")

    if not source_url:
        print(
            "PROJECTONE_TEST_DATABASE_URL is not set. This drill needs a "
            "disposable PostgreSQL database — never a shared or managed one.",
            file=sys.stderr,
        )
        return 2

    _require_disposable(source_url)
    _require_tooling()

    restore_db = f"{_RESTORE_DB_PREFIX}_{uuid.uuid4().hex[:8]}"
    admin_url = _with_database(source_url, "postgres")
    restore_url = _with_database(source_url, restore_db)
    env = {**os.environ}

    print("==> migrating the source database to head")
    from alembic import command as alembic_command
    from alembic.config import Config

    api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = Config(os.path.join(api_root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(api_root, "migrations"))
    config.set_main_option(
        "sqlalchemy.url", source_url.replace("postgresql://", "postgresql+psycopg://", 1)
    )
    alembic_command.upgrade(config, "head")

    print("==> seeding representative data across two workspaces")
    seeded = _seed(source_url)
    for workspace in seeded["workspaces"]:
        print(f"    {workspace['name']}: {workspace['projects']} projects")

    before = _capture_verification(source_url)
    print(
        f"    source: {len(before['tables'])} tables, "
        f"{len(before['workspace_rows'])} workspaces, "
        f"{len(before['project_rows'])} projects"
    )

    with tempfile.TemporaryDirectory() as workdir:
        dump_path = os.path.join(workdir, "projectone.dump")

        print("==> taking the backup (pg_dump, custom format)")
        backup_started = time.monotonic()
        with open(dump_path, "wb") as handle:
            _run(
                ["pg_dump", "--format=custom", "--no-owner", "--no-acl", source_url],
                env=env,
                stdout=handle,
            )
        backup_seconds = time.monotonic() - backup_started
        dump_bytes = os.path.getsize(dump_path)
        print(f"    {dump_bytes:,} bytes in {backup_seconds:.2f}s")

        print(f"==> creating an empty database to restore into: {restore_db}")
        # A separate, empty target. Restoring over the source would pass even if
        # the dump were empty, which is the failure this arrangement rules out.
        with psycopg.connect(admin_url, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f'CREATE DATABASE "{restore_db}"')

        try:
            print("==> restoring")
            restore_started = time.monotonic()
            _run(
                [
                    "pg_restore",
                    "--dbname",
                    restore_url,
                    "--no-owner",
                    "--no-acl",
                    "--exit-on-error",
                    dump_path,
                ],
                env=env,
            )
            restore_seconds = time.monotonic() - restore_started
            print(f"    restored in {restore_seconds:.2f}s")

            print("==> verifying the restored database against the source")
            after = _capture_verification(restore_url)

            failures: list[str] = []
            for key in (
                "tables",
                "constraints",
                "rls",
                "policies",
                "alembic_version",
                "workspace_rows",
                "user_rows",
                "project_rows",
            ):
                if before[key] != after[key]:
                    failures.append(f"  {key}: source={before[key]!r} restored={after[key]!r}")

            if failures:
                print("the restored database does NOT match the source:", file=sys.stderr)
                for line in failures[:20]:
                    print(line, file=sys.stderr)
                annotate(
                    "FA-03: restored database does not match the source",
                    "\n".join(failures[:20]),
                )
                return 1

            # Stated explicitly rather than implied by the absence of failures:
            # this is the claim [[Backup and Disaster Recovery]] could not make.
            print(f"    tables: {len(after['tables'])} — identical")
            print(f"    constraints: {len(after['constraints'])} — identical")
            print(f"    RLS flags: {len(after['rls'])} — identical")
            print(f"    policies: {len(after['policies'])} — identical")
            print(f"    workspaces: {len(after['workspace_rows'])} — identical, per tenant")
            print(f"    projects: {len(after['project_rows'])} — identical, per tenant")

            print("\n" + "=" * 68)
            print("FA-03: restore verified — schema and per-workspace data match.")
            print(f"  backup:  {backup_seconds:.2f}s ({dump_bytes:,} bytes)")
            print(f"  restore: {restore_seconds:.2f}s")
            print(
                "  NOTE: measured on a seeded test database, not production "
                "volumes. These are drill timings, not an RPO/RTO commitment."
            )
            print("=" * 68)
        finally:
            print(f"==> dropping {restore_db}")
            with psycopg.connect(admin_url, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP DATABASE IF EXISTS "{restore_db}" WITH (FORCE)')

    return 0


def _main_reporting_failures() -> int:
    """Run the drill, ensuring any failure reaches an annotation.

    `_run` raises SystemExit carrying the subprocess stderr, and an unexpected
    exception would otherwise surface only as a traceback in a log nobody
    without admin rights can read. Both are turned into an annotation first.
    """
    try:
        return main()
    except SystemExit as error:
        if error.code not in (0, None):
            annotate("FA-03: backup/restore drill failed", str(error))
        raise
    except Exception as error:
        annotate("FA-03: backup/restore drill errored", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    raise SystemExit(_main_reporting_failures())
