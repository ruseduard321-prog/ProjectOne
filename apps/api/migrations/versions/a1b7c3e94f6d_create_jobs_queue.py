"""Create the `jobs` table: ProjectOne's queue, and the first tenant table a worker writes.

[[ADR-005 Async Job Queue and Worker Execution Model]] §1 decided that the queue
is a PostgreSQL table in the existing database, claimed with
`SELECT ... FOR UPDATE SKIP LOCKED`. This is that table. The ADR deliberately
left the columns, indexes and state vocabulary to this migration (ADR-005 §Scope
Boundaries), so every choice below is made here and reviewed under
[[CLAUDE|CLAUDE.md]] §13.

It follows [[RLS Policy Pattern]] and [[Table Conventions]] without deviation.
Six decisions are specific to this table.

## The state vocabulary is four values, and `failed` is deliberately not one

    pending -> running -> succeeded
                       -> pending        (a retryable failure, attempts remain)
                       -> dead_lettered  (terminal, or attempts exhausted)

A separate `failed` state was considered and rejected. A job that failed and will
be retried is *pending* -- that is precisely what pending means -- and a job that
failed and will not be retried is *dead-lettered*. A third value between them
would name a state nothing can be in, and every reader would have to learn which
of `failed` and `dead_lettered` meant "give up". ADR-005 §7 requires that a
dead-lettered job be "visible rather than a silently dropped row"; one terminal
failure state with a timestamp and a stored error is what makes it visible.

## `enqueued_by` is the security mechanism; `workspace_id` is the attribution

ADR-005 §4 is explicit about this and it is worth restating where the columns
live. RLS in ProjectOne resolves through `auth.uid()` and `workspace_members`, so
the worker establishes tenant context by *replaying the enqueuing user's
identity*. `enqueued_by` is therefore load-bearing, not informational.

`workspace_id` is what the job is for, what the ledger charges, and what an
operator filters on. It is not what makes the execution safe.

Neither is a foreign key to `users`: a job record should outlive the account that
enqueued it, matching `workflow_runs.triggered_by` and `projects.created_by`.
The *live* membership is checked at execution time by the worker, against
`workspace_members` through RLS, which is where the answer must be current.

## The INSERT policy pins `enqueued_by` to the caller

    WITH CHECK (workspace_id IN (...) AND enqueued_by = auth.uid())

Without the second clause any member could enqueue a job that later executes as
**another member's identity** -- a member naming the owner would get the owner's
row visibility on a delayed fuse, and no route test would notice, because at
enqueue time nothing has happened yet. The workspace predicate alone does not
catch it: both users are in the same workspace, which is the whole point.

This is the one place the identity a worker will replay is chosen, so it is the
one place that choice can be constrained. It is constrained to "yourself".

## Queue state is not client-writable

`authenticated` needs `UPDATE` on this table for exactly one operation: the soft
delete that workspace erasure performs (`JobStore.erase`, [[CLAUDE|CLAUDE.md]]
§16). Granting it leaves every other column writable by a tenant, and the
consequences are not cosmetic -- a member could reset `attempts` to zero and
replay a job indefinitely, or set `status` to `succeeded` on a job that never
ran, or extend their own lease.

`app_jobs_queue_state_not_client_writable` refuses that. The shape is copied from
`app_messages_immutable` (`b4e8c02d71fa`), including the whitelist and the `app_`
name prefix that makes it fire before `touch_row`, and for the same two reasons:
RLS cannot express a rule about `OLD` and `NEW` together, and a whitelist makes
every column added later immutable by default.

It applies to `authenticated` only. The dispatcher connects as the table owner,
and what bounds *it* is ADR-005 §5: one table, three operations, every claim
logged -- a boundary this migration cannot enforce and
`tests/test_job_boundary.py` asserts instead.

## `max_attempts` is bounded by the composed ceiling, in the database

ADR-005 §7 fixes the job attempt ceiling at **2 per enqueue**, which composes to
60 upstream provider requests (2 x 5 chained invocations x 6 requests per
`complete()`). The CHECK constraint holds that number rather than trusting the
application constant alone, so a handler registering a higher ceiling is refused
by PostgreSQL rather than quietly doubling the platform's worst-case AI spend.

`tests/test_job_contract.py` asserts the constraint bound and
`MAX_JOB_ATTEMPTS` against each other, so raising one without the other fails
immediately -- the `assets.kind` defect STEP-21 paid for, pre-empted.

## The claimable index is partial, and covers both claimable shapes

A poll asks for the oldest row that is either `pending`, or `running` with a
lapsed lease. Both are covered by one partial index on
`(status, created_at) WHERE deleted_at IS NULL`, so each poll is an index scan
returning almost nothing -- the property ADR-005 §1 rests its "load is fine at
this scale" argument on. `lease_expires_at` is deliberately *not* in the
predicate: it is compared against `now()`, which is not immutable and therefore
not indexable in a partial predicate.

Revision ID: a1b7c3e94f6d
Revises: b2e94c17a5d3
Create Date: 2026-08-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1b7c3e94f6d"
down_revision: str | Sequence[str] | None = "b2e94c17a5d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREATE_JOBS = """
CREATE TABLE public.jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    version integer NOT NULL DEFAULT 1,

    workspace_id uuid NOT NULL
        CONSTRAINT fk_jobs_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    -- The identity the worker replays to establish tenant context (ADR-005 §4).
    -- Pinned to the caller by the INSERT policy below; see the module docstring.
    enqueued_by uuid NOT NULL,

    -- Which registered handler runs this job. `text` rather than an FK for the
    -- same reason `workflow_runs.workflow_type` is: handlers are declared in
    -- code (`app/jobs/registry.py`), and a handlers table would be a second
    -- source of truth able to disagree with the code that actually executes.
    job_type text NOT NULL
        CONSTRAINT ck_jobs_type_not_blank CHECK (btrim(job_type) <> '')
        CONSTRAINT ck_jobs_type_length CHECK (char_length(job_type) <= 100),

    -- What the handler is given. Opaque to the queue by design: the dispatcher
    -- never reads inside it, which is part of what keeps the cross-tenant
    -- dispatch path bounded to "a job id, a workspace id, a user id, a job type
    -- and an opaque payload" (ADR-005 §5 constraint 1).
    --
    -- `jsonb` rather than `text` for the reason `workflow_step_runs.output` is:
    -- structured data stored as text is parsed by every reader, and one of them
    -- eventually parses it differently.
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- Matches `JobStatus` in `app/jobs/contract.py` exactly, asserted by
    -- `test_job_status_vocabulary_matches_the_database` rather than trusted to
    -- have been edited together.
    status text NOT NULL DEFAULT 'pending'
        CONSTRAINT ck_jobs_status_valid CHECK (status IN (
            'pending',
            'running',
            'succeeded',
            'dead_lettered'
        )),

    -- Incremented by the claim, never by the settle. A lease recovery therefore
    -- consumes an attempt exactly as an ordinary claim does, which is what stops
    -- a worker that dies mid-job from looping on it forever (ADR-005 §6).
    attempts integer NOT NULL DEFAULT 0
        CONSTRAINT ck_jobs_attempts_non_negative CHECK (attempts >= 0),

    -- Declared by the handler at registration; there is no default that
    -- silently permits work (ADR-005 §7). The upper bound is the accepted
    -- composed ceiling -- see the module docstring.
    max_attempts integer NOT NULL
        CONSTRAINT ck_jobs_max_attempts_within_ceiling
            CHECK (max_attempts >= 1 AND max_attempts <= 2),

    CONSTRAINT ck_jobs_attempts_within_ceiling CHECK (attempts <= max_attempts),

    -- Which worker process holds this job, for an operator reading a stuck
    -- queue. Not a credential and not an identity -- host and pid.
    claimed_by text
        CONSTRAINT ck_jobs_claimed_by_length CHECK (char_length(claimed_by) <= 200),
    claimed_at timestamptz,

    -- When this claim lapses. A worker that dies stops extending it, and the
    -- job becomes claimable again once it passes (ADR-005 §6). Null whenever
    -- the job is not `running`.
    lease_expires_at timestamptz,

    -- Which claim currently owns the job. Regenerated on every claim, so a
    -- worker whose lease lapsed cannot extend, complete or fail a job that
    -- another worker has since taken -- it holds a token the row no longer
    -- carries, and its statements match zero rows.
    --
    -- **This is not decoration; at-least-once makes it necessary.** ADR-005 §6
    -- states plainly that a lapsed lease means the job becomes claimable "while
    -- the original worker may still be running it". Without a token, that
    -- original worker's eventual `record_outcome` would overwrite the state of
    -- the worker that legitimately owns the job now. The same reasoning, and the
    -- same shape, as `messages.claim_token` (`c8f1a3d54e29`).
    lease_token uuid,

    -- What the handler returned, so a job's outcome is inspectable without
    -- attaching a debugger ([[CLAUDE|CLAUDE.md]] §26).
    result jsonb,

    -- Why the last attempt failed. Written from the error's `public_message`
    -- where it has one, never from an arbitrary exception's own message: this
    -- column is tenant-readable through the SELECT policy, and an unexpected
    -- exception's text is written for an engineer (§24).
    last_error text
        CONSTRAINT ck_jobs_last_error_length CHECK (char_length(last_error) <= 2000),

    -- Set when the job reaches `dead_lettered`, so "how long has this been
    -- dead" is answerable without diffing timestamps.
    dead_lettered_at timestamptz,

    -- The enqueuing request's X-Request-ID, so an asynchronous failure is
    -- traceable back to what caused it (ADR-005 §7, [[CLAUDE|CLAUDE.md]] §26).
    -- The worker binds it into its own logging context before executing.
    correlation_id text
        CONSTRAINT ck_jobs_correlation_id_length CHECK (char_length(correlation_id) <= 200),

    finished_at timestamptz
);
"""

# Partial on `deleted_at IS NULL` throughout, matching every other table here:
# every query filters liveness (the filter is not in the policies), so an index
# excluding dead rows serves exactly the queries that exist.
_INDEXES = """
CREATE INDEX ix_jobs_status_created_at
    ON public.jobs (status, created_at)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_jobs_workspace_id
    ON public.jobs (workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_jobs_workspace_id_status
    ON public.jobs (workspace_id, status)
    WHERE deleted_at IS NULL;
"""

_ENABLE_RLS = """
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs FORCE ROW LEVEL SECURITY;
"""

# Per-command policies, never one FOR ALL.
#
# **No `deleted_at IS NULL` in the SELECT policy.** The table is soft-deleted by
# workspace erasure, and that filter would make the erasure impossible -- the
# defect that cost STEP-11a and STEP-19 a step each. Held at creation time here,
# as it now has been for `projects`, `assets` and the two workflow tables.
#
# Any live member may read and enqueue: a job is work the workspace asked for,
# and a member who cannot see what the platform is doing on their behalf cannot
# audit it. The INSERT policy additionally pins `enqueued_by` -- see the module
# docstring, which is the security half of this table.
_POLICIES = """
CREATE POLICY jobs_select_same_workspace ON public.jobs
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY jobs_insert_member ON public.jobs
FOR INSERT TO authenticated
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces())
    AND enqueued_by = auth.uid()
);

CREATE POLICY jobs_update_member ON public.jobs
FOR UPDATE TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));
"""

# Stated explicitly rather than inherited from Supabase's corrected defaults --
# depending on a default for a security property is how the next platform change
# silently reopens it. No DELETE (soft deletion only) and no TRUNCATE (not
# subject to RLS at all).
_GRANTS = """
REVOKE ALL ON public.jobs FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.jobs TO authenticated;
"""

# The role test is the whole design. `authenticated` is the role every RLS-subject
# session runs as (`RequestSessionFactory`), so this bounds the *client* path to
# the one column erasure needs. The dispatcher connects as the table owner and is
# bounded by ADR-005 §5 instead -- one table, three operations, every claim
# logged -- which is a boundary a trigger cannot express and a test asserts.
#
# **`SECURITY INVOKER`, unlike `app_messages_immutable`, and the difference is
# load-bearing rather than stylistic.** Inside a `SECURITY DEFINER` function
# `current_user` is the function's *owner*, so the test above would read
# `postgres` on every call and the guard would never fire -- it would pass review,
# pass a casual reading, and protect nothing. That was observed against a real
# database before this comment was written. Invoker rights make `current_user`
# the caller's effective role, which is the question being asked.
#
# Dropping definer rights costs nothing here: the function reads two records and
# raises, touching no table, so there is no privilege for it to have needed.
# `SET search_path = ''` is kept regardless, and every reference below is a
# column or a literal.
_WRITE_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION public.app_jobs_queue_state_not_client_writable()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    IF current_user <> 'authenticated' THEN
        RETURN NEW;
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
       OR NEW.enqueued_by IS DISTINCT FROM OLD.enqueued_by
       OR NEW.job_type IS DISTINCT FROM OLD.job_type
       OR NEW.payload IS DISTINCT FROM OLD.payload
       OR NEW.status IS DISTINCT FROM OLD.status
       OR NEW.attempts IS DISTINCT FROM OLD.attempts
       OR NEW.max_attempts IS DISTINCT FROM OLD.max_attempts
       OR NEW.claimed_by IS DISTINCT FROM OLD.claimed_by
       OR NEW.claimed_at IS DISTINCT FROM OLD.claimed_at
       OR NEW.lease_expires_at IS DISTINCT FROM OLD.lease_expires_at
       OR NEW.lease_token IS DISTINCT FROM OLD.lease_token
       OR NEW.result IS DISTINCT FROM OLD.result
       OR NEW.last_error IS DISTINCT FROM OLD.last_error
       OR NEW.dead_lettered_at IS DISTINCT FROM OLD.dead_lettered_at
       OR NEW.correlation_id IS DISTINCT FROM OLD.correlation_id
       OR NEW.finished_at IS DISTINCT FROM OLD.finished_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
    THEN
        -- 23514 (check_violation), matching `app_messages_immutable` and
        -- `app_protect_last_owner`. An integrity rule, not a permission one:
        -- the caller holds every privilege the statement needs, and the answer
        -- is still no.
        RAISE EXCEPTION 'job % queue state is not client-writable', OLD.id
            USING ERRCODE = '23514',
                  HINT = 'A client may only soft-delete a job. Queue state '
                         'belongs to the worker dispatcher (ADR-005 §5).';
    END IF;

    RETURN NEW;
END;
$$;
"""

# BEFORE triggers fire in **alphabetical order by name**, and a later trigger
# sees a NEW that an earlier one may already have modified. `app_...` sorts
# before `trg_jobs_touch_row`, so this compares the row the caller actually
# submitted rather than one `touch_row` has already advanced two columns of --
# which would make `updated_at` and `version` look changed on every legitimate
# soft delete. The same ordering reason as `app_messages_immutable`.
_WRITE_GUARD_TRIGGER = """
CREATE TRIGGER app_jobs_queue_state_not_client_writable
BEFORE UPDATE ON public.jobs
FOR EACH ROW
EXECUTE FUNCTION public.app_jobs_queue_state_not_client_writable();
"""

_TOUCH_TRIGGER = """
CREATE TRIGGER trg_jobs_touch_row
BEFORE UPDATE ON public.jobs
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();
"""


def upgrade() -> None:
    """Create `jobs` with its RLS policies, grants, indexes and triggers."""
    op.execute(_CREATE_JOBS)
    op.execute(_INDEXES)
    op.execute(_ENABLE_RLS)
    op.execute(_POLICIES)
    op.execute(_GRANTS)
    op.execute(_WRITE_GUARD_FUNCTION)
    op.execute(_WRITE_GUARD_TRIGGER)
    op.execute(_TOUCH_TRIGGER)


def downgrade() -> None:
    """Drop the table and its write guard.

    Dropping a table removes its policies, indexes, grants and triggers with it;
    the guard *function* is schema-level and is dropped explicitly.

    Rolling this back **destroys every queued and completed job in every
    workspace**, including the dead-letter record of work that failed. Nothing
    else holds that record, so this is a decision rather than a routine
    operation -- the same caution `f3c82b19d4a7` states about workflow history.
    """
    op.execute("DROP TABLE IF EXISTS public.jobs;")
    op.execute("DROP FUNCTION IF EXISTS public.app_jobs_queue_state_not_client_writable();")
