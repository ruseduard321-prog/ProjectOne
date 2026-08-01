"""Narrow table grants now that the API's database role is known.

STEP-09 deliberately left Supabase's default grants in place: `anon` and
`authenticated` each held DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE
and UPDATE on all three tables. Narrowing them required knowing which role the
API connects as, which was STEP-10's decision to make. It is now made -- the API
connects as `authenticator` and `SET LOCAL ROLE authenticated` per transaction --
so the grants can be brought in line with what that role actually needs.

**Grants and RLS are two independent gates, and both must be right.** A grant
says whether a role may attempt a command at all; a policy says which rows it
then touches. RLS was doing all the work here: `anon` held full DML on every
table and was held back purely by policies that matched no rows. That is one
mistake away from a breach -- a future table shipped without a policy would be
wide open to an unauthenticated role, because the grant was already there.
Defence in depth means removing the grant too (CLAUDE.md §16).

What changes:

- **`anon` loses everything.** No policy names `anon`, so it can already reach
  no rows. The grant was pure latent surface: it makes an unauthenticated role's
  reach depend entirely on someone never forgetting a policy.
- **`authenticated` keeps SELECT, INSERT and UPDATE.** Exactly the three
  commands the STEP-09 policies are written for, and nothing else.
- **DELETE is revoked from both.** There is no DELETE policy anywhere by design
  -- removal is a soft delete via `deleted_at` (RLS Policy Pattern). RLS already
  denies the command, so this makes the grant agree with the intent rather than
  relying on the absence of a policy to enforce it.
- **TRUNCATE and REFERENCES are revoked from both.** TRUNCATE is not subject to
  RLS *at all* -- a role holding it can empty a tenant table regardless of every
  policy on it. That is the single most dangerous grant in the default set and
  the one with the clearest case for removal.

`service_role` and `postgres` are untouched: both carry `rolbypassrls`, so no
grant change constrains them. The control there stays architectural -- neither
is used on the request path.

**Revoking the existing grants is not enough on its own.** Supabase ships
`ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon,
authenticated, service_role`, so *every table created from now on* is granted
`arwdDxtm` to `anon` and `authenticated` automatically -- DELETE and TRUNCATE
included. Revoking only the three tables that exist today would leave the next
tenant table arriving wide open, and the RLS Policy Pattern checklist would have
no way to catch it.

Confirmed by reading `pg_default_acl` during STEP-10, not assumed. This is the
same class of defect STEP-09 found with `REVOKE ... FROM PUBLIC` failing to
revoke `anon`'s EXECUTE on the definer function: Supabase's default privileges
are granted to roles *by name*, so they have to be addressed by name.

The default privileges are therefore altered too — for the `postgres` grantor,
which is the one Alembic creates tables as and therefore the one every
ProjectOne table inherits from. `supabase_admin` owns a second copy that
`postgres` cannot alter (it is not a superuser on managed Supabase); that copy
governs tables Supabase itself creates, not ProjectOne's tenant tables. The
limitation is recorded in RLS Policy Pattern rather than left implicit.

Revision ID: c4f21a86b3de
Revises: 860a798d204b
Create Date: 2026-08-01 14:22:10.114927

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4f21a86b3de"
down_revision: str | Sequence[str] | None = "860a798d204b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("users", "workspaces", "workspace_members")


def upgrade() -> None:
    """Reduce request-path grants to the minimum the policies need.

    Backward compatible in the sense STEP-13 requires: nothing running today
    uses these grants, because no application code touches these tables over a
    request-path role until this step's own code ships in the same commit.
    """
    for table in _TABLES:
        # Revoke everything first, then grant back exactly what is needed --
        # rather than revoking a list of unwanted privileges. If Supabase's
        # defaults gain a privilege later, this still ends in a known state
        # instead of silently leaving the new one in place.
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM anon")
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM authenticated")

        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table} TO authenticated")

    # Future tables, not just today's three. Without this, Supabase's default
    # privileges re-grant full DML (including DELETE and TRUNCATE) to `anon` and
    # `authenticated` on every table created from here on.
    #
    # `IN SCHEMA public` and the explicit role list mirror how Supabase set them
    # -- a default privilege is keyed by (grantor, schema, object type), so it
    # can only be altered by matching that key.
    # Only the `postgres` grantor. A default privilege is owned by the role that
    # created it, and `postgres` is not a superuser on managed Supabase, so
    # altering `supabase_admin`'s copy fails with "permission denied to change
    # default privileges" -- observed during STEP-10, not assumed.
    #
    # That is sufficient here because Alembic connects as `postgres`, so every
    # table this project creates inherits the `postgres` defaults corrected
    # below. The `supabase_admin` defaults apply to tables *Supabase* creates,
    # which are not ProjectOne's tenant tables. The residue is recorded in
    # RLS Policy Pattern rather than left as an undocumented gap.
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON TABLES FROM anon"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "REVOKE ALL ON TABLES FROM authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE ON TABLES TO authenticated"
    )


def downgrade() -> None:
    """Restore Supabase's default grants.

    Returns the tables to the permissive posture STEP-09 left them in, which is
    what "the previous migration's state" means here. It is deliberately not a
    safer-than-before state: a downgrade must restore, not improve, or the
    migration is not reversible.
    """
    for table in _TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
            f"ON TABLE public.{table} TO anon"
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
            f"ON TABLE public.{table} TO authenticated"
        )

    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO anon"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT ALL ON TABLES TO authenticated"
    )
