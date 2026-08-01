"""Create the API's request-path database role.

The decision STEP-10 could not avoid: which role the API connects as when it
serves a request. `postgres` and `service_role` both carry `rolbypassrls`, so
PostgreSQL skips every RLS policy for them -- an API on either reads every
workspace's rows while all 17 STEP-09 isolation tests keep passing, because
those tests connect as `authenticated`.

**Why a ProjectOne-owned role rather than Supabase's `authenticator`.**
`authenticator` is the obvious candidate: it is Supabase's own request-path
login role and already has the right attributes. It was rejected for one
practical reason and one architectural one:

- **It cannot be provisioned from here.** Supabase marks `authenticator` as a
  reserved role, and `postgres` is not a superuser on managed Supabase, so
  `ALTER ROLE authenticator WITH PASSWORD` fails with "is a reserved role, only
  superusers can modify it". Observed, not assumed.
- **Its definition is Supabase's to change.** PostgREST uses it, and its grants
  may shift under a platform update. A role this project creates is versioned
  here, and its privileges are reviewable in this file.

The attributes are chosen, not defaults:

| Attribute | Why |
|---|---|
| `NOBYPASSRLS` | The entire point. Policies apply to this role. |
| `NOSUPERUSER` | A superuser bypasses RLS regardless of `NOBYPASSRLS`. |
| `NOINHERIT` | See below -- the one attribute worth explaining at length. |
| `NOCREATEDB` / `NOCREATEROLE` | It serves requests; it has no reason to alter the cluster. |

**Why `NOINHERIT` specifically.** The role is granted `authenticated`, so with
`INHERIT` it would hold that role's privileges automatically on every
connection. It would work -- and it would fail open: a request path that forgot
to `SET ROLE` would still read and write tenant tables, just without the policy
context, and nothing would look wrong. With `NOINHERIT` the same bug reads
**nothing at all**, because the connection holds no table privileges until the
role switch happens. The failure is loud instead of silent, which is the only
acceptable direction for a bug in this particular code path.

The password is deliberately **not** set here. A credential in a migration is a
credential in source control (CLAUDE.md §16, §28a) -- it is set out of band, per
environment, and reaches the API through `REQUEST_DATABASE_URL`. The role is
created `NOLOGIN` for that reason: a login role with no password set is not a
usable account, but stating it explicitly means an environment that skips the
out-of-band step gets a connection failure rather than a role that might be
reachable some other way.

Revision ID: d7b95c1f4e08
Revises: c4f21a86b3de
Create Date: 2026-08-01 15:04:38.220914

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d7b95c1f4e08"
down_revision: str | Sequence[str] | None = "c4f21a86b3de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE = "projectone_api"


def upgrade() -> None:
    """Create the request-path role and grant it the ability to become `authenticated`."""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE} WITH
                    NOLOGIN
                    NOINHERIT
                    NOBYPASSRLS
                    NOSUPERUSER
                    NOCREATEDB
                    NOCREATEROLE;
            ELSE
                -- Idempotent. Only NOINHERIT is re-asserted: on managed
                -- Supabase `postgres` is not a superuser, and naming
                -- NOSUPERUSER or NOBYPASSRLS in an ALTER is itself a
                -- superuser-only operation -- it fails with "only roles with
                -- the SUPERUSER attribute may alter roles with the SUPERUSER
                -- attribute" even when the target already lacks them.
                -- Observed during STEP-10.
                ALTER ROLE {ROLE} WITH NOINHERIT NOCREATEDB NOCREATEROLE;
            END IF;

            -- Asserted rather than assumed, because it cannot be re-applied
            -- above and it is the one property the whole design rests on. A
            -- role that has drifted to BYPASSRLS or SUPERUSER silently
            -- disables tenant isolation for every request, so the migration
            -- refuses to complete rather than leaving it to be noticed later.
            IF EXISTS (
                SELECT 1 FROM pg_roles
                WHERE rolname = '{ROLE}' AND (rolbypassrls OR rolsuper)
            ) THEN
                RAISE EXCEPTION
                    'Role {ROLE} carries BYPASSRLS or SUPERUSER; it must not serve requests';
            END IF;
        END
        $$;
        """
    )

    # `SET ROLE authenticated` requires membership. NOINHERIT above is what
    # keeps this from being an implicit grant of authenticated's privileges.
    op.execute(f"GRANT authenticated TO {ROLE}")

    # Without USAGE the role cannot see the schema at all, and every query fails
    # with "permission denied for schema public" rather than returning no rows.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")


def downgrade() -> None:
    """Remove the request-path role.

    Ordered deliberately: a role cannot be dropped while it still holds
    privileges, so the grants are revoked first. `DROP ROLE IF EXISTS` keeps the
    downgrade replayable if the role was already removed by hand.
    """
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE}")
    op.execute(f"REVOKE authenticated FROM {ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {ROLE}")
