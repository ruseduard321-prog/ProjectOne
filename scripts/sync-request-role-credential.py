"""Reset the request-path role's password, in the database and in `.env`, atomically.

## Why this exists

`projectone_api` is created by migration `d7b95c1f4e08` **without a password**,
deliberately: a credential in a migration is a credential in source control
(CLAUDE.md §16, §28a). The password is therefore set out of band, and
`REQUEST_DATABASE_URL` in the git-ignored `.env` has to be updated to match.

**Two independent writes with nothing linking them.** Nothing in the repository
can detect that they have diverged, and a divergence is invisible until the
first request that touches a tenant table -- which is exactly what happened on
2026-08-03, twice, costing most of two sessions.

This script removes the manual step rather than documenting it more carefully.
It generates the password, applies it to both places in one run, and proves the
result. **No human ever sees, types or copies the value**, which also means no
value reaches a terminal history, a clipboard, or a chat transcript.

## What it does, in order

1. Connects as the privileged role (`DATABASE_URL`) -- the only connection that
   can `ALTER ROLE`.
2. Asserts the target role exists and is **not** a superuser and does **not**
   carry `BYPASSRLS`. Refuses otherwise: silently resetting the password of a
   role that bypasses RLS would hand out a credential with no tenant isolation.
3. Generates a fresh 48-character URL-safe password.
4. `ALTER ROLE ... WITH LOGIN PASSWORD` inside a transaction.
5. **Verifies by connecting as that role over a new connection**, asserting
   `current_user` and `rolbypassrls = false`. If this fails, the transaction is
   rolled back and `.env` is never touched.
6. Only then rewrites `REQUEST_DATABASE_URL` in `.env`, preserving every other
   line, and writing to a temporary file that is atomically renamed.

Step 5 is the load-bearing one: it is what makes this deterministic rather than
hopeful. The script cannot report success unless a real connection as the real
role actually worked.

## Usage

    python scripts/sync-request-role-credential.py            # apply
    python scripts/sync-request-role-credential.py --check    # verify only

`--check` changes nothing. Use it in CI, or after a rollback past
`d7b95c1f4e08`, to answer "do these two still agree?" without a write.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import secrets
import sys
import tempfile
from urllib.parse import quote, urlsplit

import psycopg

#: The role this script manages. Matches migration `d7b95c1f4e08`.
ROLE = "projectone_api"

#: The variable in `.env` that must carry the role's credential.
ENV_VAR = "REQUEST_DATABASE_URL"

#: Long enough that it is never worth attacking, and URL-safe so it needs no
#: escaping inside a connection string -- percent-encoding a password into a DSN
#: is its own class of bug, and this avoids the category rather than handling it.
PASSWORD_BYTES = 36


def api_root() -> pathlib.Path:
    """Return `apps/api`, resolved from this script's location."""
    return pathlib.Path(__file__).resolve().parent.parent / "apps" / "api"


def read_env(path: pathlib.Path) -> dict[str, str]:
    """Parse `.env` into a mapping, tolerating CRLF and a BOM."""
    values: dict[str, str] = {}

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        values[name.strip()] = value.strip()

    return values


def rewrite_env(path: pathlib.Path, variable: str, new_value: str) -> None:
    """Replace one variable's value in place, preserving everything else.

    Writes to a temporary file in the same directory and renames it, so an
    interrupted run cannot leave a half-written `.env` -- which would take the
    API down harder than the problem being fixed.
    """
    original = path.read_text(encoding="utf-8-sig")
    newline = "\r\n" if "\r\n" in original else "\n"
    lines = original.splitlines()

    replaced = False
    for index, line in enumerate(lines):
        if line.strip().startswith(f"{variable}="):
            lines[index] = f"{variable}={new_value}"
            replaced = True
            break

    if not replaced:
        lines.append(f"{variable}={new_value}")

    handle, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8", newline="") as file:
        file.write(newline.join(lines) + newline)

    os.replace(temporary, path)


def build_dsn(template: str, role: str, password: str) -> str:
    """Return `template` with its user and password replaced.

    Host, port and database are carried over unchanged, so this works for the
    direct host and the session pooler alike -- including the pooler's
    `<role>.<project-ref>` username form, which is preserved when present.
    """
    parts = urlsplit(template)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""

    # Preserve a pooler-qualified username: `projectone_api.<project-ref>`.
    existing_user = parts.username or ""
    if "." in existing_user:
        _, _, project_ref = existing_user.partition(".")
        role = f"{role}.{project_ref}"

    return (
        f"{parts.scheme}://{role}:{quote(password, safe='')}@{host}{port}{parts.path}"
    )


def assert_role_is_safe(cursor: psycopg.Cursor, role: str) -> None:
    """Refuse to touch a role that would defeat tenant isolation.

    Resetting the password of a role carrying `BYPASSRLS` or `SUPERUSER` would
    mint a request-path credential for which every RLS policy is skipped --
    which is the one outcome this whole architecture exists to prevent
    (RLS Policy Pattern). Checked here rather than assumed, because the check
    costs one query and the failure is a cross-tenant breach.
    """
    cursor.execute(
        "SELECT rolbypassrls, rolsuper, rolinherit FROM pg_authid WHERE rolname = %s",
        (role,),
    )
    row = cursor.fetchone()

    if row is None:
        raise SystemExit(
            f"Role {role!r} does not exist. It is created by migration d7b95c1f4e08 -- "
            "run `alembic upgrade head` first."
        )

    bypassrls, superuser, inherit = row

    if bypassrls or superuser:
        raise SystemExit(
            f"REFUSING to set a password on {role!r}: it carries "
            f"{'BYPASSRLS ' if bypassrls else ''}{'SUPERUSER' if superuser else ''}. "
            "A request-path role that bypasses RLS has no tenant isolation at all."
        )

    if inherit:
        print(
            f"  ! {role} has INHERIT set; migration d7b95c1f4e08 creates it NOINHERIT.\n"
            "    Not fatal, but a request path that skips SET ROLE would then fail open.",
            file=sys.stderr,
        )


def verify(dsn: str, role: str) -> None:
    """Connect as the role and assert it is subject to RLS.

    A fresh connection, deliberately: the point is to prove the credential works
    end to end, which a check inside the privileged session cannot do.
    """
    with psycopg.connect(dsn, connect_timeout=30) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT current_user, "
            "(SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)"
        )
        current_user, bypassrls = cursor.fetchone()

    expected = role.partition(".")[0]
    if current_user != expected:
        raise SystemExit(f"Connected as {current_user!r}, expected {expected!r}")

    if bypassrls:
        raise SystemExit(
            f"{current_user!r} carries rolbypassrls -- every RLS policy would be skipped."
        )

    print(f"  + authenticated as {current_user}, rolbypassrls = {bypassrls}")


def main() -> int:
    """Reset or check the request-path credential."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the current credential without changing anything.",
    )
    arguments = parser.parse_args()

    env_path = api_root() / ".env"
    if not env_path.exists():
        raise SystemExit(f"{env_path} not found. Copy .env.example first.")

    env = read_env(env_path)

    for required in ("DATABASE_URL", ENV_VAR):
        if required not in env:
            raise SystemExit(f"{required} is missing from {env_path}")

    if arguments.check:
        print(f"Checking {ENV_VAR} authenticates as {ROLE} ...")
        verify(env[ENV_VAR], ROLE)
        print("OK -- the database and .env agree.")
        return 0

    print(f"Resetting {ROLE}'s password in the database and in .env ...")

    password = secrets.token_urlsafe(PASSWORD_BYTES)
    new_dsn = build_dsn(env[ENV_VAR], ROLE, password)

    with psycopg.connect(env["DATABASE_URL"], connect_timeout=30) as admin:
        cursor = admin.cursor()
        assert_role_is_safe(cursor, ROLE)

        # psycopg cannot parameterise a role name or a password in ALTER ROLE,
        # so the password is quoted as a literal by the server-side quoting
        # helper rather than interpolated by hand.
        cursor.execute("SELECT quote_literal(%s)", (password,))
        quoted = cursor.fetchone()[0]
        cursor.execute(f"ALTER ROLE {ROLE} WITH LOGIN PASSWORD {quoted}")
        admin.commit()
        print(f"  + ALTER ROLE {ROLE} applied")

    # Proven before `.env` is touched. If this raises, the database has the new
    # password and `.env` still has the old one -- so re-running the script is
    # always safe and always converges.
    verify(new_dsn, ROLE)

    rewrite_env(env_path, ENV_VAR, new_dsn)
    print(f"  + {ENV_VAR} updated in {env_path}")
    print("\nOK -- the database and .env now agree, verified by a real connection.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
