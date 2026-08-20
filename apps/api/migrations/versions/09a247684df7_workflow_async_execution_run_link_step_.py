"""Workflow async execution: the run link, durable step state, and five protected commands.

[[ADR-006 Workflow Async Execution and Run Reconciliation]] is accepted, and this
migration is the whole of its database half. Nothing here is a new decision; the
reasoning lives in that ADR and is cited rather than restated.

Four things change, and each closes something the previous shape left open.

## 1. A job names its run relationally, and only a command may create that link

`jobs.workflow_run_id` (D4). A real column rather than `payload->>'run_id'`,
because `jobs.payload` is client-writable on INSERT -- the write guard is
`BEFORE UPDATE` only -- so a payload-borne run id is a forgeable claim rather
than a relational fact. The composite foreign key `(workflow_run_id,
workspace_id)` is the same cross-tenant protection `workflow_step_runs` and
`assets` already carry: without it the link is an unchecked assertion, and the
reconciliation in `job_dispatch.py` would write across a tenant boundary while
looking entirely ordinary.

Two rules compose into a closed door, and **neither is sufficient alone**:

- the INSERT policy forces a direct client INSERT to leave the link `NULL`;
- `ck_jobs_workflow_link_matches_type` then makes `job_type = 'workflow.execute'`
  impossible for such a row, and equally makes any *other* job type carrying a
  link impossible -- so no job may occupy the partial unique key below and block
  a run's legitimate enqueue.

The partial unique index is the final concurrency authority for enqueue: no
function decides whether a second live job may exist, they all attempt the insert
and let PostgreSQL serialise (ADR-006 D11, §Execution Safety part 1).

## 2. Durable step state: a claim that is fenced three ways, and a single-use grant

Four columns on `workflow_step_runs` (D8, D9). A claim identifies *which*
execution owns a non-replayable step; the job id and lease token record *which
delivery of which job* took it, so a settle can prove the owner still holds the
job. `approved_by` carries an approval decision across a process boundary --
today nothing does, which is why asynchronous approval was unimplementable
before this migration (ADR-006 Context fact 9).

`claimed_at`, `approved_at` and `superseded_claim_token` are deliberately **not**
added: none of them enforces anything, and storing a raw superseded fencing token
in a column a future grant could expose is precisely the exposure ADR-006
§Column Necessity refuses.

## 3. The commands, and the login that may invoke them

The runner and a direct Supabase/PostgREST client are **the same database
principal**: `RequestSessionFactory` runs `SET LOCAL ROLE authenticated`, and
PostgREST reaches the database as `authenticated` too. No policy, trigger or
column grant can separate "the runner writing a claim" from "a member writing
one", because there is nothing to separate. So the rule moves into five
`SECURITY DEFINER` commands and the direct write is taken away (D11).

Every function granted to `authenticated` is discoverable at `/rest/v1/rpc`.
Discovery is not execution: each command's **first executable statement** is a
literal equality against the application login, so a direct invocation is
refused with `42501` having touched nothing at all -- no run, no job, no grant,
no claim, no audit row. `session_user` is fixed at authentication and changes
only through `SET SESSION AUTHORIZATION`, which PostgreSQL restricts to
superusers; PostgREST connects as Supabase's `authenticator`, which is neither
a superuser nor a member of `projectone_api`. That is why the guard is a *login*
check rather than a marker: there is nothing to steal, replay or leak, because
the value is asserted by the database at connection time from a credential the
client does not hold (ADR-006 §The Caller-Identity Boundary, I21).

**The login name is a literal in each body.** Never a parameter, a GUC, a table
lookup or an allowlist -- `test_workflow_commands.py` reads the bodies out of
`pg_proc` and fails if that stops being true.

## 4. The grants that make the commands the only path

`authenticated` keeps exactly the `workflow_step_runs` write erasure needs
(`UPDATE (deleted_at)`) and loses every other write. Both fencing tokens leave
its `SELECT` grant, on `workflow_step_runs` and on `jobs` alike: **a fencing
token a client can read is a capability, not a fence.**

A member still sees everything about their workspace's runs and queue -- status,
history, cost, failure detail, who approved -- and can read or write nothing
that fences an execution.

## Lock ordering is uniform, and that is not cosmetic

Every command that takes more than one lock takes them in the same order:
**run, then step, then job**. ADR-006 §Execution Safety lists settlement's locks
in a different order; taking them in two different orders is a deadlock between
a stale worker settling and a replacement admitting, which is a shape this
codebase would meet in production and not in review. The accepted property is
that *every predicate is evaluated with every row already locked*, and that
holds here.

## Rollback destroys enforcement state, and some of it is unrecoverable

See `downgrade`. This is a decision taken with the queue drained, not a routine
operation.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "09a247684df7"
down_revision: str | Sequence[str] | None = "ca213a665ad7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: The job type the workflow handler registers, fixed in three places that must
#: agree: `WorkflowExecutionHandler.job_type`, the CHECK below, and the literal
#: inside every command that enqueues. `test_workflow_commands.py` asserts it.
WORKFLOW_JOB_TYPE = "workflow.execute"

#: `MAX_JOB_ATTEMPTS`, fixed in the function bodies so a caller cannot choose it.
#: Asserted against `app/jobs/contract.py` rather than trusted to have been
#: edited alongside it -- the defect STEP-21 paid for on `assets.kind`.
WORKFLOW_JOB_MAX_ATTEMPTS = 2


# --------------------------------------------------------------- jobs link --

_JOBS_LINK = f"""
ALTER TABLE public.jobs
    -- Which run this job advances. Null for every other job type, and that
    -- pairing is a constraint rather than a convention (see below).
    ADD COLUMN workflow_run_id uuid,

    ADD CONSTRAINT fk_jobs_workflow_run_id_workflow_runs
        FOREIGN KEY (workflow_run_id, workspace_id)
        REFERENCES public.workflow_runs (id, workspace_id) ON DELETE RESTRICT,

    -- Biconditional on purpose. The forward half stops a workflow job existing
    -- with no run to reconcile; the reverse half stops any other job type
    -- occupying the partial unique key below and blocking a run.
    ADD CONSTRAINT ck_jobs_workflow_link_matches_type
        CHECK ((job_type = '{WORKFLOW_JOB_TYPE}') = (workflow_run_id IS NOT NULL));
"""

# Required by `workflow_step_runs.claimed_by_job_id`'s composite foreign key:
# PostgreSQL needs a unique constraint on exactly the referenced pair. `id` is
# already the primary key, so this constrains no data -- the same bookkeeping
# `messages` and `conversations` already carry.
_JOBS_REFERENCED_PAIR = """
ALTER TABLE public.jobs
    ADD CONSTRAINT uq_jobs_id_workspace_id UNIQUE (id, workspace_id);
"""

# One live job per run. `pending` and `running` are the live states; a
# `succeeded` or `dead_lettered` job leaves the set, which is what lets an
# explicit recovery enqueue a replacement.
_LIVE_JOB_INDEX = """
CREATE UNIQUE INDEX uq_jobs_one_live_job_per_workflow_run
    ON public.jobs (workflow_run_id)
    WHERE workflow_run_id IS NOT NULL
      AND deleted_at IS NULL
      AND status IN ('pending', 'running');
"""

# The INSERT policy gains one clause. A workflow job is created only by a
# command, which runs as the table owner and is not bound by this policy.
_JOBS_INSERT_POLICY = """
DROP POLICY jobs_insert_member ON public.jobs;

CREATE POLICY jobs_insert_member ON public.jobs
FOR INSERT TO authenticated
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces())
    AND enqueued_by = auth.uid()
    AND workflow_run_id IS NULL
);
"""

_JOBS_INSERT_POLICY_BEFORE = """
DROP POLICY jobs_insert_member ON public.jobs;

CREATE POLICY jobs_insert_member ON public.jobs
FOR INSERT TO authenticated
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces())
    AND enqueued_by = auth.uid()
);
"""


def _jobs_write_guard(*, with_workflow_run_id: bool) -> str:
    """Return the queue-state write guard, optionally covering the run link.

    Restated in full rather than altered, because a trigger function has no
    `ALTER` that adds one column to a whitelist. The body is `a1b7c3e94f6d`'s
    verbatim, plus one comparison -- and the whitelist shape is what makes every
    column added later immutable by default.
    """
    link = (
        "       OR NEW.workflow_run_id IS DISTINCT FROM OLD.workflow_run_id\n"
        if with_workflow_run_id
        else ""
    )

    return f"""
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
{link}    THEN
        RAISE EXCEPTION 'job % queue state is not client-writable', OLD.id
            USING ERRCODE = '23514',
                  HINT = 'A client may only soft-delete a job. Queue state '
                         'belongs to the worker dispatcher (ADR-005 §5).';
    END IF;

    RETURN NEW;
END;
$$;
"""


# ------------------------------------------------------- step claim + grant --

_STEP_STATE = """
ALTER TABLE public.workflow_step_runs
    -- The durable workflow-layer claim, rotated on every acquisition. A step
    -- holding one is being executed by exactly one execution, and only that
    -- execution may persist a result for it. Never released by elapsed time, by
    -- a replacement worker, or by reconciliation (ADR-006 Q4).
    ADD COLUMN claim_token uuid,

    -- Which job, and which lease of it, owns the claim. The claim token proves
    -- *which* execution; the lease token proves it *still* owns the job -- a
    -- claim whose job has been re-claimed is stale, and the job's current token
    -- alone cannot detect that rotation.
    ADD COLUMN claimed_by_job_id uuid,
    ADD COLUMN claimed_by_lease_token uuid,

    -- The durable, single-use approval grant. Non-null means "granted and
    -- unspent"; admission consumes it. Pinned to `auth.uid()` by the only
    -- function that writes it, so it can never name someone else.
    --
    -- Not a foreign key to `users`, matching `enqueued_by` and `triggered_by`:
    -- the record of who approved should outlive the account that approved.
    ADD COLUMN approved_by uuid,

    -- A claim is all three columns or none of them. Without this, a partial
    -- claim would satisfy predicate (1) and have no lease to check against.
    ADD CONSTRAINT ck_workflow_step_runs_claim_complete
        CHECK (num_nonnulls(claim_token, claimed_by_job_id, claimed_by_lease_token) IN (0, 3)),

    -- A claim may only name a job in the same workspace. The composite shape
    -- for the same reason every other relationship here uses it: RLS sees one
    -- row at a time and cannot check a relationship between two of them.
    ADD CONSTRAINT fk_workflow_step_runs_claimed_by_job_id_jobs
        FOREIGN KEY (claimed_by_job_id, workspace_id)
        REFERENCES public.jobs (id, workspace_id) ON DELETE RESTRICT;
"""

# The whole point of D11, expressed as privileges.
#
# `UPDATE (deleted_at)` is what workspace erasure needs and is all it needs
# (CLAUDE.md §16). `INSERT` goes entirely: a step row is created by admission or
# by settlement, both of which run as the table owner.
#
# The `SELECT` list is stated column by column rather than as "everything except
# two", so a column added later is unreadable by a client until someone decides
# it should be -- the same defaulting choice the write guard's whitelist makes.
_STEP_GRANTS = """
REVOKE INSERT, UPDATE ON public.workflow_step_runs FROM authenticated;
GRANT UPDATE (deleted_at) ON public.workflow_step_runs TO authenticated;

REVOKE SELECT ON public.workflow_step_runs FROM authenticated;
GRANT SELECT (id, workspace_id, run_id, step_index, step_name, status, detail,
              tokens_used, output, started_at, finished_at, created_at,
              updated_at, deleted_at, version, approved_by)
    ON public.workflow_step_runs TO authenticated;
"""

# `jobs` keeps every operational column a member can usefully read: what the job
# is, what state it reached, how many attempts it cost, and why it failed.
#
# Two columns leave, and for two different reasons. `lease_token` is a
# capability: a member who could read it could forge a claim that satisfied the
# lease predicate, which is the whole of ADR-006 §Execution Safety part 2.
# `lease_expires_at` is not a capability -- it is a timestamp, and knowing it
# lets nobody admit or settle anything -- but nothing on the tenant path reads
# it: no router exposes `jobs`, and `JobRepository` selected it into a field no
# caller consumed. It is dropped from both, because the enumerated grant list is
# exactly ADR-006 §D11's, and a column granted "in case" is a column no future
# reader can tell was ever needed. The dispatcher is unaffected: lease arithmetic
# lives entirely on the privileged connection, which is not `authenticated`.
_JOB_GRANTS = """
REVOKE SELECT ON public.jobs FROM authenticated;
GRANT SELECT (id, workspace_id, enqueued_by, job_type, payload, status,
              attempts, max_attempts, claimed_by, claimed_at,
              result, last_error, dead_lettered_at, correlation_id, created_at,
              updated_at, deleted_at, version, finished_at, workflow_run_id)
    ON public.jobs TO authenticated;
"""

_STEP_GRANTS_BEFORE = """
REVOKE ALL ON public.workflow_step_runs FROM authenticated;
GRANT SELECT, INSERT, UPDATE ON public.workflow_step_runs TO authenticated;
"""

_JOB_GRANTS_BEFORE = """
REVOKE ALL ON public.jobs FROM authenticated;
GRANT SELECT, INSERT, UPDATE ON public.jobs TO authenticated;
"""


# ---------------------------------------------------------------- audit log --

_PREVIOUS_ACTIONS = (
    "'workspace.created'",
    "'member.added'",
    "'member.removed'",
    "'member.left'",
    "'ownership.transferred'",
    "'provider_key.stored'",
    "'provider_key.revoked'",
    "'budget.updated'",
)

#: Recovering an interrupted run may cause a second provider charge. That is
#: exactly the consequential action CLAUDE.md §16 requires auditing, and the
#: record is what makes "who decided to pay again, and for which step" a
#: question with an answer.
_ADDED_ACTIONS = ("'workflow.recovered'",)


def _action_constraint(values: Sequence[str]) -> str:
    """Return SQL replacing the audit action CHECK with one accepting `values`."""
    accepted = ",\n            ".join(values)

    return f"""
ALTER TABLE public.audit_log
    DROP CONSTRAINT ck_audit_log_action_valid;

ALTER TABLE public.audit_log
    ADD CONSTRAINT ck_audit_log_action_valid CHECK (action IN (
            {accepted}
    ));
"""


# ------------------------------------------------------------- the commands --

#: The application login every workflow execution command demands.
#:
#: `d7b95c1f4e08` creates this role for the request path and records that
#: Supabase's `authenticator` was **rejected** for it -- "it cannot be
#: provisioned from here... its definition is Supabase's to change". The two
#: logins being different is therefore a decision this repository made and can
#: keep, not an accident of hosting.
APPLICATION_LOGIN = "projectone_api"

#: Refusals these commands raise, so a repository can map an outcome without
#: matching on message text -- a message is prose and drifts; a SQLSTATE is a
#: contract. `42501` and `22023` are PostgreSQL's own and are used where they
#: fit exactly; the `WF0xx` codes name domain refusals PostgreSQL has no code
#: for, in a class PostgreSQL does not use.
SQLSTATE_NOT_FOUND = "WF001"
SQLSTATE_WRONG_STATE = "WF002"
SQLSTATE_APPROVAL_REQUIRED = "WF003"
SQLSTATE_STEP_CLAIMED = "WF004"
SQLSTATE_OWNERSHIP_LOST = "WF005"

# The first executable statement of every command, before any read or write.
#
# Four properties, each deliberate:
#
# - **The login name is a literal.** Never a parameter, a GUC, a table lookup or
#   an allowlist. One equality against one hard-coded name is the whole check.
# - **It runs first.** A direct PostgREST call therefore changes nothing at all,
#   rather than being rolled back after doing work.
# - **`auth.uid()` remains the actor.** `session_user` answers *which process is
#   connected*; `auth.uid()` answers *who is acting*. The guard adds a caller
#   check and does not become the identity.
# - **`session_user`, not `current_user`.** `current_user` is mutable -- that is
#   what `SET LOCAL ROLE` is for, and both the application and PostgREST use it
#   to reach `authenticated`. `session_user` is fixed at authentication and
#   changes only through `SET SESSION AUTHORIZATION`, which is superuser-only.
_GUARD = f"""    IF session_user <> '{APPLICATION_LOGIN}' THEN
        RAISE EXCEPTION
            'workflow execution commands are invocable only by the ProjectOne application login'
            USING ERRCODE = '42501';
    END IF;

    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'workflow execution commands require a verified actor'
            USING ERRCODE = '42501';
    END IF;
"""

_MEMBER_CHECK = """    IF p_workspace_id IS NULL
       OR p_workspace_id NOT IN (SELECT public.app_current_user_workspaces()) THEN
        RAISE EXCEPTION 'the actor holds no live membership in this workspace'
            USING ERRCODE = '42501';
    END IF;
"""


# Tier 1, command 1. Creates the run and its job in one transaction, so the
# transactional enqueue ADR-005 §1 chose a database queue for is preserved: both
# inserts are in the caller's transaction and commit or roll back together.
#
# The caller supplies domain values and nothing else. `job_type`, `max_attempts`,
# the actor, the workspace authority and the relational link are all fixed in
# this body -- there is no parameter through which a caller could name another
# user, register a different handler, or buy itself more attempts.
_START_RUN = f"""
CREATE OR REPLACE FUNCTION public.app_start_workflow_run(
    p_workspace_id uuid,
    p_workflow_type text,
    p_definition_version integer,
    p_project_id uuid,
    p_payload jsonb,
    p_correlation_id text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_run_id uuid;
BEGIN
{_GUARD}
    IF p_workflow_type IS NULL
       OR btrim(p_workflow_type) = ''
       OR char_length(p_workflow_type) > 100 THEN
        RAISE EXCEPTION 'workflow type is not a usable identifier'
            USING ERRCODE = '22023';
    END IF;

    IF p_definition_version IS NULL OR p_definition_version < 1 THEN
        RAISE EXCEPTION 'definition version must be a positive integer'
            USING ERRCODE = '22023';
    END IF;

{_MEMBER_CHECK}
    INSERT INTO public.workflow_runs
        (workspace_id, workflow_type, definition_version, status, project_id, triggered_by)
    VALUES
        (p_workspace_id, p_workflow_type, p_definition_version, 'pending',
         p_project_id, auth.uid())
    RETURNING id INTO v_run_id;

    INSERT INTO public.jobs
        (workspace_id, enqueued_by, job_type, payload, status, max_attempts,
         correlation_id, workflow_run_id)
    VALUES
        (p_workspace_id, auth.uid(), '{WORKFLOW_JOB_TYPE}',
         coalesce(p_payload, jsonb_build_object()), 'pending',
         {WORKFLOW_JOB_MAX_ATTEMPTS}, p_correlation_id, v_run_id);

    RETURN v_run_id;
END;
$$;
"""


# Tier 1, command 2. **The grant and the job are inseparable**, and that is the
# whole reason this is one command rather than two.
#
# A function that merely wrote the grant would leave a run sitting in
# `awaiting_approval` carrying a live entitlement that some later, differently
# authorized path could spend -- an approval that is durable but detached from
# the execution it authorizes. There is no way to obtain one without the other.
#
# Two concurrent calls serialise on the run's `FOR UPDATE` lock; the second sees
# the consumed grant and is refused. The partial unique index is the backstop
# behind that, not the primary mechanism.
_APPROVE_STEP = f"""
CREATE OR REPLACE FUNCTION public.app_approve_workflow_step(
    p_workspace_id uuid,
    p_run_id uuid,
    p_step_index integer,
    p_correlation_id text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_role text;
    v_run_status text;
    v_awaited integer;
    v_approved uuid;
    v_job_id uuid;
BEGIN
{_GUARD}
    v_role := public.app_workspace_role(p_workspace_id);

    IF v_role IS NULL OR v_role NOT IN ('owner', 'admin') THEN
        RAISE EXCEPTION 'approving a workflow step requires the owner or admin role'
            USING ERRCODE = '42501';
    END IF;

    SELECT status INTO v_run_status
      FROM public.workflow_runs
     WHERE id = p_run_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'workflow run not found'
            USING ERRCODE = '{SQLSTATE_NOT_FOUND}';
    END IF;

    IF v_run_status <> 'awaiting_approval' THEN
        RAISE EXCEPTION 'this run is not waiting for an approval'
            USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
    END IF;

    SELECT step_index, approved_by INTO v_awaited, v_approved
      FROM public.workflow_step_runs
     WHERE run_id = p_run_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL
       AND status = 'awaiting_approval'
     ORDER BY step_index
     LIMIT 1
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'this run records no step waiting for an approval'
            USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
    END IF;

    IF v_awaited IS DISTINCT FROM p_step_index THEN
        RAISE EXCEPTION 'this run is not waiting on the step named'
            USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
    END IF;

    IF v_approved IS NOT NULL THEN
        RAISE EXCEPTION 'this step already carries an unspent approval'
            USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
    END IF;

    UPDATE public.workflow_step_runs
       SET approved_by = auth.uid()
     WHERE run_id = p_run_id
       AND workspace_id = p_workspace_id
       AND step_index = v_awaited;

    INSERT INTO public.jobs
        (workspace_id, enqueued_by, job_type, payload, status, max_attempts,
         correlation_id, workflow_run_id)
    VALUES
        (p_workspace_id, auth.uid(), '{WORKFLOW_JOB_TYPE}', jsonb_build_object(),
         'pending', {WORKFLOW_JOB_MAX_ATTEMPTS}, p_correlation_id, p_run_id)
    RETURNING id INTO v_job_id;

    RETURN v_job_id;
END;
$$;
"""


# Tier 1, command 3. Completes the transition one of two ways and **never
# neither**.
#
# A function that merely cleared a stale claim would leave the run `failed` with
# no replacement job and no re-armed gate -- and worse, a cleared claim on a step
# still `running` is exactly the state that lets an automatic redelivery re-enter
# a paid step.
#
# The superseded claim's value is never stored and never logged: a fencing token
# written into an audit table is a value some future grant can expose. The audit
# row records that a claim *was* superseded, which is the fact an auditor needs.
#
# `approved_by` is cleared unconditionally. Admission consumed it, so it should
# already be null -- and if some future path ever left one unspent, a run
# returning to its gate with a live entitlement could not be approved again
# (`app_approve_workflow_step` refuses an unspent grant) and would be stuck.
_RECOVER_RUN = f"""
CREATE OR REPLACE FUNCTION public.app_recover_workflow_run(
    p_workspace_id uuid,
    p_run_id uuid,
    p_step_index integer,
    p_step_requires_approval boolean,
    p_correlation_id text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_run_status text;
    v_step_index integer;
    v_had_claim boolean;
    v_job_id uuid;
BEGIN
{_GUARD}
{_MEMBER_CHECK}
    IF p_step_requires_approval IS NULL THEN
        RAISE EXCEPTION 'recovery must state whether the interrupted step is gated'
            USING ERRCODE = '22023';
    END IF;

    SELECT status INTO v_run_status
      FROM public.workflow_runs
     WHERE id = p_run_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'workflow run not found'
            USING ERRCODE = '{SQLSTATE_NOT_FOUND}';
    END IF;

    IF v_run_status <> 'failed' THEN
        RAISE EXCEPTION 'only a failed run can be recovered'
            USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
    END IF;

    SELECT step_index, claim_token IS NOT NULL
      INTO v_step_index, v_had_claim
      FROM public.workflow_step_runs
     WHERE run_id = p_run_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL
       AND status <> 'completed'
     ORDER BY step_index
     LIMIT 1
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'this run records no incomplete step to recover'
            USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
    END IF;

    IF v_step_index IS DISTINCT FROM p_step_index THEN
        RAISE EXCEPTION 'the step named is not the one this run stopped on'
            USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
    END IF;

    UPDATE public.workflow_step_runs
       SET claim_token = NULL,
           claimed_by_job_id = NULL,
           claimed_by_lease_token = NULL,
           approved_by = NULL,
           status = CASE WHEN p_step_requires_approval
                         THEN 'awaiting_approval' ELSE 'failed' END,
           detail = CASE WHEN p_step_requires_approval
                         THEN 'Waiting for approval before this step runs'
                         ELSE 'This step stopped before it finished and can be run again' END,
           finished_at = NULL
     WHERE run_id = p_run_id
       AND workspace_id = p_workspace_id
       AND step_index = v_step_index;

    IF p_step_requires_approval THEN
        UPDATE public.workflow_runs
           SET status = 'awaiting_approval',
               detail = 'This run stopped before it finished and needs approving again',
               finished_at = NULL
         WHERE id = p_run_id AND workspace_id = p_workspace_id;
    ELSE
        UPDATE public.workflow_runs
           SET status = 'pending',
               detail = 'This run stopped before it finished and has been queued to continue',
               finished_at = NULL
         WHERE id = p_run_id AND workspace_id = p_workspace_id;

        INSERT INTO public.jobs
            (workspace_id, enqueued_by, job_type, payload, status, max_attempts,
             correlation_id, workflow_run_id)
        VALUES
            (p_workspace_id, auth.uid(), '{WORKFLOW_JOB_TYPE}', jsonb_build_object(),
             'pending', {WORKFLOW_JOB_MAX_ATTEMPTS}, p_correlation_id, p_run_id)
        RETURNING id INTO v_job_id;
    END IF;

    INSERT INTO public.audit_log
        (workspace_id, actor_id, action, target_id, detail)
    VALUES
        (p_workspace_id, auth.uid(), 'workflow.recovered', p_run_id,
         jsonb_build_object(
             'step_index', v_step_index,
             'superseded_claim', v_had_claim,
             'requires_approval', p_step_requires_approval,
             'job_id', v_job_id
         ));

    RETURN v_job_id;
END;
$$;
"""


# Tier 2, command 1. **Every step passes through here**, whatever its
# replayability or gating -- which is what makes approval consumption
# independent of the claim, so a step that is gated *and* replayable still
# spends its grant exactly once.
#
# The locks make steps 1-5 one indivisible decision: two executions serialise on
# the run row, and the second sees the committed result of the first. That is
# `c8f1a3d54e29`'s conditional-claim property, reached through a lock rather
# than an upsert predicate because this function must also read `jobs`.
#
# **This commits before the provider is called.** The long work then runs with
# no row locked and no claim decision pending, which is ADR-005 §4's transaction
# shape and the reason a claim is durable rather than held in a transaction.
_ADMIT_STEP = f"""
CREATE OR REPLACE FUNCTION public.app_admit_workflow_step(
    p_workspace_id uuid,
    p_run_id uuid,
    p_step_index integer,
    p_step_name text,
    p_requires_approval boolean,
    p_replayable boolean,
    p_job_id uuid,
    p_lease_token uuid
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_run_status text;
    v_step_status text;
    v_claim uuid;
    v_approved uuid;
    v_job_status text;
    v_job_lease uuid;
    v_job_run uuid;
    v_job_actor uuid;
BEGIN
{_GUARD}
    IF p_step_index IS NULL OR p_step_index < 0 THEN
        RAISE EXCEPTION 'step index must be a non-negative integer'
            USING ERRCODE = '22023';
    END IF;

    IF p_step_name IS NULL
       OR btrim(p_step_name) = ''
       OR char_length(p_step_name) > 100 THEN
        RAISE EXCEPTION 'step name is not a usable identifier'
            USING ERRCODE = '22023';
    END IF;

    IF p_requires_approval IS NULL OR p_replayable IS NULL THEN
        RAISE EXCEPTION 'admission must state approval and replayability'
            USING ERRCODE = '22023';
    END IF;

{_MEMBER_CHECK}
    -- 1. The run. Locked first, and every command that takes more than one lock
    -- takes them in this order -- run, step, job -- so an admission and a
    -- settlement racing each other queue rather than deadlock.
    SELECT status INTO v_run_status
      FROM public.workflow_runs
     WHERE id = p_run_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'workflow run not found'
            USING ERRCODE = '{SQLSTATE_NOT_FOUND}';
    END IF;

    IF v_run_status IN ('completed', 'failed') THEN
        RAISE EXCEPTION 'this run has already reached a terminal state'
            USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
    END IF;

    -- 2. The step, created if this is its first admission.
    SELECT status, claim_token, approved_by
      INTO v_step_status, v_claim, v_approved
      FROM public.workflow_step_runs
     WHERE run_id = p_run_id
       AND workspace_id = p_workspace_id
       AND step_index = p_step_index
       AND deleted_at IS NULL
     FOR UPDATE;

    IF NOT FOUND THEN
        INSERT INTO public.workflow_step_runs
            (workspace_id, run_id, step_index, step_name, status)
        VALUES
            (p_workspace_id, p_run_id, p_step_index, p_step_name, 'pending');

        v_step_status := 'pending';
        v_claim := NULL;
        v_approved := NULL;
    END IF;

    -- 3. The job, under a share lock so a concurrent claim cannot rotate the
    -- lease between this check and the write below.
    SELECT status, lease_token, workflow_run_id, enqueued_by
      INTO v_job_status, v_job_lease, v_job_run, v_job_actor
      FROM public.jobs
     WHERE id = p_job_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL
     FOR SHARE;

    IF NOT FOUND
       OR v_job_status <> 'running'
       OR v_job_lease IS DISTINCT FROM p_lease_token
       OR v_job_run IS DISTINCT FROM p_run_id
       OR v_job_actor IS DISTINCT FROM auth.uid() THEN
        RAISE EXCEPTION 'this execution no longer holds the job it is running'
            USING ERRCODE = '{SQLSTATE_OWNERSHIP_LOST}';
    END IF;

    -- 4. The approval grant is consumed here, at admission, and not at claim
    -- time -- so a gated step that is also replayable spends its grant once.
    IF p_requires_approval AND v_approved IS NULL THEN
        RAISE EXCEPTION 'this step needs a fresh approval before it can run'
            USING ERRCODE = '{SQLSTATE_APPROVAL_REQUIRED}';
    END IF;

    -- 5. The claim, for a step whose execution has an external effect.
    IF p_replayable THEN
        v_claim := NULL;
    ELSE
        IF v_claim IS NOT NULL THEN
            RAISE EXCEPTION 'this step is already held by another execution'
                USING ERRCODE = '{SQLSTATE_STEP_CLAIMED}';
        END IF;

        IF v_step_status NOT IN ('pending', 'awaiting_approval', 'failed') THEN
            RAISE EXCEPTION 'this step is not in a state that can be claimed'
                USING ERRCODE = '{SQLSTATE_WRONG_STATE}';
        END IF;

        v_claim := gen_random_uuid();
    END IF;

    UPDATE public.workflow_step_runs
       SET status = 'running',
           step_name = p_step_name,
           detail = NULL,
           started_at = coalesce(started_at, now()),
           finished_at = NULL,
           claim_token = v_claim,
           claimed_by_job_id = CASE WHEN v_claim IS NULL THEN NULL ELSE p_job_id END,
           claimed_by_lease_token = CASE WHEN v_claim IS NULL THEN NULL ELSE p_lease_token END,
           approved_by = CASE WHEN p_requires_approval THEN NULL ELSE approved_by END
     WHERE run_id = p_run_id
       AND workspace_id = p_workspace_id
       AND step_index = p_step_index;

    RETURN v_claim;
END;
$$;
"""


# Tier 2, command 2. Three predicates, all evaluated with every row already
# locked:
#
#   (1) the step's `claim_token` is the caller's;
#   (2) the caller still holds the job, and its lease has not rotated;
#   (3) the run has not already been terminally reconciled.
#
# Expressing this as one `UPDATE ... WHERE EXISTS (SELECT ... FROM jobs ...)`
# is one *statement* but not one atomic *condition*: the subquery is evaluated
# at the statement snapshot and never re-checked, so a concurrent claim could
# rotate `lease_token` between snapshot and write and a stale settle would pass.
# `FOR SHARE` on the job is what closes that window.
#
# **Returning false means ownership was lost.** The caller writes nothing, logs
# why, and stops. It does not retry, does not fail the run, and does not touch
# the step row -- the claim is the record of what was in flight, and erasing it
# would both destroy that evidence and re-open the duplicate call.
#
# A replayable step settles with a null claim token, which makes (1) trivially
# true and keeps (2) and (3): a replayable step is still not writable by an
# execution that has lost its job or whose run is already reconciled.
_SETTLE_STEP = f"""
CREATE OR REPLACE FUNCTION public.app_settle_workflow_step(
    p_workspace_id uuid,
    p_run_id uuid,
    p_step_index integer,
    p_step_name text,
    p_status text,
    p_detail text,
    p_output jsonb,
    p_tokens_used integer,
    p_job_id uuid,
    p_lease_token uuid,
    p_claim_token uuid
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_run_status text;
    v_claim uuid;
    v_claim_job uuid;
    v_claim_lease uuid;
    v_job_status text;
    v_job_lease uuid;
    v_job_run uuid;
    v_job_actor uuid;
BEGIN
{_GUARD}
    IF p_status IS NULL OR p_status NOT IN
        ('pending', 'running', 'awaiting_approval', 'completed', 'failed', 'skipped') THEN
        RAISE EXCEPTION 'step status is not one this table accepts'
            USING ERRCODE = '22023';
    END IF;

    IF p_step_index IS NULL OR p_step_index < 0 THEN
        RAISE EXCEPTION 'step index must be a non-negative integer'
            USING ERRCODE = '22023';
    END IF;

    IF p_step_name IS NULL
       OR btrim(p_step_name) = ''
       OR char_length(p_step_name) > 100 THEN
        RAISE EXCEPTION 'step name is not a usable identifier'
            USING ERRCODE = '22023';
    END IF;

    IF p_tokens_used IS NULL OR p_tokens_used < 0 THEN
        RAISE EXCEPTION 'tokens used must be a non-negative integer'
            USING ERRCODE = '22023';
    END IF;

{_MEMBER_CHECK}
    -- Predicate (3), and the first of the three locks. Run, step, job -- the
    -- same order admission takes them in.
    SELECT status INTO v_run_status
      FROM public.workflow_runs
     WHERE id = p_run_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL
     FOR UPDATE;

    IF NOT FOUND OR v_run_status IN ('completed', 'failed') THEN
        RETURN false;
    END IF;

    SELECT claim_token, claimed_by_job_id, claimed_by_lease_token
      INTO v_claim, v_claim_job, v_claim_lease
      FROM public.workflow_step_runs
     WHERE run_id = p_run_id
       AND workspace_id = p_workspace_id
       AND step_index = p_step_index
       AND deleted_at IS NULL
     FOR UPDATE;

    IF NOT FOUND THEN
        -- A claim that names a row which does not exist is not this caller's.
        IF p_claim_token IS NOT NULL THEN
            RETURN false;
        END IF;

        INSERT INTO public.workflow_step_runs
            (workspace_id, run_id, step_index, step_name, status)
        VALUES
            (p_workspace_id, p_run_id, p_step_index, p_step_name, 'pending');

        v_claim := NULL;
        v_claim_job := NULL;
        v_claim_lease := NULL;
    END IF;

    -- Predicate (1).
    IF v_claim IS DISTINCT FROM p_claim_token THEN
        RETURN false;
    END IF;

    -- Predicate (2).
    SELECT status, lease_token, workflow_run_id, enqueued_by
      INTO v_job_status, v_job_lease, v_job_run, v_job_actor
      FROM public.jobs
     WHERE id = p_job_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL
     FOR SHARE;

    IF NOT FOUND
       OR v_job_status <> 'running'
       OR v_job_lease IS DISTINCT FROM p_lease_token
       OR v_job_run IS DISTINCT FROM p_run_id
       OR v_job_actor IS DISTINCT FROM auth.uid() THEN
        RETURN false;
    END IF;

    IF v_claim IS NOT NULL
       AND (v_claim_job IS DISTINCT FROM p_job_id
            OR v_claim_lease IS DISTINCT FROM p_lease_token) THEN
        RETURN false;
    END IF;

    UPDATE public.workflow_step_runs
       SET status = p_status,
           step_name = p_step_name,
           detail = p_detail,
           tokens_used = p_tokens_used,
           -- `coalesce` so a later write carrying no output does not erase one
           -- an earlier write stored, matching the upsert this replaces.
           output = coalesce(p_output, output),
           started_at = CASE WHEN p_status = 'running'
                             THEN coalesce(started_at, now()) ELSE started_at END,
           finished_at = CASE WHEN p_status IN ('completed', 'failed', 'skipped')
                              THEN now() ELSE finished_at END,
           claim_token = NULL,
           claimed_by_job_id = NULL,
           claimed_by_lease_token = NULL
     WHERE run_id = p_run_id
       AND workspace_id = p_workspace_id
       AND step_index = p_step_index;

    RETURN true;
END;
$$;
"""


#: Every command's signature, for the grant statements and for the tests that
#: read `pg_proc`. One list, so a command cannot be added without its
#: containment being written in the same edit.
COMMAND_SIGNATURES: tuple[str, ...] = (
    "public.app_start_workflow_run(uuid, text, integer, uuid, jsonb, text)",
    "public.app_approve_workflow_step(uuid, uuid, integer, text)",
    "public.app_recover_workflow_run(uuid, uuid, integer, boolean, text)",
    "public.app_admit_workflow_step(uuid, uuid, integer, text, boolean, boolean, uuid, uuid)",
    "public.app_settle_workflow_step("
    "uuid, uuid, integer, text, text, text, jsonb, integer, uuid, uuid, uuid)",
)

# `REVOKE ... FROM PUBLIC` does **not** cover `anon` in this database --
# `c4f21a86b3de` proved that against a real one -- so `anon` and `service_role`
# are named. `authenticated` is the one role that must hold EXECUTE, because the
# application and the worker both reach the database as it; the `session_user`
# guard inside each body is what separates them from a PostgREST caller who
# holds the identical role.
_COMMAND_GRANTS = "\n".join(
    f"""
REVOKE ALL ON FUNCTION {signature} FROM PUBLIC;
REVOKE ALL ON FUNCTION {signature} FROM anon;
REVOKE ALL ON FUNCTION {signature} FROM service_role;
GRANT EXECUTE ON FUNCTION {signature} TO authenticated;
"""
    for signature in COMMAND_SIGNATURES
)

_DROP_COMMANDS = "\n".join(
    f"DROP FUNCTION IF EXISTS {signature};" for signature in COMMAND_SIGNATURES
)


def upgrade() -> None:
    """Add the run link, the durable step state, the five commands and their grants."""
    op.execute(_JOBS_LINK)
    op.execute(_JOBS_REFERENCED_PAIR)
    op.execute(_LIVE_JOB_INDEX)
    op.execute(_JOBS_INSERT_POLICY)
    op.execute(_jobs_write_guard(with_workflow_run_id=True))

    op.execute(_STEP_STATE)

    op.execute(_action_constraint(_PREVIOUS_ACTIONS + _ADDED_ACTIONS))

    op.execute(_START_RUN)
    op.execute(_APPROVE_STEP)
    op.execute(_RECOVER_RUN)
    op.execute(_ADMIT_STEP)
    op.execute(_SETTLE_STEP)
    op.execute(_COMMAND_GRANTS)

    # Last, deliberately. Until the commands exist there is no path that could
    # write the state these grants take away, so narrowing earlier would leave a
    # window in which a step could be recorded by nothing at all.
    op.execute(_STEP_GRANTS)
    op.execute(_JOB_GRANTS)


def downgrade() -> None:
    """Remove the commands, the columns and the narrowed grants.

    **Referential integrity survives; enforcement state does not, and some of
    what is destroyed is unrecoverable.** Calling this reversible would be
    wrong, so it is spelled out:

    **Restoring the broad `authenticated` grants** destroys the isolation itself.
    Every column becomes client-writable again and the forgery paths reopen --
    **while the code still trusts `approved_by`**, which is strictly worse than
    before this migration, because now something depends on it.

    **Dropping `approved_by`** destroys every unspent approval grant in flight.
    Runs waiting at a gate lose the record that they were approved and must be
    approved again. The history survives in `audit_log`; the entitlement does
    not.

    **Dropping the three claim columns** destroys all fencing evidence for steps
    in flight, and with it the duplicate-execution protection. A step that was
    safely stranded becomes an ordinary `running` row that a redelivery will
    re-enter -- **re-invoking a provider that has already been paid**.

    **Dropping `workflow_run_id`** destroys reconciliation and the live-job
    uniqueness guard. Any workflow job still queued loses the only thing naming
    its run, and `ON DELETE RESTRICT` refuses while one exists.

    **A downgrade taken while any step is claimed converts a deliberately
    stranded run into an automatically replayable one.** That is a cost event,
    not a schema event: it is a decision, taken with the queue drained.

    The audit vocabulary narrows on the way down, so any `workflow.recovered`
    row would fail the recreated CHECK. That is correct rather than a flaw -- a
    downgrade that silently dropped audit rows to make itself succeed would
    destroy exactly the records the table exists to keep, and an operator
    hitting it needs to decide what happens to them.
    """
    op.execute(_STEP_GRANTS_BEFORE)
    op.execute(_JOB_GRANTS_BEFORE)

    op.execute(_DROP_COMMANDS)

    op.execute(
        """
        ALTER TABLE public.workflow_step_runs
            DROP COLUMN IF EXISTS claim_token,
            DROP COLUMN IF EXISTS claimed_by_job_id,
            DROP COLUMN IF EXISTS claimed_by_lease_token,
            DROP COLUMN IF EXISTS approved_by;
        """
    )

    op.execute(_jobs_write_guard(with_workflow_run_id=False))
    op.execute(_JOBS_INSERT_POLICY_BEFORE)
    op.execute("DROP INDEX IF EXISTS public.uq_jobs_one_live_job_per_workflow_run;")
    op.execute(
        """
        ALTER TABLE public.jobs
            DROP CONSTRAINT IF EXISTS uq_jobs_id_workspace_id,
            DROP CONSTRAINT IF EXISTS ck_jobs_workflow_link_matches_type,
            DROP CONSTRAINT IF EXISTS fk_jobs_workflow_run_id_workflow_runs,
            DROP COLUMN IF EXISTS workflow_run_id;
        """
    )

    op.execute(_action_constraint(_PREVIOUS_ACTIONS))
