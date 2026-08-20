---
title: STEP-31 Workflow Async Execution
category: Development/Build Step
status: draft
version: "3.0"
last_updated: 2026-08-20
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-31
step_status: In Progress
detail_level: full
phase: "Platform Substrate"
---

# STEP-31 — Workflow Async Execution

**Status:** In Progress
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** full — expanded 2026-08-17 by [[STEP-30 Async Job Infrastructure]]; **readiness contract re-synchronized 2026-08-20 against the accepted [[ADR-006 Workflow Async Execution and Run Reconciliation]]**, which corrected several statements this note made before that ADR existed.

## Objective

Move workflow runs off the request path and onto the worker, without changing what a run means.

## Why This Step Exists Now

[[STEP-22 Minimum Workflow Engine]] built a runner that is deterministic, resumable and versioned but **synchronous**: every step executes inside the HTTP request that started it. A multi-minute render cannot be a workflow under that model, and [[STEP-32 Media Processing Pipeline]] onward are blocked on it.

[[STEP-30 Async Job Infrastructure]] removed the reason it could not change. The queue, the worker, the tenant boundary and the retry ceiling all exist and are proven; what does not exist is a handler that drives a run.

## Dependencies

- [[STEP-30 Async Job Infrastructure]] — the queue, the worker, and the contract this step writes its first real handler against.
- **[[ADR-006 Workflow Async Execution and Run Reconciliation]] — accepted 2026-08-20, and binding on every task below.** It supersedes [[ADR-005 Async Job Queue and Worker Execution Model]] §5 constraints 1 and 2 only; every other ADR-005 decision, tenant protection, retry ceiling, the at-least-once model and the 60-request composed ceiling carry forward unchanged. **ADR-006 is the authority for workflow reconciliation; ADR-005 is the historical record of the queue.**

## Inherited from STEP-30, as corrected by ADR-006

Recorded during synchronization against what was built, then corrected on 2026-08-20 where the accepted ADR contradicts it.

- **The infrastructure is complete and proven on a probe.** `app/jobs/` holds the contract, registry, handler ABC and worker; `app/repositories/job_dispatch.py` holds the bounded cross-tenant dispatcher. The only registered handler is `TenantProbeHandler`.
- **A handler receives `JobContext`, and its only database access is `tenant_session()`.** The handler builds its repository and its definition per unit of work inside a session rather than holding one. ADR-006 adds `lease_token` and `workflow_run_id` to that context; it adds no connection and no privilege.
- **`WorkflowStep` implementations close over request-scoped services**, so the handler builds its definition inside the job's tenant context.
- **Handlers declare `max_attempts` explicitly**, bounded to `MAX_JOB_ATTEMPTS` (2). The 60-request composed ceiling is unchanged and must stay computed from its three factors.
- **A job whose actor lost workspace membership fails terminally, before the handler runs** — and under ADR-006 D5 that job's run is now reconciled to `failed` in the same commit, so it no longer strands.

### Correction: `next_step_index` alone does **not** make this handler duplicate-safe

**The previous version of this note said it did. That was wrong, and shipping against it would have been a defect.** `next_step_index` makes a *sequential* redelivery resume rather than restart — a delivery that begins after the previous one stopped. It says nothing about two deliveries alive at once, which is exactly what a lapsed job lease creates ([[ADR-005 Async Job Queue and Worker Execution Model]] §6 says so in its own words). Two workers would both enter the same incomplete step, both call the provider, both be billed, and the step upsert would leave no trace that it happened.

ADR-005 §6 already required the remedy — "any handler performing a non-idempotent external action must guard it with its own durable claim" — and this step is where the workflow handler discharges it.

### Four distinct problems, four different answers

| Problem | Mechanism | Guarantee |
|---|---|---|
| **Duplicate enqueue** — two requests create two jobs for one run | partial unique index on `jobs.workflow_run_id`, plus the INSERT policy and type/link CHECK | no two live jobs for one run |
| **Replayable-step redelivery** — a pure step runs twice | none needed; the step declares `replayable = True` | duplicate execution has no external effect |
| **Non-replayable redelivery** — two executions in one paid step | durable step claim + three-predicate fenced settlement | at most one execution can *persist* the step |
| **Provider completed before persistence** — the worker died after the call was billed | **nothing closes this** | no automatic re-invocation; a deliberate recovery may repeat the call |

**The fourth is a stated residual, not a gap to design away.** It closes only with provider-side idempotency keys, which ADR-005 §Scope Boundaries leaves open and ADR-006 does not reopen. **There is no exactly-once provider execution, and nothing in this step may claim one.**

### What automatic redelivery does and does not do

- **Automatic redelivery resumes replayable work only.** A worker interrupted between steps, or inside a replayable step, is re-delivered and continues from the last completed checkpoint with no user involvement.
- **An interrupted claimed non-replayable step fails safely.** The replacement worker acquires nothing, calls nothing, writes nothing to the step, and is **terminally interrupted** — dead-lettered, with the run reconciled to `failed` in the same statement. It must **never** settle `succeeded`: it cannot prove the claim holder is dead, and a false success would leave a succeeded job, a `running` run and nothing able to advance it.
- **Recovery is explicit.** The user resumes, and execution continues **from the last completed checkpoint** — not from the beginning. Claims protecting non-replayable steps have **no expiry and are never stolen or auto-released** (ADR-006 Q4).
- **It is therefore not true that every interrupted workflow automatically resumes**, and this note no longer says so. The narrowing is required by ADR-005 §6 and by [[CLAUDE|CLAUDE.md]] §40 — a platform that silently re-spends a user's money to avoid showing them a failure has made the user's decision for them.

### Approval must become durable domain state

**Approval is persisted nowhere today.** `WorkflowRunner.approve` passes `approved=True` as an in-memory parameter and logs `approved_by`; no column, no row, no record. Synchronously that is fine — the approving request *is* the executing request. **Asynchronously the decision must cross a process boundary, and there is nothing durable to carry it, so this step cannot ship without adding one.**

- The grant is **single-use domain state** on the step row, pinned to `auth.uid()`, and **consumed at admission** — not at claim time, so a step that is gated *and* replayable still spends its grant exactly once.
- **Approval is never inferred from `jobs.payload`.** The payload is client-writable on INSERT and carries no authority; it identifies which run to advance and nothing else. **The handler derives its run target from `jobs.workflow_run_id`.**
- An interrupted gated step has already spent its grant, so continuing requires a **fresh** approval from an owner or admin.

## Scope

- Starting a run, approving a step and resuming a run all **enqueue** rather than execute inline, and all answer `202 Accepted` with a `Location` header.
- A workflow job handler that drives the existing `WorkflowRunner` to completion, pause or failure.
- **`jobs.workflow_run_id`** — nullable column, composite tenant-safe foreign key, partial unique live-job index, INSERT policy requiring `NULL`, and a CHECK tying `job_type = 'workflow.execute'` to a non-null link in both directions.
- **A protected workflow-job enqueue path.** A direct authenticated INSERT must never be able to create a workflow-linked job.
- **Five `SECURITY DEFINER` commands** — `app_start_workflow_run`, `app_approve_workflow_step`, `app_recover_workflow_run` (complete domain transitions) and `app_admit_workflow_step`, `app_settle_workflow_step` (worker internals fenced by tokens no client can read).
- **The immutable `session_user = 'projectone_api'` caller boundary**, checked as a literal before any read or write in all five commands.
- Durable, single-use approval as domain state.
- Durable step claims for non-replayable steps, with three-predicate fenced settlement and no expiry.
- **All-dead-letter reconciliation:** every dead-lettered job carrying a `workflow_run_id` marks its run `failed` in the same statement, never overwriting `completed` or `failed`.
- Explicit user recovery from an interrupted non-replayable step.
- Execution budgets, ceilings and the approval gate behaving exactly as they do synchronously.

## Out of Scope

- No branching, parallelism or scheduling — [[STEP-51 Workflow Branching]], [[STEP-52 Workflow Parallel Execution]], [[STEP-74 Workflow Scheduling and Triggers]].
- No new workflow type, and no change to what the existing definition does.
- No change to `WorkflowRunner`'s execution semantics. It is already resumable; this step drives it.
- **No notification of completion** — [[STEP-34 Notifications Domain]]. A user watching a run finish is a different problem, and this step leaves polling as the answer.
- No new queue capability. If this step wants something the queue does not have, that is a finding to report, not a widening.

## Surfaces Affected

**Database:** one migration adding `jobs.workflow_run_id` (FK, partial unique index, INSERT policy, type/link CHECK, write-guard whitelist entry); four columns on `workflow_step_runs` (`claim_token`, `claimed_by_job_id`, `claimed_by_lease_token`, `approved_by`); the five `SECURITY DEFINER` commands with `SET search_path = ''`, PUBLIC and `anon` revoked by name, `EXECUTE` to `authenticated` only; and the grant narrowing that removes direct client write access to execution state and removes every fencing token from client `SELECT` grants.

**Backend:** `app/jobs/handlers.py`, `registry.py`, `contract.py` (`JobContext` gains `lease_token` and `workflow_run_id`), `worker.py`; `app/repositories/workflows.py` and `job_dispatch.py`; `app/routers/workflows.py`; `app/workflows/models.py` (`WorkflowStep.replayable`, defaulting to `False`; `StepInterruptedError`), `runner.py` and `agents.py` (`ValidateProjectStep` and `QualityCheckStep` declare `replayable = True` with their reasoning; `PlanningAgent` inherits `False`).

**Frontend:** run status handling for in-flight runs. `apps/web/src/lib/api.ts` has no start/approve/resume caller and already types `pending`, so no client type changes are expected.

**Documentation correction carried by this step:** `apps/api/app/core/config.py` documented the request connection as `authenticator`; it is `projectone_api`. Corrected during the ADR-006 acceptance transaction.

## Required Documentation

A candidate list, not a reading list ([[Execution Protocol#Context Discipline]] rule 2).

| Document | The question it answers | Likely needed |
|---|---|---|
| `app/jobs/contract.py` | What does a handler receive and owe? | **Yes** — the handler is written against it |
| `app/workflows/runner.py`, `definitions.py` | How is a definition built, and what does it close over? | **Yes** — item 3 above |
| `app/routers/workflows.py` | What does the API return today? | **Yes** — the contract change |
| [[Async Job Execution]] | How does the worker establish tenancy, and what is at-least-once? | Probably — the handler's obligations |
| [[Workflow Execution]] | What does the runner already guarantee? | Only if the runner's behaviour is in doubt |
| [[API Conventions]] | What is the convention for an accepted-but-unfinished response? | **Yes** — item 2 |

## Tasks

Grouped as they will be built. ADR-006 is binding on every one; its decision numbers are cited rather than restated.

### 1. Schema and security functions (one migration)

`jobs.workflow_run_id` with its FK, partial unique index, INSERT-policy `NULL` rule, type/link CHECK and write-guard whitelist entry (D4). Four columns on `workflow_step_runs` (D8, D9). The five commands with their containment and the `session_user` literal guard (D11, §The Caller-Identity Boundary). The grant narrowing that removes direct client write access and hides every fencing token.

### 2. Durable, single-use approval

`approved_by` written only by `app_grant_step_approval`'s successor `app_approve_workflow_step`, pinned to `auth.uid()`, valid for one run, one step index and one `awaiting_approval` state, consumed at **admission** (D9).

### 3. Durable step claims and fenced settlement

`WorkflowStep.replayable` defaulting to `False`. Admission acquires the claim under row locks; settlement requires the claim token, a still-current job lease and a non-terminal run, all evaluated under locks (D8).

### 4. The workflow job handler

Drives `WorkflowRunner` for one run id, taken from `jobs.workflow_run_id` and never from the payload. Declares `max_attempts` explicitly. **Its docstring states duplicate safety as the four-part claim ADR-006 §Execution Safety part 4 requires** — not `next_step_index` alone. A held claim raises `StepInterruptedError`; the job dead-letters and never settles `succeeded`.

### 5. Enqueue on start, approve and resume; `202` and `Location`

All three paths enqueue through the protected commands and answer `202 Accepted`. The existing `limit_by_user("workflow-run", …)` stays on all three and is now the only entrance.

### 6. All-dead-letter reconciliation

Both dead-letter sites carry the reconciliation leg in one statement (D5). It never touches `workflow_step_runs`, so a stale claim survives as evidence and as a fence.

### 7. Explicit recovery

`app_recover_workflow_run` validates a `failed` run, supersedes the stale claim, writes an `audit_log` row **without the raw token**, and then either enqueues a replacement job or re-arms the gate with no job — never neither (D10).

### 8. Tests

Every proof below.

### 9. Documentation

- Update [[Workflow Execution]] and [[Async Job Execution]] where this changes what they describe, **including ADR-005 §5's constraints and §6's duplicate-safety obligation**.
- Update [[API Endpoints]] and [[API Conventions]] for `202` and `Location`.
- Update [[Table - jobs]] and add a table note for `workflow_step_runs`' new columns.
- Remove the "execution is still synchronous" note from [[Workflow Engine]].
- Update this note's status and the [[Build Plan]] index row together.
- ~~Expand [[STEP-32 Media Processing Pipeline]] to full detail.~~ **Withdrawn by the project owner on 2026-08-20**: the [[Build Plan]] pauses after STEP-31 for a complete design milestone, so the next step is not expanded from here.

### 10. Cutover

**One coordinated pre-production cutover: one branch, one PR, one commit on `main`.** The migration and the code land together. There is no production deployment and no rolling fleet to protect, so the expand → cutover → contract sequence protects nothing here and would split one coherent change (ADR-006 §Migration and Rollback Implications).

**A future production rolling deployment is different and the obligation is recorded now:** the grant narrowing must then follow expand → code cutover → contract, because between the second and third steps both code versions must work against one schema ([[CLAUDE|CLAUDE.md]] §13). **That belongs to [[STEP-82 Staging Environment and Deployment Pipeline]] and must not split this step.**

`projectone-dev` is migrated only after merge, once `main` matches the schema.

## Required Tests and Proofs

The full set is [[ADR-006 Workflow Async Execution and Run Reconciliation]] P1–P52, which this step does not restate. Grouped by what each family must establish:

**Async execution and contract (P1–P3, P13)** — a run started via the API reaches its terminal state **in the worker**, proven by persisted state; all three endpoints answer `202` with a working `Location`; approval enqueues rather than executing inline, asserted directly; **a sequential redelivery interrupted between steps or inside a replayable step resumes rather than restarts.**

**Duplicate enqueue (P4, P31–P33, P44)** — two concurrent enqueues produce one job and one 409; **a direct authenticated INSERT cannot set `workflow_run_id`, and cannot construct a workflow execution job through `job_type` plus payload**; cross-workspace links fail at the policy and again at the composite FK; the partial unique index remains the final race-safe authority.

**Non-replayable claims and stale-worker fencing (P14–P18, P20, P28)** — **a stale worker cannot persist**: with the lease rotated, its fenced settle matches zero rows and the step row is unchanged, asserted for each predicate independently; **the replacement worker calls no provider**, asserted on the stub's call count; **it dead-letters and never settles `succeeded`**; the claim survives reconciliation; settlement cannot race the lease.

**Reconciliation (P5–P7, P17)** — every dead-lettered linked job leaves its run `failed`, including the reap path with no worker alive; a run already `completed` or `failed` is never overwritten.

**Approval (P19, P26, P27, P42)** — approval is never inferred; `resume` on an interrupted gated step re-arms the gate, enqueues nothing and calls no provider; the grant is single-use **including for a gated `replayable` step**; a member cannot approve; an owner/admin cannot approve the wrong step, a stale run or a spent grant.

**Caller boundary (P45–P52)** — the application connection is `session_user = projectone_api`, `current_user = authenticated`, `auth.uid()` the intended actor; all five commands work through the repository path; **every command called directly at `/rest/v1/rpc` as a member, an owner/admin and an unrelated-workspace user is refused with no run, job, grant, claim, audit row or status change**, asserted on before/after table snapshots; `session_user` cannot be forged through `SET ROLE`, JWT claims, `set_config`, headers or an RPC parameter; **the route still rate-limits before invoking**, proven by the absence of a new run and job on the 21st call; the worker's access does not widen.

**Boundary guards (P8, P9, P34–P37, P43, P50)** — the dispatcher names `workflow_runs` in exactly two statements of the required shape and never reads it, and never names `workflow_step_runs`; `JobContext` exposes no privileged handle; every command carries `SECURITY DEFINER`, `SET search_path = ''`, schema-qualified references and no dynamic SQL; **the guard test fails if the `session_user` check is removed, becomes a parameter or a GUC, admits `authenticator`, or admits a second login.**

**Governance (P12)** — `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` is still **60**, still computed from its three factors.

**Migration pipeline** — clean-database bootstrap to head, and a full upgrade/downgrade cycle through the existing drill.

## Definition of Done

Workflow runs execute asynchronously with resumability, approvals and ceilings behaving as they did synchronously — **except where ADR-006 deliberately narrowed automatic resumption**, which is part of the definition rather than a shortfall against it: automatic redelivery resumes replayable work, and an interrupted claimed non-replayable step fails safely and waits for an explicit user decision.

Proven by the existing STEP-22 suite plus the proof families above.

Additionally, per [[Execution Protocol#Step Completion]]:

- [ ] The API contract change is documented, and every existing caller updated.
- [ ] No path claims exactly-once provider execution; the residual window is documented where a user or operator can see it.
- [ ] Required CI green, and the manual checklist complete.
- [ ] Owner approval obtained — this step is Critical.
- [ ] Status synchronized between this note and the [[Build Plan]] index.
- [ ] ~~[[STEP-32 Media Processing Pipeline]] expanded to full detail.~~ **Not applicable** — withdrawn by the project owner on 2026-08-20; the [[Build Plan]] pauses after this step for a complete design milestone.

## Outcome

Recorded while building, not after. The Step Completion Record below stays open until the Pull Request merges.

### What was built

**One migration, `09a247684df7`** (`down_revision = ca213a665ad7`, the head):

- `jobs.workflow_run_id` — composite FK to `workflow_runs (id, workspace_id)`, the partial unique live-job index, an INSERT policy requiring `NULL`, a biconditional CHECK tying it to `job_type = 'workflow.execute'`, and an entry on the write-guard whitelist. Plus `uq_jobs_id_workspace_id`, the bookkeeping the step-claim FK needs.
- Four columns on `workflow_step_runs` — `claim_token`, `claimed_by_job_id`, `claimed_by_lease_token`, `approved_by` — with an all-or-none CHECK on the claim and a composite FK from the claim to its job. **`claimed_at`, `approved_at` and a superseded-token column were not added**: none enforces anything, and a raw superseded token in a column is the exposure ADR-006 §Column Necessity refuses.
- **The five commands**, each `SECURITY DEFINER`, `SET search_path = ''`, schema-qualified throughout, no dynamic SQL, `PUBLIC`/`anon`/`service_role` revoked by name, `EXECUTE` to `authenticated` only, and the `session_user = 'projectone_api'` literal as the first executable statement.
- **The grant narrowing**: `authenticated` loses `INSERT` and all but `UPDATE (deleted_at)` on `workflow_step_runs`; both fencing tokens leave its `SELECT` grants on `workflow_step_runs` and `jobs`, and `jobs.lease_expires_at` leaves with them because nothing on the tenant path read it.
- `workflow.recovered` added to the audit action vocabulary.

**Application:**

- `app/workflows/runner.py` — one entry point, `execute`. `start`, `resume` and `approve` are gone: creating a run, granting an approval and recovering an interrupted one are complete domain transitions that must be atomic with the job they enqueue, so they live in the commands. The runner opens one short session per unit of work through a factory rather than holding a connection.
- `app/workflows/execution.py` — new. The worker's composition root, the one place a job's definition is built, and where a step's database work is scoped to a session per call rather than to a connection held across a provider call. `app/core/dependencies.py` imports it, never the reverse, which is what keeps a handler unable to reach `Settings`.
- `app/jobs/handlers.py` — `WorkflowExecutionHandler`, carrying the four-part duplicate-safety statement and what it does not cover.
- `app/repositories/job_dispatch.py` — both dead-letter paths become one data-modifying CTE each, carrying the reconciliation leg.
- `app/routers/workflows.py` — three routes, `202` and `Location`, no job identifier.

### Five things worth recording, found by building rather than by planning

1. **The pause needs a write, and the write needs a command.** Once `authenticated` loses `INSERT` on `workflow_step_runs`, recording a step as `awaiting_approval` is no longer something the runner can do directly. It goes through `app_settle_workflow_step` with a null claim token — which keeps the lease and non-terminal-run predicates on the pause, so a worker that has lost its job cannot park a run it no longer owns. No sixth command was needed.

2. **Every command takes its locks in one order: run, then step, then job.** ADR-006 lists settlement's locks in a different order from admission's. Taking them in two orders is a deadlock between a stale worker settling and a replacement admitting — a shape this codebase would meet in production and not in review. The accepted property is that *every predicate is evaluated with every row already locked*, and that holds.

3. **A gated step held by another execution refuses at the approval check, not the claim check**, because admission consumes the grant before it takes the claim. The outcome is identical — nothing is executed, nothing is written, the job dead-letters and the run is reconciled — and the claim survives untouched.

4. **`app_start_workflow_run` needs a workspace parameter** ADR-006's signature omits, because a membership check needs a workspace to check. Every other value the caller supplies is validated; `job_type`, `max_attempts`, the actor and the relational link are fixed in the body.

5. **The test teardown order became load-bearing again.** `workflow_step_runs` → `jobs` → `workflow_runs`, because a claim names its job and a job names its run, both `ON DELETE RESTRICT`. Deleting jobs first fails whenever a claim survives a test — which is exactly what a deliberately stranded run leaves behind.

### Four conformance defects found by independent review — resolved in ADR-006 v1.7

Every one is a place where the implementation did not do what ADR-006 already required, or where the ADR asserted a property nothing enforced. **None changed an authority boundary, a product decision or a security gate.**

1. **Approval left no history.** §Column Necessity declines an `approved_at` column because "'when' is history and belongs in `audit_log`, which survives consumption" — and nothing wrote that row. Since `approved_by` is cleared at admission, *who approved a gated step vanished the moment the step ran*. `workflow.approved` now joins the audit vocabulary and `app_approve_workflow_step` writes one row in the same transaction as the grant and the job, with `audit_log.created_at` as the approval time and no token of any kind.

2. **A step outcome and its run transition were two transactions**, and a lease can rotate in the gap. Two of the three consequences cost money: a final step committing `completed` under a still-`running` run can be reconciled to `failed` by a replacement, and a failed non-replayable step committing with its claim cleared can be **admitted and re-executed** before the run turns `failed`. Both writes now share one transaction, so the run, step and job locks the settlement takes are held across the pair, and a run transition that cannot be written rolls the step back with it. **No sixth command was needed** — the run update is an ordinary tenant write inside the settlement's own session.

3. **A redelivery of a completed run was dead-lettered.** Refusing to re-execute is right; reporting it as a failure is not — it marks a genuinely completed run as having a failed job against it. It is now an idempotent success: no provider call, no state change, job `succeeded`.

4. **The stored `definition_version` was never checked.** A run parked at a gate across a deploy could continue against a different step sequence, or a step that had stopped being gated or replayable — and `next_step_index` counts completed rows, so an inserted step shifts every index after it. One canonical check now runs before execution, recovery **and** approval. Approval is included because an approval that enqueues work the worker will refuse spends the grant and dead-letters the job. It fails closed with a fixed public-safe message and preserves the run, because what happens to an incompatible run is a product decision.

A fifth finding was structural rather than behavioural: **the two new child foreign keys had no usable index.** `uq_jobs_one_live_job_per_workflow_run` is partial on `status IN ('pending','running')`, so terminal jobs — the ones that accumulate — leave it while `ON DELETE RESTRICT` still has to find them. Two partial indexes now cover every non-null referencing row.

**The Supabase CLI is not installed here**, so the advisor's missing-FK-index check is written out as a test instead, which is the better home: an advisor run is a moment, and a test fails the next migration that forgets one. It reported **six pre-existing unindexed child foreign keys** across `assets`, `conversations`, `messages` and `workflow_runs`, none of them this step's. They are recorded as a pinned baseline rather than fixed — indexing them is unrelated work ([[CLAUDE|CLAUDE.md]] §29) and each deserves its own judgement about write cost — so a *new* one fails while the existing debt is visible instead of invisible.

### Two things ADR-006 said that the implementation read differently — now resolved in ADR-006 v1.6

Reported first, then taken to the owner and written into the ADR rather than left in a Pull Request description. **[[ADR-006 Workflow Async Execution and Run Reconciliation]] is now v1.6, still `accepted`**: an implementation clarification that changes no boundary, removes no predicate and relaxes no gate.

- **I15 said a client may not *read* `approved_by`**, while §D11's grant block — the concrete specification the migration implements — puts it in the client `SELECT` grant, and P24 asserts that it is readable. **v1.6 rewrites I15** to separate the two ideas: the three fencing tokens are unreadable *and* unwritable; `approved_by` is tenant-readable audit metadata and client-unwritable. Nothing is relaxed — the grant block was always the enforced rule. `TestTheGrantsThemselves::test_approval_metadata_is_readable_and_unwritable` states it as one proposition.
- **§D11's `jobs` grant list omits `lease_expires_at`**, which first read as an enumeration slip. Tracing every reader settled it the other way: **no caller consumes it.** No router exposes `jobs`, and `JobRepository` selected the column into a `Job` field nothing read. So least privilege wins — the column leaves the grant, and the dead read leaves the repository and the dataclass with it. The dispatcher is untouched: every lease computation runs on the privileged connection.

**Four normative sections also still named `app_grant_step_approval` and `app_supersede_step_claim`** — the v1.3 functions §D11 consolidated away in v1.4 — in the recovery transaction, the state machine, I10, D9 and four Required Proofs. Someone implementing from those sections would have built the exact half-transitions D11 abolished. v1.6 replaces them with the five accepted commands, keeping the old names only where the line itself says they are superseded, guarded by `TestTheAcceptedCommandNames`. One further inconsistency surfaced in the same pass and is fixed with them: the state machine listed `superseded token` in the audit record two lines below its own `no raw token` caption, contradicting I17.

### Deliberately not built

- **Provider-side idempotency keys.** ADR-005 §Scope Boundaries leaves them open and ADR-006 does not reopen them. **There is no exactly-once provider execution**, and no path added here claims one.
- **A private, unexposed schema for the commands.** Worth adding later as a second layer; rejected as the *primary* mechanism because PostgREST's exposed-schema list is Supabase project configuration rather than repository state, so a test here cannot assert it.
- **Completion notification.** [[STEP-34 Notifications Domain]]. Polling is the answer for now, and the `Location` header is what makes polling a contract rather than a guess.
- **Frontend changes.** `apps/web` already types `pending` and already renders queued runs as "Queued"; there was nothing to change, and ADR-006 predicted as much.

### The connection a step holds — found, measured, closed

**First reported as a known gap, then measured, and the measurement changed the answer.**

The gap as first stated was "a step holds a tenant session across the provider call, and closing it reaches into chat." Two things were wrong with leaving it there. The hold was not merely a connection: `RequestSessionFactory` keeps a **transaction** open for a session's life, because `SET LOCAL ROLE` and the local JWT claim do not survive outside one — so a step was a `projectone_api` backend sitting `idle in transaction` for the length of a provider call, up to `ExecutionBudget`'s 300-second ceiling. And ADR-005 §4 already forbids exactly that ("no transaction is open while the long work runs"), as does `app/repositories/session.py`'s own docstring. It was a conformance defect, not a design tradeoff.

`pg_stat_activity`, observed from a third connection while a real provider call was in flight, showed one `projectone_api` backend `idle in transaction` — and, usefully, showed the privileged spend connection as `idle` rather than mid-transaction.

**The fix is workflow-local and does not touch chat.** Two Protocols name what a step actually needs — `ProjectReader` (one read) and `CredentialReader` (two) — and `app/workflows/execution.py` satisfies them with readers that open a short session per call and close it. The concrete `ProjectRepository` and `ProviderCredentialService` satisfy the same Protocols as written, so the request path is unchanged, and the credential path is still the real service over the real cipher: **BYOK isolation, `auth.uid()` attribution and the RLS policy that answers each lookup are all untouched.** The runner then builds one definition per execution before any session exists, and executes a step with no session wrapper at all.

Measured again: **no `projectone_api` backend exists during the provider call**, and nothing anywhere is mid-transaction. Both are permanent tests, and both were confirmed to fail against the previous shape before being kept.

**What deliberately remains.** `AISpendService.guard` holds one privileged connection for a guarded call rather than opening eight — its own documented decision, held `idle`, and shared identically with chat. Narrowing it is a decision about the AI service, not about workflows, and it is now asserted to stay non-transactional rather than trusted to. The resulting budget is written down in [[Async Job Execution#What a running step occupies]] and `infrastructure/process-model.md`: no application-side pool, one job per worker process, and therefore `N` workers costing at most `N` request-role connections.

### Validation

| Check | Result |
|---|---|
| `ruff check .` / `ruff format --check .` | Passed |
| `mypy app` (strict) | Passed — 94 source files |
| `pytest` against PostgreSQL 17, database tests required | **1264 passed, 4 skipped** (from 1181 — **+83**) |
| `migration_cycle_drill.py` (FA-02) | Passed — 435 schema facts identical after downgrade to base and re-upgrade |
| `backup_restore_drill.py` (FA-03) | Passed — schema and per-workspace data identical after restore |
| `web`: lint, typecheck, test, build | Passed — 324 tests, production build clean |
| `sync-governance-docs.sh --check` | In sync |

The four skips are the opt-in live-R2 integration tests, unchanged by this step.

**Three proof families were added by the pre-publication audit**, on top of the suite above: `TestTheProviderCallHoldsNoTenantConnection` measures `pg_stat_activity` while a real provider call is in flight; `TestTheGrantsThemselves` asserts the privilege state column by column, so a migration that granted columns and then revoked the table would fail loudly rather than silently; and `TestTheAcceptedCommandNames` fails if an abolished v1.3 function name returns to a normative section of ADR-006.

**The new tests split by what only a database can answer.** `test_workflow_commands.py` (59 tests) runs against real PostgreSQL because a fake has no `SECURITY DEFINER`, no `session_user`, no column grant, no partial unique index and no `FOR UPDATE` — it would report success for an implementation that let any member forge an approval. `test_workflow_engine.py` stays offline and asserts sequencing and gating, with its fake extended to model the conditional claim and the three settlement predicates. `test_workflows_api.py` drives the **real worker** alongside the real routes, because the API no longer executes anything and a suite that only drove HTTP would assert that nothing happened.

### Manual test checklist

**Applicable, and performed at the process boundary rather than in a browser.** This step changes a public API contract and adds no browser control: `apps/web` has no caller for start, approval or resume, and the one surface it does render — a queued run — already worked.

What replaces a browser check is real HTTP against a real database with the real worker process driving execution, which is what `test_workflows_api.py` does end to end: a 202 with a `Location` that resolves, a run that reaches its terminal state **in the worker**, an approval that enqueues rather than executing inline, a stranded run that stops instead of paying twice, and a recovery that continues it. Those are the user-facing behaviours, and a browser could not observe the half that matters.

## Risks and Governance Gates

**Critical** — a public API contract change, the multi-tenancy boundary, and database schema. **No new principal is created**: the five commands are `SECURITY DEFINER` functions owned by the existing database owner, which is a constrained command boundary rather than a new identity — and each refuses any caller whose `session_user` is not the application login that already existed. Every one of these is decided in [[ADR-006 Workflow Async Execution and Run Reconciliation]]; the risk here is implementing them incompletely, not re-deciding them.

- **Settling `succeeded` when a claim is found held.** The single most dangerous mistake available in this step: it would leave a succeeded job, a `running` run and nothing able to advance or reconcile it. Dead-letter, always.
- **Releasing a claim on any automatic path.** No expiry, no stealing, and reconciliation must not touch `workflow_step_runs`.
- **A command missing its `session_user` guard**, or the guard becoming a parameter, a GUC or a list. Every command is reachable at `/rest/v1/rpc`; the guard is the only thing between a stranger and a complete domain transition.
- **Approval carried in the job payload.** The payload is client-writable on INSERT. Authorization must come from validated domain state.
- **A definition built outside tenant context.** `definitions.py` already warns a module-level definition is a cross-tenant leak.
- **The ceiling composing differently than stated.** The 60-request bound assumes one job attempt drives one run execution.

## Audit Gaps Closed

**Background / async execution** — *Foundation / Partial, P0*

---

## Navigation

- **Previous:** [[STEP-30 Async Job Infrastructure]]
- **Next:** [[STEP-32 Media Processing Pipeline]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]] · [[ADR-006 Workflow Async Execution and Run Reconciliation]] · [[Async Job Execution]] · [[Workflow Execution]]
