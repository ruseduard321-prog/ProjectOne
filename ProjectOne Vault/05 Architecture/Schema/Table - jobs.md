---
title: Table - jobs
category: Architecture/Schema
status: stable
version: "1.0"
last_updated: 2026-08-17
tags: [database, schema, multi-tenancy, jobs, infrastructure]
aliases: ["jobs", "Job Queue Table", "Async Jobs Table"]
---

# Table - jobs

**The queue.** Created by [[STEP-30 Async Job Infrastructure]] in migration `a1b7c3e94f6d`, against [[ADR-005 Async Job Queue and Worker Execution Model]].

This is the first table that a **process other than the API** writes to, and the only table reached by a deliberately cross-tenant path. Both facts shape almost every decision below.

> [!important] The governing decision is now [[ADR-006 Workflow Async Execution and Run Reconciliation]]
> Accepted 2026-08-20, superseding ADR-005 §5 constraints 1 and 2. [[STEP-31 Workflow Async Execution]] added `workflow_run_id` with its composite foreign key, live-job unique index, INSERT-policy rule and type/link constraint, and narrowed the client `SELECT` grant so `lease_token` is unreadable. All of it is documented below.

## Columns

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | Primary key |
| `created_at` / `updated_at` / `deleted_at` / `version` | | Standard column set ([[Table Conventions]]) |
| `workspace_id` | `uuid` NOT NULL | FK → `workspaces(id)` `ON DELETE RESTRICT`. **Attribution, not the security mechanism** |
| `enqueued_by` | `uuid` NOT NULL | The identity the worker replays. **Not** an FK. Pinned by the INSERT policy |
| `job_type` | `text` NOT NULL | Which registered handler runs it. Not an FK — see below |
| `payload` | `jsonb` NOT NULL | What the handler is given. Opaque to the queue |
| `status` | `text` NOT NULL | CHECK: `pending`, `running`, `succeeded`, `dead_lettered` |
| `attempts` | `integer` NOT NULL | Incremented by the **claim**, never by the settle |
| `max_attempts` | `integer` NOT NULL | CHECK: `1..2` — the accepted composed ceiling |
| `claimed_by` | `text` | Host and pid of the holding worker. Operations detail, not a credential |
| `claimed_at` | `timestamptz` | |
| `lease_expires_at` | `timestamptz` | When this claim lapses |
| `lease_token` | `uuid` | Proof that *this* claim owns the job |
| `result` | `jsonb` | What the handler returned |
| `last_error` | `text` | Why the last attempt failed. Tenant-readable, so it carries no internal detail |
| `dead_lettered_at` | `timestamptz` | |
| `correlation_id` | `text` | The enqueuing request's `X-Request-ID` |
| `finished_at` | `timestamptz` | |
| `workflow_run_id` | `uuid` | Which run this job advances; NULL for every other type. Composite FK → `workflow_runs(id, workspace_id)`. **Immutable and never client-writable** — see below |

## Four states, and why there is no `failed`

```
pending → running → succeeded
                  → pending        (retryable failure, attempts remain)
                  → dead_lettered  (terminal refusal, or attempts exhausted)
```

A job that failed and will be retried **is** pending — that is what pending means. A job that failed and will not be retried is dead-lettered. A `failed` value between them would name a state nothing can be in, and every reader would have to learn which of the two meant "give up".

> [!important] Dead-lettering is an event, not only a status
> [[CLAUDE|CLAUDE.md]] §26 is explicit that a system which can fail in a way nobody notices is an observability gap. Reaching `dead_lettered` emits a logged `job_dead_lettered` event carrying the job id, type, workspace, attempt count and cause — including for jobs retired by the reap, whose worker died and left nothing running to report them.

## `enqueued_by` is the security mechanism

RLS in ProjectOne resolves through `auth.uid()` and `workspace_members`, so a worker with no request has no user — and whatever carries tenancy into it *is* the tenant boundary rather than an implementation detail (ADR-005 §4).

The worker establishes context by calling `RequestSessionFactory.authenticated_as(enqueued_by)`: the same code path, the same role switch, the same claim, subject to the same policies a request meets.

> [!warning] The INSERT policy pins `enqueued_by`, and this is the escalation it closes
> ```sql
> WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces())
>             AND enqueued_by = auth.uid())
> ```
>
> Without the second clause any member could enqueue a job that later executes as **another member's identity** — naming the owner would grant the owner's row visibility on a delayed fuse. The workspace predicate alone does not catch it, because both users are in the same workspace, which is the whole point.
>
> Enqueue is the one place the identity a worker replays is chosen, so it is the one place that choice can be constrained. `test_a_member_cannot_enqueue_work_that_runs_as_someone_else` asserts it.

**A job whose actor lost membership fails terminally.** The policies resolve at execution time, so a revoked user's job would read nothing and fail obscurely. The worker proves the identity *before* invoking any handler and dead-letters the job naming revocation — accepted by the project owner on 2026-08-17 (ADR-005 §4, §7).

## Queue state is not client-writable

`authenticated` needs `UPDATE` for exactly one operation: the soft delete workspace erasure performs. Granting it leaves every other column writable by a tenant, and the consequences are not cosmetic — resetting `attempts` replays a job indefinitely, and setting `status` forges an outcome.

`app_jobs_queue_state_not_client_writable` refuses that, permitting only `deleted_at` (plus `updated_at` and `version`, which `touch_row` maintains). The shape is copied from `app_messages_immutable`, including the whitelist and the `app_` prefix that makes it fire *before* `touch_row`.

> [!danger] It is `SECURITY INVOKER`, unlike `app_messages_immutable`, and the difference is load-bearing
> Inside a `SECURITY DEFINER` function `current_user` is the function's **owner**, so a role test written there reads `postgres` on every call and the guard never fires. It would pass review, pass a casual reading, and protect nothing.
>
> Observed against a real database while writing the migration. Invoker rights make `current_user` the caller's effective role, which is the question being asked. The function reads two records and raises, touching no table, so there was no privilege for it to have needed.

The guard bounds the **client** path only. The dispatcher connects as the table owner and is bounded by ADR-005 §5 instead — one table, three operations, every claim logged — which a trigger cannot express and `tests/test_job_boundary.py` asserts.

## `max_attempts` carries the composed ceiling

CHECK `1..2`, which is ADR-005 §7's accepted job attempt ceiling. It composes to **60 upstream provider requests per enqueue**:

| Layer | Ceiling |
|---|---|
| Provider attempts per provider | 3 |
| Providers in the fallback chain | 2 |
| → upstream requests per `complete()` | **6** |
| Chained AI invocations per run execution | 5 |
| → upstream requests per run execution | **30** |
| Job attempts per enqueue | **2** |
| → **upstream requests per enqueue** | **60** |

The registry refuses an over-ceiling handler at import, which is the readable failure. **The constraint is the guarantee**, because a job row is what actually costs money. `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` is computed from its three factors rather than written as 60, so raising any layer moves it visibly.

## A claim consumes an attempt, including a lease recovery

A job is claimable in two states: `pending`, or `running` with a lapsed lease. The claim increments `attempts` in both cases.

That is deliberate (ADR-005 §6): a worker crash-looping on a job that kills the process would otherwise be unbounded — the one shape where "the process died so it does not count" produces an infinite loop with no error to observe.

**`lease_token` is what makes the recovery survivable.** A lapsed lease means the job becomes claimable *while the original worker may still be running it*, so a superseded worker's late `record_outcome` would otherwise overwrite the state of the worker that legitimately owns it now. The same shape, and the same reasoning, as `messages.claim_token` (`c8f1a3d54e29`).

## The reap: a job whose worker died on its last attempt

A job with attempts exhausted is not claimable, so without a reap it would sit in `running` with a lapsed lease forever — unfinished, invisible, never dead-lettered. The claim operation retires those rows first, in the same transaction, and returns them so the caller logs each one.

This is why the dispatcher's "three statements" is three *operations*, one of which needs two statements to be correct: retiring an unrecoverable job is part of finding the next one.

## `job_type` is not a foreign key

There is no handlers table. Handlers are declared in code (`app/jobs/registry.py`), because a handler is executable Python — the same reasoning as `workflow_runs.workflow_type`. A handlers table would be a second source of truth able to disagree with the code that actually runs, and the disagreement would surface mid-job.

## The SELECT policy does not filter `deleted_at`

The table is soft-deleted by workspace erasure, so that filter would make the erasure impossible — the defect that cost [[STEP-11a Membership Removal Policy]] and [[STEP-19 Settings and BYOK UI]] a step each. Held at creation time, as it now has been for `projects`, `assets` and the two workflow tables.

**A soft-deleted job is not claimable**, because the claim filters `deleted_at IS NULL`. An erasure therefore drains the workspace's queue as well as clearing its rows, which is the correct behaviour: a workspace that asked to be cleared should not have work still running on its behalf.

## Registered for export and erasure

`JobStore` is in `REGISTERED_STORES` in the same change that created the table ([[CLAUDE|CLAUDE.md]] §16). A job is the record of work a workspace asked for out of band — the same class of data as a workflow run, and carrying no retention exception.

The export includes `payload` and `result`, which are the workspace's own content, and deliberately excludes `claimed_by`: which worker process held a job is platform operations detail and names an internal host.

## `workflow_run_id`: a relational fact, not a payload claim

A workflow job names its run in a **column**, and the handler reads its target from there and nowhere else. `payload` was rejected for a decisive reason: it is **client-writable on INSERT** — the write guard is `BEFORE UPDATE` only, and the INSERT policy pins nothing but the workspace and the actor — so a payload-borne run id is a forgeable assertion rather than a relational fact. A job whose payload names a different run advances only the run its column names; the payload is not so much rejected as never consulted.

Three rules compose into a closed door, and **no two of them are sufficient**:

| Rule | What it stops |
|---|---|
| `jobs_insert_member` requires `workflow_run_id IS NULL` | A direct client INSERT occupying the live-job key for a run, blocking every legitimate start, approval and resume for it |
| `ck_jobs_workflow_link_matches_type` — `job_type = 'workflow.execute'` **iff** the link is non-null | A workflow job with no run to reconcile, and any other job type wearing a link |
| `fk_jobs_workflow_run_id_workflow_runs` on `(workflow_run_id, workspace_id)` | A link across a tenant boundary — the protection `workflow_step_runs` and `assets` already use |

`workflow_run_id` is on the write guard's whitelist, so a link cannot be repointed after creation. **Creation is closed by the policy; mutation is closed by the trigger; the pairing is closed by the CHECK.** A workflow job therefore exists only where one of the protected commands created it (see [[Workflow Execution]]).

## The client `SELECT` grant omits `lease_token` and `lease_expires_at`

`authenticated` holds column-level `SELECT` on everything else, including `workflow_run_id`, `claimed_by`, `claimed_at` and `last_error` — a member can still see status, attempts, failure detail and which run a job is for.

**The two omissions are omissions for different reasons, and the difference is worth keeping straight.**

`lease_token` leaves because it is a **capability**: a fence a client can read is not a fence, and a member who could read it could forge a step claim that satisfied the lease predicate ([[ADR-006 Workflow Async Execution and Run Reconciliation]] §Execution Safety).

`lease_expires_at` is not a capability — it is a timestamp, and knowing when a lease ends lets nobody admit, settle or extend anything, all of which need the token. It leaves because **nothing on the tenant path reads it**: no router exposes `jobs`, and `JobRepository` selected it into a field no caller consumed. A privilege with no reader is one nobody can later justify or safely remove. Lease arithmetic is entirely the dispatcher's, on the privileged connection.

The grant is written column by column rather than as "everything except two", so a column added later is unreadable until someone decides it should be — and restoring `lease_expires_at` for a real feature is one line, deliberately taken rather than inherited.

## Indexes

| Index | Purpose |
|---|---|
| `ix_jobs_status_created_at` | The poll. Partial on `deleted_at IS NULL`, so each claim is an index scan returning almost nothing |
| `ix_jobs_workspace_id` | A workspace's own listing |
| `ix_jobs_workspace_id_status` | Filtering that listing by state |
| `uq_jobs_one_live_job_per_workflow_run` | **The final concurrency authority for enqueue.** Unique on `workflow_run_id`, partial on live rows (`pending`, `running`) and `deleted_at IS NULL`. No command decides whether a second live job may exist; they attempt the insert and let PostgreSQL serialise |
| `uq_jobs_id_workspace_id` | Bookkeeping for the composite FK `workflow_step_runs.claimed_by_job_id` needs. Constrains no data — `id` is already the primary key |

`lease_expires_at` is deliberately **not** in the poll index's predicate: it is compared against `now()`, which is not immutable and therefore not indexable in a partial predicate.

## Teardown ordering

Registered in `_WORKSPACE_DEPENDANTS`, and **its position is now load-bearing**. A step row's claim names the job that took it (`fk_workflow_step_runs_claimed_by_job_id_jobs`) and a job names the run it advances (`fk_jobs_workflow_run_id_workflow_runs`); both are `ON DELETE RESTRICT`, so the chain comes apart in one order only:

`workflow_step_runs` → `jobs` → `workflow_runs`

Deleting `jobs` first fails whenever a claim survived a test — which is precisely what a deliberately stranded run leaves behind. See [[Table Conventions#A `RESTRICT` foreign key to `workspaces` is also a test-teardown obligation]].

---

## Navigation

- **Previous:** [[Table - workflow_runs]]
- **Next:** —
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Async Job Execution]] · [[ADR-005 Async Job Queue and Worker Execution Model]] · [[RLS Policy Pattern]] · [[Table Conventions]] · [[Schema Overview]] · [[Table - workflow_runs]]
