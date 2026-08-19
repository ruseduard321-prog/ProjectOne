"""Contain `public.alembic_version`: revoke application roles, enable RLS.

Alembic's own bookkeeping table was reachable by `anon` and `authenticated`
with `SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER`. This
migration removes that access and turns row-level security on.

## Why it was exposed, which is an ordering problem rather than an oversight

`c4f21a86b3de` narrowed the request-path grants and repaired Supabase's
`ALTER DEFAULT PRIVILEGES ... GRANT ALL ON TABLES TO anon, authenticated`, so
tables created after it arrive closed. It could not reach `alembic_version`,
because **Alembic creates that table at the start of the first
`alembic upgrade`, before it applies the first revision.** At that instant the
permissive defaults are still in force, so the table is created holding them.
`c4f21a86b3de` names three tables explicitly and fixes the defaults for
everything created afterwards; `alembic_version` is in neither set, and no list
of application tables would ever have caught it, because nothing in this
repository creates it.

That makes this reproducible rather than historical: **every clean bootstrap
against a Supabase-shaped database produces the same exposure**, which is why
the fix belongs in the migration chain and not in a one-off script.

## What made it urgent

`TRUNCATE`. It is not subject to row-level security at all, so no policy would
have contained it. An unauthenticated caller holding it could empty the
migration ledger, leaving a database whose recorded version no longer describes
its schema and which no subsequent migration can safely touch. Supabase's
advisor reported only the missing RLS (`rls_disabled_in_public`, ERROR); the
grant was the larger half of the finding and the advisor does not report it.

The two statements below were applied directly to `projectone-dev` on
2026-08-18 as emergency containment, with the project owner's knowledge, ahead
of this migration. This revision is what makes that change a version-controlled
migration rather than a manual, undocumented one (CLAUDE.md §13). Applying it
to that project changes nothing beyond stamping the revision: `REVOKE` of a
privilege that is not held is a no-op, and `ENABLE ROW LEVEL SECURITY` on an
already-enabled table is a no-op. Neither raises.

## `ENABLE`, deliberately without `FORCE`

[[RLS Policy Pattern]] requires `ENABLE` **and** `FORCE` on every application
table. This table is an explicit, documented exception, and the reason is what
the table is rather than what any particular environment tolerates:
`alembic_version` is infrastructure bookkeeping, not application or tenant
data. It intentionally carries no policies, and it must stay writable by
whichever role runs migrations — `FORCE` subjects the table owner to policies,
and the owner here is exactly that role.

In the environments this project supports today the distinction is not load
bearing: both the Supabase `postgres` role and the CI container's superuser
already bypass row-level policies, so `FORCE` would not lock them out.
Omitting it avoids creating that fragility for a future environment whose table
owner does *not* bypass RLS — where `FORCE` on a policy-less table would fail
the first `UPDATE alembic_version` and take the migration pipeline with it.

`tests/test_request_session.py` asserts `relforcerowsecurity` is false here, so
the exception stays deliberate instead of being "corrected" later by someone
cross-checking the catalog against the application-table rule.

## No policy, deliberately

The residual `rls_enabled_no_policy` advisor (INFO) is the intended terminal
state, not an open item. RLS denies by default, so with no policy defined
`anon` and `authenticated` reach zero rows — which is the requirement. A policy
here would be the defect.

## Roles left untouched, and why that is safe

`service_role` and `postgres` keep the table privileges they already hold, and
that retention is what keeps them working — a grant is an independent gate from
a policy, and `BYPASSRLS` does not substitute for one. `BYPASSRLS` exempts a
role from row-level *policies* only; it has no effect on ordinary SQL privilege
checks, so a role stripped of its grants would still be refused regardless of
the attribute. `service_role` remains functional here because its privileges
are deliberately retained. `postgres` owns this table and retains its existing
access on that basis, and its `BYPASSRLS` attribute independently exempts it
from policies.

Revision ID: 7b4360bcefed
Revises: a1b7c3e94f6d
Create Date: 2026-08-19 06:27:01.766340

"""

from collections.abc import Sequence

from alembic import op

revision: str = "7b4360bcefed"
down_revision: str | Sequence[str] | None = "a1b7c3e94f6d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# `REVOKE ALL` rather than a list of the unwanted privileges, matching
# `c4f21a86b3de`: if Supabase's defaults gain a privilege later, this still
# ends in a known state instead of silently leaving the new one in place.
_REVOKE_APPLICATION_ROLES = """
REVOKE ALL ON TABLE public.alembic_version FROM anon;
REVOKE ALL ON TABLE public.alembic_version FROM authenticated;
"""

# `ENABLE` only -- see the module docstring. No `FORCE`, and no policy.
_ENABLE_RLS = """
ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
"""


def upgrade() -> None:
    """Close both gates on Alembic's own bookkeeping table.

    Idempotent in both directions, which is what lets this run cleanly against
    `projectone-dev`, where the same two statements are already in effect.
    """
    op.execute(_REVOKE_APPLICATION_ROLES)
    op.execute(_ENABLE_RLS)


def downgrade() -> None:
    """Deliberately do nothing, rather than restore a known exposure.

    A downgrade normally restores the previous *intended* state (Table
    Conventions; `database-engineer` check 5). There is no intended prior state
    to restore here. These grants were never granted by a decision — they were
    inherited from Supabase's default privileges because Alembic creates this
    table before the first revision runs. Restoring an accident is not
    reversibility, and this asymmetry was approved by the project owner on
    2026-08-19 rather than chosen quietly.

    Restoring faithfully would also be materially worse than the comparable case
    in `c4f21a86b3de`. There, `anon`'s restored grants still met policies that
    matched no rows, so a second gate held. Here it would mean
    `DISABLE ROW LEVEL SECURITY` plus re-granting `DELETE` and `TRUNCATE` on the
    migration ledger to an unauthenticated role, with no second gate at all.

    Rollback-safety — the property this check actually protects — is unaffected.
    Nothing reads or writes `alembic_version` except Alembic itself and the two
    drill scripts, all over privileged connections, so downgrading past this
    revision breaks no previous version of the application.

    `scripts/migration_cycle_drill.py` (FA-02) compares `relrowsecurity` for
    every public table across `upgrade head -> downgrade base -> upgrade head`.
    Because this leaves the flag set and `upgrade()` is idempotent, both
    captures agree and the cycle stays clean.
    """
