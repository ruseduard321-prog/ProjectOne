"""Create the append-only security event log for authentication events.

**FA-06**, closed under the project owner's decision of 2026-08-15: a separate
table rather than widening `audit_log`.

## Why `audit_log` could not absorb these

`audit_log.workspace_id` is `NOT NULL` with a foreign key to `workspaces`,
because every action it records happens inside a tenant and is read back by that
tenant's members. **The events this table exists for have no tenant, and often
no user.** A failed sign-in is recorded at a moment when nothing about the
caller is known or trustworthy — there is no workspace to attribute it to, and
naming a user would be worse than useless (see the oracle note below).

Making `audit_log.workspace_id` nullable would put rows in a tenant-scoped table
that `audit_log_select_same_workspace` cannot classify: `workspace_id IN (...)`
is neither true nor false for NULL, so such rows would be invisible to every
reader while still occupying the table that a tenant is told is their audit
trail. `a3c07d5e91f4` wrote itself out of exactly that, and this migration keeps
that decision intact rather than reversing it.

## The account-existence oracle, and how the schema forecloses it

The hard requirement is not "do not store the password". It is that **an
attacker who can submit addresses must not learn which ones exist** — and an
audit table is a surprisingly easy way to hand that over:

- **No column can hold a submitted identifier.** No `email`, no `username`, no
  `identifier` — and deliberately no `email_hash` either. A hash is an oracle to
  anyone who can compute it over a guess, which is everyone; it protects the
  address from a casual reader and not at all from the attack that matters.
- **`user_id` is nullable and is null on every failure.** A row reading
  "sign-in failed for user X" answers "does X exist?" from its own contents.
  `ck_security_event_log_failure_is_anonymous` enforces this in the database, so
  it holds even against a caller that gets the application logic wrong.
- **No IP address.** Recording one would make this a table of personal data
  about unauthenticated strangers, which fails the data-minimisation rule
  (CLAUDE.md §16) that the rest of this schema is built to.

What remains is what an investigation actually needs: what kind of event,
whether it succeeded, when, and the correlation id that ties it to the request
log.

## Append-only, enforced rather than intended

Four independent mechanisms, in the same spirit as `a3c07d5e91f4`:

1. **No policies at all.** RLS denies by default, so with `ENABLE` and `FORCE`
   set and not one policy defined, `authenticated` has no route to any command.
   The total absence *is* the control here — stricter than `audit_log`, which
   has a SELECT policy because a workspace's own actions are its own business.
   These events span tenants and precede identity, so there is no correct tenant
   scope to read them under, and the owner's requirement is explicit: no
   tenant-facing read path.
2. **No grants.** `REVOKE ALL` and nothing granted back. A grant is an
   independent gate from a policy ([[RLS Policy Pattern]]), and `TRUNCATE` in
   particular is not subject to RLS at all.
3. **An UPDATE trigger that raises.** Policies and grants stop the *request*
   role; they do not stop the privileged connection the application writes over,
   and a bug there is precisely what would rewrite history. The trigger closes
   that path, so immutability holds against every route except the approved
   retention delete.
4. **Writes come only from the privileged connection**, inside
   `SecurityEventService`. A client able to forge its own security events could
   bury a real one under noise.

## Privileges

The minimum the requirement allows: the application appends over the privileged
connection, retention deletes over the same one, and the request-path role holds
nothing whatsoever. There is no read path for any tenant and no public endpoint.

Revision ID: b2e94c17a5d3
Revises: c8f1a3d54e29
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2e94c17a5d3"
down_revision: str | Sequence[str] | None = "c8f1a3d54e29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREATE_TABLE = """
CREATE TABLE public.security_event_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- When it happened. The only timestamp: these rows are never modified, so
    -- there is no `updated_at` to maintain and no `version` to increment.
    created_at timestamptz NOT NULL DEFAULT now(),

    -- What kind of event. `text` with a CHECK rather than an ENUM, per
    -- Table Conventions: adding an event type later is one ALTER statement
    -- instead of a type rewrite that locks the table.
    --
    -- The allowlist is the point. An event type this constraint does not know
    -- is a row nobody can interpret later, and silently accepting one would let
    -- a typo become an entire category of events that no query finds.
    event_type text NOT NULL
        CONSTRAINT ck_security_event_log_type_valid CHECK (event_type IN (
            'auth.sign_up',
            'auth.sign_in',
            'auth.sign_out',
            'auth.token_refresh'
        )),

    -- Whether it worked. Recording only successes would omit exactly the events
    -- an investigation starts from.
    outcome text NOT NULL
        CONSTRAINT ck_security_event_log_outcome_valid
        CHECK (outcome IN ('succeeded', 'failed')),

    -- The correlation id of the request, so a security event can be joined to
    -- the request log without either side carrying the other's data. Opaque and
    -- server-generated (`app.core.middleware`), and sanitised there before it
    -- ever reaches here.
    request_id text NOT NULL,

    -- Who, *where that is already known to the caller*. Null on every failure
    -- (see the constraint below) and null wherever identity was never
    -- established.
    --
    -- Not a foreign key, for the reason `audit_log.actor_id` is not one: the
    -- trail must outlive the account that generated it, and an FK would mean
    -- either blocking a user's deletion forever or cascading their security
    -- history away with them.
    user_id uuid,

    -- The workspace, on the rare event that has one. Nullable, and deliberately
    -- **not** a foreign key: an FK to `workspaces` would make this table a
    -- teardown dependency of every workspace and would block a workspace's
    -- deletion on its own security history.
    workspace_id uuid,

    -- Bounded, allowlisted diagnostic context -- a failure reason, never an
    -- identifier or a secret. `SecurityEvent` refuses forbidden keys and
    -- secret-shaped values before a row is ever built; this size cap is the
    -- database's own backstop, since an append-only table with unbounded row
    -- size is a storage problem that only shows up in production.
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CONSTRAINT ck_security_event_log_metadata_bounded
        CHECK (pg_column_size(metadata) <= 2048),

    -- **The oracle rule, in the database.**
    --
    -- A failed authentication must not name a user or a workspace. Enforced
    -- here as well as in `SecurityEvent` because application logic is what gets
    -- this wrong under time pressure, and the consequence -- a table that
    -- answers "does this account exist?" -- is not one that shows up in a test
    -- somebody remembered to write.
    CONSTRAINT ck_security_event_log_failure_is_anonymous
        CHECK (outcome <> 'failed' OR (user_id IS NULL AND workspace_id IS NULL))
);
"""

# Retention scans by age, and investigations read by time. Both are served by
# one index on `created_at`, which is also the only column the purge filters on.
#
# No index on `user_id`: there is no read path that filters by it, and indexing
# a column speculatively is exactly what Chapter 7 forbids.
_INDEXES = """
CREATE INDEX ix_security_event_log_created_at
    ON public.security_event_log (created_at DESC);
"""

_ENABLE_RLS = """
ALTER TABLE public.security_event_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.security_event_log FORCE ROW LEVEL SECURITY;
"""

# Deliberately no policies whatsoever -- see the module docstring. RLS denies by
# default, so their absence denies every command to every non-owner role.
#
# `FORCE` matters more here than anywhere else in the schema: without it the
# table owner bypasses RLS entirely, and the owner is the role the application's
# privileged connection uses.

# Grants: none. Stated as an explicit REVOKE rather than assumed from the
# schema's default privileges, for the reason `a3c07d5e91f4` records --
# depending on a default for a security property is how the next Supabase
# change silently reopens it.
_GRANTS = """
REVOKE ALL ON public.security_event_log FROM anon, authenticated;
"""

# Immutability against the privileged connection too.
#
# The grants above stop `authenticated`. They do not stop the role the
# application itself writes as, and "append-only" that holds only for clients is
# not the property this table is for. `BEFORE UPDATE` rather than a rule or a
# check so the failure is loud, immediate, and names itself.
#
# DELETE is deliberately *not* blocked: the approved retention mechanism is a
# filtered delete, and a trigger forbidding it would make the 90-day policy
# unimplementable. Deletion is instead constrained by privilege -- only the
# privileged connection can reach the table at all.
_IMMUTABILITY_TRIGGER = """
CREATE OR REPLACE FUNCTION public.security_event_log_forbid_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'security_event_log is append-only; rows cannot be modified'
        USING ERRCODE = 'raise_exception';
END;
$$;

CREATE TRIGGER trg_security_event_log_forbid_update
    BEFORE UPDATE ON public.security_event_log
    FOR EACH ROW
    EXECUTE FUNCTION public.security_event_log_forbid_update();
"""


def upgrade() -> None:
    """Create the append-only security event log, denied to every client role."""
    op.execute(_CREATE_TABLE)
    op.execute(_INDEXES)
    op.execute(_ENABLE_RLS)
    op.execute(_GRANTS)
    op.execute(_IMMUTABILITY_TRIGGER)


def downgrade() -> None:
    """Drop the security event log and its trigger function.

    Written and verified alongside `upgrade()` per Table Conventions, and
    exercised on every pull request by `scripts/migration_cycle_drill.py`
    (FA-02) — which is what makes this reversible in fact rather than in
    intention.

    Dropping the table removes its trigger, index and constraints with it. The
    trigger *function* is schema-level and is not, so it is dropped explicitly;
    leaving it behind would make the cycle non-idempotent and fail the drill.

    Worth stating plainly: rolling this back **destroys the authentication
    trail**, for the same reason and with the same weight as `a3c07d5e91f4`.
    """
    op.execute("DROP TABLE IF EXISTS public.security_event_log;")
    op.execute("DROP FUNCTION IF EXISTS public.security_event_log_forbid_update();")
