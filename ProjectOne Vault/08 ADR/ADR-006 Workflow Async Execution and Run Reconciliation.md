---
title: "ADR-006: Workflow Async Execution and Run Reconciliation"
category: ADR
status: accepted
version: "1.7"
last_updated: 2026-08-21
tags: [adr, decision, backend, api, workflow, jobs, security, database]
adr_number: "0006"
---

# ADR-006: Workflow Async Execution and Run Reconciliation

## Status

**Accepted** — approved by the project owner on 2026-08-20.

This decision is now binding, and [[STEP-31 Workflow Async Execution]] may build against it ([[CLAUDE|CLAUDE.md]] §7). **Changing the caller-identity boundary, the execution-claim model, the approval model, or the cross-tenant reconciliation boundary requires a new ADR that supersedes this one** — this note is not amended in place.

> [!note] v1.6 and v1.7 are corrections, not re-decisions
> **The accepted architecture and authority model are unchanged by both.** v1.6 rewrites wording that contradicted itself. v1.7 goes further in kind but not in authority: it corrects three places where **the implementation did not conform to what this ADR already required**, and states the requirement precisely enough to be testable.
>
> Nothing either version touches is on the list above: no boundary moves, no predicate is removed, no gate is relaxed, and no product decision is revisited. They record what [[STEP-31 Workflow Async Execution]] found while building v1.5, and state the resolutions in the ADR rather than in a Pull Request description the next reader will not open.

### What the owner accepted, explicitly

Drafted and revised through five versions on 2026-08-20, each revision closing a defect the previous one carried. Accepted at v1.5, in these parts:

| # | Accepted |
|---|---|
| 1 | **Q1–Q5** as recorded in §Owner Decisions — reconciliation scope, the tightened boundary test, the concrete `jobs.workflow_run_id`, no claim expiry, and `202 Accepted` throughout. |
| 2 | **Reconciliation of every workflow-linked dead-letter**, not only pre-handler ones, with the guard that never overwrites `completed` or `failed` (D5). |
| 3 | **Five `SECURITY DEFINER` commands** — three complete domain commands and two lease-fenced worker internals (D11). |
| 4 | **The literal `session_user = 'projectone_api'` caller boundary**, checked before any read or write in every command (§The Caller-Identity Boundary). |
| 5 | **Complete atomic start, approve and recover transitions** — no client-reachable half-operation grants, supersedes or enqueues (D11). |
| 6 | **Hidden fencing tokens and three-predicate settlement** — claim token, current job lease, non-terminal run, evaluated under row locks (D8). |
| 7 | **No expiry and no automatic recovery** for claims protecting non-replayable steps (D8, Q4). |
| 8 | **Explicit user recovery** as the only path back into an interrupted paid step (D10). |
| 9 | **One coordinated pre-production cutover** for STEP-31 — one branch, one PR (§Migration and Rollback Implications). |
| 10 | **That any future change to the request-path or worker connection role requires a migration and a superseding ADR revision**, because the accepted login is a literal in five function bodies rather than configuration (I21). |

**No open owner decisions remain.** Every question raised across v1.0–v1.5 is answered in this note; §Owner Decisions records Q1–Q5 and the acceptance conditions on D9 and D11 are met by D11 and §The Caller-Identity Boundary respectively.

### Revision history

**v1.7 — 2026-08-21.** **Conformance correction**, raised by independent review of [[STEP-31 Workflow Async Execution]]. **Status remains `accepted`. No authority boundary, product decision or security gate changes.** Each row below is a place where the implementation failed to do what this ADR already required, or where the ADR asserted a property nothing enforced.

| Input | Change |
|---|---|
| **Approval history was not persisted.** §Column Necessity declines an `approved_at` column because "'when' is history and belongs in `audit_log`, which survives consumption" — but nothing wrote that row. `approved_by` is enforcement state and is cleared at admission, so **the moment an approved step ran, who approved it was gone.** The ADR described a property the schema did not have. | **`workflow.approved` joins the audit vocabulary**, and `app_approve_workflow_step` writes one row in the same transaction as the grant and the job. It records workspace, actor (`auth.uid()`), run, step index and the created job id, and no token of any kind. `audit_log.created_at` is the durable approval time. New **I22**; new proofs **P42–P44**. |
| **A step outcome and its run transition were two transactions.** The runner settled the step, committed, and then moved the run. A job's lease can rotate inside that gap, and two of the three consequences are expensive: a final step committing `completed` under a run still `running` can be reconciled to `failed` by a replacement, and a failed non-replayable step committing with its claim cleared can be **admitted and re-executed by a replacement before the run turns `failed`** — a second charge for work already paid for. | **One transaction.** The run transition is written inside the same session as `app_settle_workflow_step`, so the run, step and job locks that command takes are held across both writes; a run transition that cannot be written rolls the step settlement back with it. **No sixth command was needed.** New **I23**; new proofs **P45–P48**. |
| **A redelivery of a completed run was a failure.** The runner refused re-entry by raising, which dead-letters the job — marking a genuinely completed run as having a failed job against it, with D5's reconciliation the only thing between that and the run being rewritten to `failed`. | **An idempotent success.** No provider call, no state change, and the delivery settles `succeeded`. Refusing to re-execute and reporting failure are different things. New proof **P49**. |
| **The stored definition version was never checked.** A run records `definition_version` and the worker built the current definition without comparing them, while the recovery route read `requires_approval` off the current definition before mutating a failed run. A run parked at a gate across a deploy could continue against a **different step sequence, or a step that had stopped being gated or replayable** — and `next_step_index` counts completed rows, so an inserted step shifts every index after it. | **Checked before every mutation** — execution, recovery **and** approval — failing closed with a fixed public-safe message and preserving the run untouched. Approval is included because an approval that enqueues work the worker will refuse spends the grant and dead-letters the job. New **I24**; new proofs **P50–P53**. |
| **Two new child foreign keys had no usable index.** `uq_jobs_one_live_job_per_workflow_run` is partial on `status IN ('pending','running')`, so terminal jobs — the ones that accumulate — leave it, while `ON DELETE RESTRICT` still has to find them. | Two partial indexes covering every non-null referencing row, `ix_jobs_workflow_run_id_workspace_id` and `ix_workflow_step_runs_claimed_by_job_id_workspace_id`, with downgrade removal. New proof **P54**. |

**v1.6 — 2026-08-21.** Implementation clarification, raised by [[STEP-31 Workflow Async Execution]] while building v1.5. **Status remains `accepted`; the approved architecture and authority model are unchanged.** Three internal inconsistencies are resolved in favour of what v1.5 actually specified, and one grant is decided on evidence rather than left ambiguous.

| Input | Change |
|---|---|
| **I15 forbade what §D11 granted.** I15 said no client-reachable role may *read* `approved_by`; §D11's grant block — the concrete specification the migration implements — lists `approved_by` in the client `SELECT` grant, and P24 asserts that it is readable. Two normative statements, one of them enforceable. | **I15 rewritten.** Fencing state and audit metadata are now separated explicitly: `claim_token`, `claimed_by_lease_token` and `jobs.lease_token` are unreadable and unwritable; `approved_by` is **tenant-readable audit metadata and client-unwritable**. No write restriction and no single-use property is weakened — the grant block was always the enforced rule, and it is now the only rule stated. |
| **§D11's `jobs` grant list omits `lease_expires_at`**, and the omission read as an enumeration slip rather than a decision, because the column is a timestamp rather than a capability. | **Kept out, and now on purpose.** Tracing every reader found none: no router exposes `jobs`, and `JobRepository` selected the column into a `Job` field no caller consumed. Least privilege therefore says revoke, and the dead read is removed with it. The dispatcher is unaffected — every lease computation runs on the privileged connection, which is not `authenticated`. See §The `lease_expires_at` decision. |
| **Two sections still named `app_grant_step_approval` and `app_supersede_step_claim`**, the v1.3 function names §D11 consolidated away in v1.4, in *normative* positions — the recovery transaction, the state machine, I10, D9, and four Required Proofs. A reader implementing from those sections would build functions this ADR abolished. | **Replaced throughout with the five accepted commands.** The old names survive only where they are explicitly described as superseded history: this table, the v1.4 entry, and §D11's account of why the consolidation happened. A documentation guard, `tests/test_workflow_commands.py::TestTheAcceptedCommandNames`, fails if either name returns to a normative section. |
| **The state machine named a token its own caption forbids.** §Concurrency and Recovery State Machine listed `audit_log entry: run, step index, superseded token, actor` two lines below `(audited, no raw token)`, contradicting **I17**. | Corrected to record the **fact** of supersession. I17 is unchanged and was always the operative rule. |

**v1.5 — 2026-08-20.** Caller-identity audit. **v1.4's SAFE verdict was premature, and the reason is instructive: the fix recreated the defect one layer up.**

| Input | Change |
|---|---|
| **Gap:** v1.4 closed the direct `INSERT` denial of service by moving workflow enqueue into `app_start_workflow_run` — and then described that command as *client-callable by design* and granted it to `authenticated`. **Every function granted to `authenticated` is reachable at `/rest/v1/rpc`.** So any member could call it directly, create a valid run and a valid linked job, and **bypass the FastAPI `workflow-run` rate limiter** — with a fresh run id each time, so the partial unique index bounds nothing. An owner/admin could call the approval command the same way. v1.4 itself argued the original INSERT bypass mattered *because* it evaded that limiter, then shipped a public RPC performing the same transition. | **New §The Caller-Identity Boundary** and a `session_user` guard at the head of all five commands. |
| **Verified, not assumed:** the application and PostgREST reach the database under **different immutable logins**. `d7b95c1f4e08` creates `projectone_api` and records that Supabase's `authenticator` was **rejected** for the request path; `.env.example` connects as `projectone_api`; `tests/conftest.py` exercises the real role; `test_request_session.py` already asserts the session reverts to `projectone_api` after its transaction. PostgREST connects as `authenticator`. Both reach `current_user = authenticated`; **only `session_user` distinguishes them, and it cannot be changed without superuser.** | The guard is built on that, and **I21** makes it a named part of the security model. |
| **Terminology corrected.** v1.3 and v1.4 called these "client-callable commands", which described the transport and implied the intent. | They are **application and worker commands executed under an RLS-subject actor**. They are *discoverable* as RPCs and are **not callable**: a direct PostgREST invocation fails before any read or write. |
| **Documentation defect found in passing** (reported, not fixed — this task changes no code): `app/core/config.py`'s comment on `request_database_url` names the connecting role as `authenticator`. That is the role `d7b95c1f4e08` explicitly rejected. The comment contradicts the migration, the env template and the test harness, and it is exactly the kind of stale note that would mislead someone reasoning about this boundary later. | Recorded in §The Caller-Identity Boundary for STEP-31 to correct. |

**v1.4 — 2026-08-20.** Final correction before acceptance. **v1.3's claim that the attack surface was closed was incomplete.**

| Input | Change |
|---|---|
| **Gap:** v1.3 closed the `workflow_step_runs` surface but left `jobs`. `jobs_insert_member` pins only `workspace_id` and `enqueued_by`; `app_jobs_queue_state_not_client_writable` is **`BEFORE UPDATE` only**; `authenticated` holds `INSERT`. A member could therefore directly INSERT a job carrying any `workflow_run_id` in their workspace — **occupying the partial unique key and blocking every legitimate start, approval and resume for that run**, bypassing the per-user rate limit, and attempting to drive a workflow from a forged payload. v1.3 dismissed this as "grants nothing, because the enqueued job carries no authority", which addressed forgery and missed denial of service entirely. | **D4** gains the INSERT-policy `NULL` rule and the job-type/link biconditional CHECK; **D11** gains the protected enqueue. |
| **Owner decision:** D11's privilege boundary is approved in principle, subject to the eight containment conditions (§D11). | Recorded and asserted by P34–P42. |
| **Complete-transition rule.** Any function granted to `authenticated` is a **callable PostgREST RPC**. v1.3's `app_grant_step_approval` and `app_supersede_step_claim` were each **half-transitions**: the first could leave an unspent grant with no job, the second could clear a claim and leave the run with no correct next state. | **Consolidated.** Four functions become **five in two tiers** — three complete domain commands and two lease-fenced worker internals. There is now **no client-callable primitive that merely enqueues, merely grants, or merely supersedes.** |
| **Owner decision:** the project has no production deployment or rolling fleet. | v1.3's three-ordered-deployments requirement is **withdrawn**. STEP-31 ships as **one coordinated pre-production cutover, one branch, one PR**. The expand → cutover → contract sequence is documented as a *future production* obligation belonging to deployment planning, and is not imposed on STEP-31. |

**v1.3 — 2026-08-20.** Security and integrity audit before acceptance. **A gap was found, and it is exploitable by an ordinary authenticated member.**

| Input | Change |
|---|---|
| **Audit finding:** ProjectOne runs on managed Supabase. `authenticated` holds `SELECT, INSERT, UPDATE` on every tenant table (`c4f21a86b3de`), PostgREST reaches the database as that role, and `app/repositories/supabase_auth.py` records that `/rest/v1/` answers 200. `workflow_step_runs` has **no write-guard trigger** and its UPDATE policy checks only workspace membership. **Every D8/D9 column as specified in v1.2 was therefore directly writable by any member holding their own Supabase JWT** — including `approved_by`, which would let a member forge an owner's approval and detonate the §15 gate. | New **§Authenticated-Client Attack Surface** with the evidence, and **D11** closing it. |
| **The root cause is that the runner and the attacker are the same database principal.** `RequestSessionFactory` runs `SET LOCAL ROLE authenticated`; PostgREST does the same. No trigger, policy or column grant can distinguish "the runner writing a claim" from "a member writing a claim", because there is nothing to distinguish. v1.2's assumption that no endpoint exposes these columns is exactly the "the UI does not expose it" reasoning the audit forbids. | **D11**: claim, admission, settlement, approval and supersession move into four narrow `SECURITY DEFINER` functions that validate `auth.uid()` internally; `authenticated` loses direct UPDATE on `workflow_step_runs` and loses `SELECT` on the two token columns. |
| **Fencing tokens were tenant-readable.** `jobs_select_same_workspace` grants SELECT on **all** columns, `lease_token` included. A member could read the live lease token and forge a claim that satisfied predicate (2). A fencing token that a client can read is a capability, not a fence. | Column-level `SELECT` grants; both token columns become unreadable by `authenticated`. |
| **Predicate (2) could race.** v1.2's fenced settle checked the lease through an `EXISTS` subquery on `jobs`, evaluated at the statement snapshot and never re-checked. A concurrent claim could rotate `lease_token` between snapshot and write. | The settle function takes `FOR UPDATE` on the step row and `FOR SHARE` on the job row before evaluating any predicate. |
| **Single-use approval was tied to the claim**, so a future step that is gated *and* `replayable = True` would never consume its grant and a redelivery would reuse it. | Consumption moves to **admission**, which every step passes through regardless of replayability. |
| **Column count challenged.** Three of v1.2's seven columns enforced nothing. | **Seven columns become four.** `claimed_at`, `superseded_claim_token` and `approved_at` removed; the facts they carried move to `audit_log`, without raw tokens. |

**v1.2 — 2026-08-20.** Owner decisions on all five questions, plus one correction that changes behaviour.

| Input | Change |
|---|---|
| **Q1–Q5 all decided** by the owner (§Owner Decisions) | Applied throughout. §Open Questions is replaced by §Owner Decisions; nothing is left open for the owner to answer. |
| **Correction:** a redelivered worker that finds an existing non-replayable step claim **must not settle its job `succeeded`** | v1.1 said it should. **v1.1 was wrong**, and the reasoning it gave was wrong in a specific way worth recording: it assumed the claim holder was alive. A worker cannot prove that. Settling `succeeded` on a dead holder leaves a job terminally succeeded, a run still `running`, and **nothing left that could advance or reconcile it** — a silently stranded run, which is the §26 failure this ADR exists to remove. Corrected in D8: the job is **terminally interrupted**, dead-lettered with a safe public message, and D5 reconciles the run to `failed` atomically. |
| **The objection v1.1 raised against dead-lettering is answered by fencing, not ignored.** | v1.1 declined to dead-letter because D5 would then mark `failed` a run a live sibling was executing. Under v1.2's three-predicate fencing (D8), a sibling that has lost its lease **can no longer persist anything at all** — so marking the run `failed` cannot race a write that will still land. Fencing is what makes the correction safe, and it is why the correction is strictly better than v1.1's design rather than a different trade. |
| **New finding while verifying the correction** | Approval is **not persisted anywhere**. `WorkflowRunner.approve` passes `approved=True` as an in-memory parameter and logs `approved_by`; `grep` over `app/` and `migrations/` finds no `approved_at` or persisted `approved_by` column. **Asynchronous approval is therefore unimplementable as the code stands** — the decision cannot cross the process boundary. New **D9** makes approval durable, single-use state, which also makes owner requirement 10 checkable rather than aspirational. |
| Replayability verified against the code rather than assumed | `ValidateProjectStep` reads one row and writes nothing; `QualityCheckStep` inspects a value already in memory. Both verified `replayable = True`. `PlanningAgent` reaches a paid provider: non-replayable. |

**v1.1 — 2026-08-20.** Owner decision on all-dead-letter reconciliation; §Execution Safety added after a review finding that the partial unique index does nothing about redelivery of one job after lease expiry. v1.0's Concurrency Guard conflated two problems and was wrong by omission on the second.

**v1.0 — 2026-08-20.** Initial draft.

### What happened to ADR-005 on acceptance

[[ADR-005 Async Job Queue and Worker Execution Model]] §Status requires that changing "the cross-tenant dispatch boundary requires a new ADR that supersedes this one — this note is not amended in place." This ADR changes that, and nothing else.

- **ADR-005 was `Accepted` and fully binding until this ADR was accepted.**
- **On acceptance ADR-005 moved to `Superseded`**, naming ADR-006 as its successor. That change was made in the same act as this one.
- **`Superseded` means "restated with two constraints changed", not "withdrawn".** §What of ADR-005 Remains Binding carries every unchanged decision forward.
- **§Execution Safety supersedes nothing.** It *discharges* an obligation ADR-005 §6 already imposed.

---

## Owner Decisions

All five questions raised by v1.0/v1.1 are decided. They are recorded here as settled inputs, not as open items.

| # | Question | **Owner's decision** | Where applied |
|---|---|---|---|
| **Q1** | Scope of reconciliation | **Reconcile every dead-lettered job linked to a workflow run.** Preserve the guard that never overwrites `completed` or `failed`. | D5 |
| **Q2** | The architectural boundary test | **Rewrite it more tightly.** Do not add `workflow_runs` to a broad exclusion list. | D6, P8 |
| **Q3** | How a job names its run | **Concrete nullable `jobs.workflow_run_id`**, composite tenant-safe FK, partial unique live-job index. | D4 |
| **Q4** | Claim expiry | **No expiry and no automatic recovery** for claims protecting non-replayable steps. **Cost safety and explicit user control take priority over automatic replay.** | D8, D10 |
| **Q5** | Status codes | **`202 Accepted` consistently** for start, approval and resume. | D1 |

Q4 is the decision the rest of this ADR is shaped by. It is not a tuning constant: it settles that ProjectOne would rather stop and ask than silently pay a provider twice, which is [[CLAUDE|CLAUDE.md]] §40's "AI should think. Users should decide." applied to a failure path.

---

## Context

### What STEP-31 has to do, and what already exists to do it with

`WorkflowRunner` executes every step inside the HTTP request that started it. [[STEP-30 Async Job Infrastructure]] built the queue, the worker, the tenant boundary and the retry ceiling, proven on `TenantProbeHandler`. STEP-31 is one handler plus the route changes that enqueue it.

Nine facts were read from the code rather than assumed.

**1. The engine is already resumable, and the routes are already thin.** `_execute_from` persists each step before starting the next; `next_step_index` counts only `completed` steps. `app/routers/workflows.py` decides nothing about execution.

**2. Enqueue is genuinely transactional.** `get_tenant_connection` yields one connection inside one transaction for the whole request. `create_run` and `enqueue` commit together or not at all. **This is also what makes an atomic recovery transaction possible (D10) without any new machinery.**

**3. Two records of one run's state already exist and can disagree.**

**4. Dead-lettering is reachable by three paths, and two have no tenant identity available.**

| Path | Where | Tenant session as the actor? |
|---|---|---|
| `TenantContextUnavailableError` — actor lost membership | `JobWorker._establish_identity` | **No.** `app_current_user_workspaces()` filters `workspace_members.deleted_at IS NULL` (`b8e1d94c50a7`), so the revoked actor's session cannot see the run. |
| Handler failure, including an unregistered type | `JobWorker._execute` | Yes |
| Reap on claim — worker died with attempts exhausted | `JobDispatchRepository.claim` | **No.** No identity established; runs inside the privileged claim transaction. |

**5. The privileged connection already holds full cross-tenant write access to every table.** `DATABASE_URL` connects as `postgres`; a superuser bypasses row security entirely, which is why the dispatcher works. **Reconciliation invents no privilege** — only the stated bound changes.

**6. The architectural guard is written against exactly that bound.** `tests/test_job_boundary.py::TestConstraintOneOneTable` asserts no SQL literal in `job_dispatch.py` mentions any of fifteen tenant tables, `workflow_runs` among them.

**7. ADR-005 §6 already obliges this handler to hold a durable claim, and nothing in the code provides one.**

> For the workflow handler this is nearly free: `next_step_index` counts completed steps… **It is not free for any handler with an external side effect.** … Any handler performing a non-idempotent external action must guard it with **its own durable claim in the same shape**, and the job lease is not a substitute for one.

`PlanningAgent` bills a provider, so the second half governs. STEP-31's *Inherited from STEP-30* note quotes only the first half. **ADR-006 does not create this obligation; it discharges it.**

Supporting observations, each read from the code:

- **`WorkflowRunner` has no claim of any kind.** `_execute_from` calls `update_run_status(RUNNING)` unconditionally; `record_step` is an unconditional upsert. Two workers entering one incomplete step both proceed, both call the provider, and the second write silently overwrites the first.
- **`uq_workflow_step_runs_run_id_step_index` deduplicates the row, never the bill.** `c8f1a3d54e29` records that a unique index was tried first for chat turns and **rejected** on exactly this ground.
- **Spend controls bound cost; they do not deduplicate calls.** `try_reserve` is a compare-and-increment so two callers cannot consume the same headroom — but where headroom exists both are granted and both invoke. A redelivery gets a **fresh** `ExecutionBudget` by design.
- **The precedent already names this ADR's job:** "Reconciliation, lease policy and provider idempotency are a separate ADR-backed step covering **every AI feature**, not just chat."

**8. The STEP-31 proof does not reach the case that matters.** Its wording is *"Two enqueues for one run do not produce two executions"* — duplicate **enqueue**. A single job **redelivered after lease expiry** is a different scenario with the same symptom. P4 and P14 separate them.

**9. Approval is not persisted, and this blocks D1 outright.** `WorkflowRunner.approve` takes `approved_by`, logs it, and calls `_continue(..., approved=True)` — an **in-memory parameter**. `grep -rn "approved_by\|approved_at" app/ migrations/` returns three hits, all of them that parameter being passed and logged. No column, no row, no record. Synchronously this is fine: the approving request *is* the executing request. **Asynchronously the decision has to reach a different process, and there is nothing durable for it to travel in.** D9 fixes it, and the fix is also what makes owner requirement 10 provable rather than a convention.

### Why this needs its own ADR

Three of §39's ADR-requiring categories at once — the multi-tenancy model, a public API contract, the database model — and §21 makes it Critical independently.

---

## Decisions

**[Owner-approved]** marks direction the owner has decided. **[Implementation — open to evidence]** marks a shape STEP-31 must prove, changeable on evidence without a new ADR.

### D1. Start, approval and resume are *accepted*, not *performed* **[Owner-approved, Q5]**

All three endpoints enqueue and return **`202 Accepted`**, consistently. No continuation executes inside a request.

Approval matters most: `WorkflowRunner.approve` continues execution inline today, and leaving it inline would put a multi-minute render back inside a request through the one route nobody would check.

`POST .../runs` moves 201 → 202. A run row *is* created, so 201 is not false — but the operation is not complete, and 202 is the only code that says so. Three sibling endpoints answering with one code for one semantic is the point of Q5's decision.

### D2. The body stays `WorkflowRunResponse`, and no job identifier is exposed **[Owner-approved]**

Same schema as today, rendering the run in `pending`. No envelope, no `job_id`, no queue state. There is no jobs router, and `apps/web/src/lib/api.ts` already types `ApiRunStatus` as including `pending`. Exposing a job id would make the queue a public contract and turn ADR-005 §1's broker-migration escape hatch into a breaking client change.

### D3. `workflow_runs` is authoritative for user-facing state; `jobs` is operational delivery state **[Owner-approved]**

| Question | Answered by |
|---|---|
| What is this run's status, and why? | `workflow_runs.status`, `.detail` |
| What did each step do, and what did it cost? | `workflow_step_runs` |
| Has delivery been attempted, how often, with what lease? | `jobs` |
| Did the platform give up on delivering this run? | `jobs.status = 'dead_lettered'` — and, by D5, `workflow_runs.status = 'failed'` in the same instant |
| Is a step mid-execution, and who owns it? | `workflow_step_runs.claim_token`, `.claimed_by_job_id`, `.claimed_by_lease_token` |
| Is a gated step's approval granted and unspent? | `workflow_step_runs.approved_by` (D9) |
| Which run is this job for? | `jobs.workflow_run_id` — **never `jobs.payload`**, which is client-writable on INSERT |
| Who approved, and when? | `audit_log` — history survives the grant being spent |

**No user-facing surface derives run state by reading `jobs`, and none joins the two.** The runner's *fencing predicate* does read `jobs` over the tenant session (D8) — that is an internal correctness check, not a user-facing read, and it is explicitly not the privileged path.

### D4. One live workflow job per run, and a workflow job can only be created by the protected command **[Owner-approved, Q3; the INSERT closure is new in v1.4]**

```sql
ALTER TABLE public.jobs
    ADD COLUMN workflow_run_id uuid,
    ADD CONSTRAINT fk_jobs_workflow_run_id_workflow_runs
        FOREIGN KEY (workflow_run_id, workspace_id)
        REFERENCES public.workflow_runs (id, workspace_id) ON DELETE RESTRICT,

    -- A workflow execution job **is** its relational link, and nothing else may
    -- wear the link. Biconditional on purpose: the forward half stops a workflow
    -- job existing without a run to reconcile; the reverse half stops any other
    -- job type occupying the partial unique key below and blocking a run.
    ADD CONSTRAINT ck_jobs_workflow_link_matches_type
        CHECK ((job_type = 'workflow.execute') = (workflow_run_id IS NOT NULL));

CREATE UNIQUE INDEX uq_jobs_one_live_job_per_workflow_run
    ON public.jobs (workflow_run_id)
    WHERE workflow_run_id IS NOT NULL
      AND deleted_at IS NULL
      AND status IN ('pending', 'running');
```

and the INSERT policy is tightened so a direct client can never create a workflow-linked row:

```sql
DROP POLICY jobs_insert_member ON public.jobs;
CREATE POLICY jobs_insert_member ON public.jobs
FOR INSERT TO authenticated
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces())
    AND enqueued_by = auth.uid()
    -- New in v1.4. A workflow job is created only by the protected command
    -- (D11), which runs as the table owner and is not bound by this policy.
    AND workflow_run_id IS NULL
);
```

**The two rules compose into a closed door, and neither is sufficient alone.** The policy forces a direct INSERT to leave the link `NULL`; the CHECK then makes `job_type = 'workflow.execute'` impossible for such a row, and equally makes any *other* job type carrying a link impossible. A member attempting either half is refused by the database, not by a route:

| Direct INSERT attempt | Refused by |
|---|---|
| `job_type='workflow.execute'`, `workflow_run_id=NULL` | `ck_jobs_workflow_link_matches_type` |
| `job_type='workflow.execute'`, `workflow_run_id=<their own run>` | `jobs_insert_member` (link must be NULL) |
| `job_type='tenant.probe'`, `workflow_run_id=<any run>` | `jobs_insert_member`, and `ck_jobs_workflow_link_matches_type` behind it |
| any type, `workflow_run_id=<another workspace's run>` | `jobs_insert_member`, and `fk_jobs_workflow_run_id_workflow_runs` behind it |
| forged `workspace_id` | `jobs_insert_member` |
| forged `enqueued_by` | `jobs_insert_member` (`= auth.uid()`) |

**Why the composite FK, not a bare one.** Otherwise the link is an unchecked claim and D5's reconciliation would write across a tenant boundary while looking ordinary — the protection `workflow_step_runs` and `assets` already use.

**Why a real column, not `payload->>'run_id'`.** ADR-005 §5 constraint 1 rests part of its argument on the payload being *opaque*, an expression index over JSON is not FK-checkable, and — decisively — **`jobs.payload` is client-writable on INSERT**, so a payload-borne run id is a forgeable claim rather than a relational fact.

**`workflow_run_id` is also added to the `app_jobs_queue_state_not_client_writable` whitelist**, so it cannot be repointed by a later UPDATE. Creation is closed by the policy; mutation is closed by the trigger; the pairing is closed by the CHECK.

**What D4 does not do.** It bounds *creation and enqueue* only. One job delivered twice is D8.

### D5. Every dead-lettered job linked to a run marks that run `failed`, in the same statement **[Owner-approved, Q1]**

Reconciliation applies to **every** dead-lettered job carrying a `workflow_run_id`. The dispatcher cannot know where a job failed; it knows delivery is over, and a run left non-terminal when its job is abandoned was abandoned whatever stage it reached.

**The terminal-state guard is preserved and is the whole safety of the rule.** A run already `completed` or `failed` is never touched.

Both dead-letter sites — the reap inside `claim` and the terminal branch of `record_outcome` — become a single data-modifying-CTE statement:

```sql
WITH settled AS (
    UPDATE public.jobs
       SET status = 'dead_lettered', ...
     WHERE ...
    RETURNING id, workspace_id, workflow_run_id, status
)
UPDATE public.workflow_runs r
   SET status = 'failed',
       detail = %s,          -- a fixed public sentence; see D7
       finished_at = now()
  FROM settled s
 WHERE r.id = s.workflow_run_id
   AND r.workspace_id = s.workspace_id
   AND r.deleted_at IS NULL
   AND r.status NOT IN ('completed', 'failed')
RETURNING r.id;
```

**Why a CTE rather than two statements in one transaction.** Both are durable-atomic, but a CTE is atomic *structurally* — no ordering to get right, no early `return` that can skip the second write, and no future edit that separates them without visibly rewriting one statement into two.

**Reconciliation never touches `workflow_step_runs`, and therefore never clears a claim.** This is load-bearing three times over:

1. **Evidence.** The stale claim is the record of what was in flight when the run stopped (owner requirement 8).
2. **Fencing.** The claim token remains a live predicate against the stale worker.
3. **Cost safety.** A reconciliation that released the claim would hand the next automatic delivery permission to re-invoke a provider that has already been paid.

**A run may therefore be `failed` while still holding a claimed step.** That combination is the honest description of "this stopped mid-call", and it is the state a stranded run is *meant* to end in — visible, terminal, and recoverable only by an explicit act (D10).

### D6. The privileged path's stated bound widens from one table to two, and nothing else changes **[Owner-approved]**

**ADR-005 §5 constraint 1 — "One table"** is replaced by:

> **Two tables, one of them by exactly one statement shape.** The dispatcher reads and updates `public.jobs`. It additionally updates `public.workflow_runs` in the single reconciliation leg in D5 — never in any other statement, never as a `SELECT`, never returning any column beyond `r.id`, and only where the run is named by `jobs.workflow_run_id` and matched on the job's own `workspace_id`. It joins to no other tenant table and returns no tenant data. **It never touches `workflow_step_runs`.**

**ADR-005 §5 constraint 2 — "Three statements"** is replaced by:

> **Three operations, not a connection.** `claim`, `extend_lease`, `record_outcome`. Two carry the reconciliation leg.

**Nothing else in §5 moves.** Constraints 3, 4, 5 and 6 are unchanged and binding verbatim.

**No new privilege is created and the worker's access does not broaden.** The dispatch connection is already `postgres` (Context fact 5); nothing is granted, no role created, no `SECURITY DEFINER` function added. **Every mechanism in D8, D9 and D10 runs over the ordinary tenant session as the enqueuing or requesting user and requires no privilege at all.**

**The guard is rewritten tighter, not exempted (Q2).** Specified in P8.

### D7. No internal error text reaches the run, the job, or any response **[Owner-approved]**

Reconciliation writes a **fixed public sentence**, never a copy of `jobs.last_error` and never an exception's message. The interrupted case gets its own fixed sentence naming the *situation* rather than the cause — a run that stopped before its last step completed, and can be continued — because that is what the user needs in order to act.

The revoked-actor case stays generic for a second reason beyond §24: "the account that started this job no longer has access" is a statement about another member's status, shown to everyone who can see the run. The cause stays in the dead-letter log line.

### D8. A durable step claim, fenced three ways, with no expiry **[Owner-approved (Q4); shapes are Implementation — open to evidence]**

Specified in full in §Execution Safety. In summary:

- Every `WorkflowStep` declares `replayable`, defaulting to **`False`**, inherited rather than written — the identical safe-default pattern `requires_approval` already uses.
- A non-replayable step is claimed by a conditional upsert before it executes; exactly one execution wins.
- **Persisting a step result requires all three of:** the correct durable `claim_token`; the worker's job lease token still current on `jobs`; and the run not already terminally reconciled.
- **No expiry, no automatic recovery, and no stealing.** A replacement worker never expires or takes a claim it finds.
- A replacement worker that finds a live claim treats the job as **terminally interrupted** — dead-lettered, reconciled by D5 — **never as succeeded**.

### D9. Approval becomes durable, single-use state on the step **[Owner-approved in principle; D11 is the condition of acceptance]**

`workflow_step_runs` gains **one** column, `approved_by uuid`. Non-null means *granted and unspent*; consumption clears it. `approved_at` is not kept — see §Column Necessity.

- **The grant is written by `app_approve_workflow_step`** (D11), in the same transaction that enqueues the job (D1). This is what carries the decision across the process boundary; there is nothing today that does (Context fact 9).
- **The function pins every part of the grant structurally**, so a direct database path is exactly as safe as the API route: `approved_by := auth.uid()` (never a parameter), `public.app_workspace_role(workspace_id) IN ('owner','admin')`, the run named and live and **currently `awaiting_approval`**, the step index the one the run is actually waiting on, and `approved_by IS NULL` beforehand so a grant cannot be re-issued over an unspent one.
- **Admission consumes it** (D8), not the claim — so a gated step that is also `replayable = True` still spends its grant exactly once.
- **An interrupted gated step has therefore already spent its approval**, and no later delivery can execute it without a fresh one. Owner requirement 10 is structural: nothing *infers* approval, because the persisted model records the grant was spent.
- **Not the job payload.** An authorization decision in an opaque blob has no audit trail and no writer validation. `jobs.payload` is client-writable on INSERT — the write guard is `BEFORE UPDATE` only and the INSERT policy pins nothing but `enqueued_by` and workspace — so a payload-carried approval would be forgeable by any member.
- **Who approved, and when, is durable in `audit_log`**, written by the same request. The step column is enforcement state and is cleared on use; the audit record is history and is not.

### D10. Recovery from an interrupted step is an explicit user action **[Owner-approved, Q4]**

Automatic delivery never re-enters a claimed non-replayable step. Continuing is a request a person makes, and the transaction that supersedes the stale claim and enqueues the replacement job is **one atomic tenant transaction**. Specified in §Explicit Recovery.

### D11. Execution authority lives in five `SECURITY DEFINER` commands, invocable only by the application login **[Owner-approved in principle, v1.3; consolidated in v1.4; caller boundary added in v1.5]**

**Why a privilege is unavoidable here, when it was avoidable for D5.** For reconciliation there was an alternative: the dispatch connection already held the access, so widening a *stated bound* sufficed and no principal was invented. Here there is none, because **the application runner and a direct Supabase/PostgREST client are the same database principal**. `RequestSessionFactory` runs `SET LOCAL ROLE authenticated`; PostgREST reaches the database as `authenticated` too. No policy, trigger or column grant can separate "the runner writing a claim" from "a member writing a claim" — there is nothing to separate. The rule has to move somewhere the caller cannot reach around, and the direct write has to be taken away.

#### The containment conditions, as approved

`postgres` ownership is acceptable **only** with all eight, and each is asserted rather than asserted-in-prose:

| Condition | How it is met | Proof |
|---|---|---|
| `SECURITY DEFINER` | on all five | P34 |
| `SET search_path = ''` | on all five | P34 |
| Every object schema-qualified | `public.` on every reference | P34 |
| No dynamic SQL | no `EXECUTE`, no `format()`, no string-built statements | P34 |
| PUBLIC/anon execution revoked explicitly | `REVOKE ALL … FROM PUBLIC` **and** `FROM anon` **by name** — `c4f21a86b3de` proved that revoking from PUBLIC does not cover `anon` in this database | P35 |
| EXECUTE granted only where required | `GRANT EXECUTE … TO authenticated`, the one role that must call them | P35 |
| Actor always from `auth.uid()` | **no function takes an actor parameter** | P36 |
| **Invocable only by the application login** | `session_user = 'projectone_api'`, checked as a literal before any read or write (§The Caller-Identity Boundary) | P45–P50 |
| Exact table and statement boundaries asserted | tests read the function bodies | P37 |

This is the containment `app_workspace_role` already carries (`b8e1d94c50a7`), applied to five functions instead of one.

#### Every granted function is discoverable as an RPC, so every one must refuse a direct caller *and* be a whole transition

PostgREST exposes any function granted to `authenticated` at `/rest/v1/rpc/<name>`. **A stranger can therefore attempt each of these directly, in any order, any number of times.** Two independent consequences follow, and v1.4 acted on only the second:

1. **A direct attempt must change nothing.** Closed in v1.5 by the `session_user` guard: an invocation that did not arrive over the `projectone_api` login is refused with `42501` before its first read. **These are application and worker commands executed under an RLS-subject actor — discoverable, not callable.**
2. **A legitimate invocation must be a whole transition.** A command is not a helper the application calls in a sequence it controls; it must leave the domain valid or change nothing.

**v1.4 satisfied (2) and reintroduced the very defect it had just fixed under (1).** It moved workflow enqueue into `app_start_workflow_run` to stop a direct `INSERT` from occupying the unique key, then granted that command to `authenticated` and called it client-callable — so a member could create a run and its job over `/rest/v1/rpc`, with a fresh run id every time, bypassing the `workflow-run` limiter that bounds AI spend per user. The unique index does not bound that, because each call names a different run. Closing a bypass by relocating it is not closing it.

v1.3's four functions failed that test twice:

- **`app_grant_step_approval` was a half-transition.** Called on its own by an owner/admin it wrote an unspent grant with **no job enqueued** — a run sitting in `awaiting_approval` carrying a live entitlement that some later, differently-authorized path could spend. An approval that is durable but detached from the execution it authorizes is precisely the "reusable grant another action can exploit" this audit forbids.
- **`app_supersede_step_claim` was a half-transition.** Called on its own it cleared a stale claim and left the run `failed` with **no replacement job and no re-armed gate** — and worse, a cleared claim on a step still `running` is exactly the state that lets a redelivery re-enter a paid step.

**Both are consolidated away. There is no client-callable primitive that merely grants, merely supersedes, or merely enqueues.** Four functions become five, and the count is not the point — the point is that the three client-facing ones are each a complete domain command.

#### Tier 1 — complete domain commands (invoked by the API, refused from anywhere else)

Each performs its whole transition in one transaction, or raises and changes nothing — and each begins with the `session_user` guard, so the API route is the only path into it.

**`app_start_workflow_run(workflow_type, definition_version, project_id, payload) → uuid`**
Live member of the workspace (`app_current_user_workspaces()`); inserts the run in `pending`; inserts the job with `job_type := 'workflow.execute'` **fixed in the function body**, `max_attempts := ` the registered ceiling **fixed in the function body**, `enqueued_by := auth.uid()`, and the relational `workflow_run_id`. Returns the run id and nothing else. Transactional enqueue (ADR-005 §1) is preserved because both inserts are in the caller's transaction.

**`app_approve_workflow_step(run_id, step_index) → uuid`**
`app_workspace_role(workspace_id) IN ('owner','admin')`; locks the run `FOR UPDATE` and refuses unless it is live and **currently `awaiting_approval`**; refuses unless `step_index` is the step the run is actually waiting on; refuses unless `approved_by IS NULL`. Then, in the same transaction: writes `approved_by := auth.uid()` **and** enqueues the workflow job. **The grant and the job are inseparable** — there is no way to obtain one without the other, which is what makes a detached grant unreachable. Returns the job id.

**`app_recover_workflow_run(run_id) → uuid | null`**
Live member; locks the run `FOR UPDATE` and refuses unless it is `failed`; locks the interrupted step `FOR UPDATE`; clears `claim_token`, `claimed_by_job_id`, `claimed_by_lease_token`; writes the `audit_log` row (run id, step index, actor, superseding job id, and the *fact* of supersession — **never the raw token**); then completes the transition one of two ways and never neither:

- **step not gated** → step `failed` (claimable), run `pending`, **job enqueued**, job id returned;
- **step gated** → step `awaiting_approval`, `approved_by` left `NULL` (the grant was consumed at admission), run `awaiting_approval`, **no job**, `NULL` returned. Continuing then requires `app_approve_workflow_step`, which is separately role-checked.

#### Tier 2 — worker internals, fenced by the application login *and* by a value no client can hold

`app_admit_workflow_step(run_id, step_index, step_name, requires_approval, replayable, job_id, lease_token) → uuid | null` and `app_settle_workflow_step(run_id, step_index, status, detail, output, tokens_used, claim_token) → boolean`.

Both must be granted to `authenticated`, because the worker *is* `authenticated`. **Two independent things stop a client: the `session_user` guard refuses the call outright, and — were that guard ever removed — both still demand a value the client cannot read or guess**: `lease_token` is written only by the privileged dispatcher and, since v1.3's column grants, is not in any `SELECT` grant held by `authenticated`; `claim_token` is likewise unreadable. Each function validates that value **under row locks** — the run `FOR UPDATE`, the step `FOR UPDATE`, the job `FOR SHARE` — before touching anything.

A client calling either with a guessed token gets a refusal and no state change. This is the same reasoning `messages.claim_token` already rests on, one layer up.

#### The grant changes that make the commands the only path

```sql
REVOKE UPDATE ON public.workflow_step_runs FROM authenticated;
GRANT  UPDATE (deleted_at) ON public.workflow_step_runs TO authenticated;
REVOKE INSERT ON public.workflow_step_runs FROM authenticated;

REVOKE SELECT ON public.workflow_step_runs FROM authenticated;
GRANT  SELECT (id, workspace_id, run_id, step_index, step_name, status, detail,
               tokens_used, output, started_at, finished_at, created_at,
               updated_at, deleted_at, version, approved_by)
       ON public.workflow_step_runs TO authenticated;

REVOKE SELECT ON public.jobs FROM authenticated;
GRANT  SELECT (id, workspace_id, enqueued_by, job_type, payload, status,
               attempts, max_attempts, claimed_by, claimed_at, result,
               last_error, dead_lettered_at, correlation_id, created_at,
               updated_at, deleted_at, version, finished_at, workflow_run_id)
       ON public.jobs TO authenticated;
```

`lease_token`, `claim_token` and `claimed_by_lease_token` appear in no client grant. **A member still sees everything about their workspace's runs and queue — status, history, cost, failure detail, and who approved a gated step — and can read or write nothing that fences an execution.** That last clause is the whole of I15: `approved_by` is in the `SELECT` list deliberately, because reading it is audit and writing it is authority, and only the second is withheld.

#### The `lease_expires_at` decision

**It is absent from the `jobs` grant on purpose, and the purpose is not that it is dangerous.** It is a timestamp. A member who read it could not admit a step, could not settle one, and could not extend anything — every one of those requires `lease_token`, which no client grant contains. Knowing *when* a lease ends grants nothing; holding the token does.

It is withheld because **nothing on the tenant path reads it.** No router exposes `jobs` at all, and `JobRepository` selected the column into a `Job` field that no caller consumed. A grant with no reader is a privilege nobody can later justify or safely remove, so the column leaves the grant and the dead read leaves the repository in the same change.

**The dispatcher is unaffected, and that is the reason this costs nothing.** Every lease computation — reaping an expired lease, extending a live one, clearing it on settlement — runs in `app/repositories/job_dispatch.py` on the **privileged** connection, which is not `authenticated` and holds the table grant outright. A client-facing feature that later needs to show "this job's lease expires at…" restores one line of `GRANT SELECT (…)`; what it cannot do is find the privilege already there and assume someone meant it.

#### Payload is data; the relational link is authority

**The handler derives its run target from `jobs.workflow_run_id`, never from `payload`.** `ClaimedJob` and `JobContext` carry the column (the dispatcher's `RETURNING` already reads only `jobs`, so D6's bound is unaffected), and the handler has no code path that reads a run id out of the payload at all. A forged or disagreeing payload run id is therefore not *rejected* so much as *unreachable* — there is nothing that would consult it. P41 asserts a job whose payload names a different run still advances only the run its column names.

#### Failing closed, by construction

Every command refuses on: a forged actor id (not expressible — the actor is `auth.uid()`); a workspace the caller is not a live member of; a run that is not live, not theirs, or in the wrong state for the transition; a step index the run is not waiting on; a consumed approval (`approved_by IS NULL`); a stale or unheld lease token; a claim token that is not the caller's; and a cross-workspace run id, which fails at the policy and again at the composite foreign key.

**The API's rate limiter remains the effective bound on workflow execution.** `limit_by_user("workflow-run", limit=20, window_seconds=60)` is unchanged on all three routes, and it is now genuinely load-bearing rather than nominally so: since no other caller can enter a command, the route is the only entrance and its limiter is the only gate anyone passes through. Under v1.4 that was false — `/rest/v1/rpc` was a second entrance with no limiter at all.

**The partial unique index remains the final concurrency authority.** None of these functions decides whether a second live job may exist; they attempt the insert and let PostgreSQL serialise. Two concurrent `app_approve_workflow_step` calls for one run both pass every check and then contend on the index — one commits, the other raises `unique_violation` and its grant write rolls back with it. **One grant consumed, one job created**, which is P39.

---

---

## Execution Safety

Three problems wear the same symptom — "a run executed twice". They have different causes, different mechanisms and different residual guarantees.

### 1. Duplicate enqueue protection

**The problem.** Two requests — two raced approvals, an approval and a resume, a client retrying a 202 it never saw — create two jobs for one run.

**The mechanism.** D4's partial unique index. Enforced by PostgreSQL, not application code.

**Behaviour under concurrency.** A partial unique index is a btree over the rows satisfying its predicate. Two transactions inserting a job for the same `workflow_run_id` attempt the same key; PostgreSQL makes the second **block on the first's uncommitted index tuple**. When the first commits, the second raises `unique_violation` (23505); when it rolls back, the second succeeds. There is no window admitting both, and no `SELECT`-then-`INSERT` time-of-check-to-time-of-use gap — the same reasoning `AISpendRepository.try_reserve` uses.

**Two implementation consequences.**

- **`start` never conflicts.** The run is created in the same transaction, so its id is new. The guard bites on approval, resume and recovery.
- **A 23505 aborts the whole request transaction**, since the request is one transaction. Routes must therefore **read before enqueueing** — as `approve` and `resume` already do via `_run_workflow_type`. A `SAVEPOINT` is the alternative if a route ever needs to continue. **[Implementation — open to evidence]**

**Prevents:** two live jobs for one run. **Does not prevent:** anything about one job delivered twice.

### 2. Concurrent lease-redelivery protection

**The problem, precisely.** ADR-005 §6 makes delivery at-least-once, bounded by a lease. When the lease lapses the job becomes claimable **while the original worker may still be running it** — §6's own words. Worker A is mid-`PlanningAgent`; A's lease lapses (a slow provider, a paused process, a partition to the database while the upstream call continues); worker B claims the same job as attempt 2, reaches the same incomplete step, and calls the provider too. Both are billed, and the upsert lets B's write erase any trace that A ran.

**What the lease and `lease_token` actually do**, stated exactly because v1.0 leaned on them:

- The **lease** bounds how long a claim is *presumed* live. It is a timer, not a mutual exclusion — its expiry is precisely the event that admits the second worker.
- The **`lease_token`** fences **settling the job row**. `extend_lease` and `record_outcome` are scoped by it, so a superseded worker's settle affects zero rows. That protects the queue's bookkeeping. It says nothing about what that worker already did to the outside world, and it does not reach `workflow_runs` or `workflow_step_runs` at all. **A fencing token that guards the settle is not a mutual exclusion over the work.**

D8 makes the lease token reach the workflow layer, which is the missing half.

#### Schema

**Four columns, not v1.2's seven.** Each independently enforces a guarantee; the three removed enforced none (§Column Necessity).

```sql
ALTER TABLE public.workflow_step_runs
    -- The durable workflow-layer claim. Rotated on every acquisition.
    -- NOT readable by `authenticated` (D11): a readable fence is a capability.
    ADD COLUMN claim_token uuid,

    -- Which job, and which lease of it, owns this claim. The claim token proves
    -- *which* execution; the lease token proves it *still* owns the job.
    -- `claimed_by_lease_token` is likewise not readable by `authenticated`.
    ADD COLUMN claimed_by_job_id uuid,
    ADD COLUMN claimed_by_lease_token uuid,

    -- The durable, single-use approval grant (D9). Non-null means "granted and
    -- unspent"; consumption clears it. Pinned to `auth.uid()` by the function
    -- that writes it, so it can never name someone else.
    ADD COLUMN approved_by uuid;
```

All nullable, no defaults, no table rewrite. No side table: the state belongs to the step row it describes, and a side table would need its own policies, workspace column and a join on every read — `c8f1a3d54e29` made the same call for `messages`.

#### Which steps are claimed

```python
@property
def replayable(self) -> bool:
    """Return whether re-executing this step is free of external effect."""
    return False
```

**The default is `False` and is inherited rather than written** — the identical defaulting decision `requires_approval` already makes, for the reason its docstring gives: "a step author who did not consider the question ships the unsafe behaviour." Overriding to `True` asserts the step is a pure read or trivially reversible and owes that reasoning in its docstring, exactly as the two `requires_approval = False` exemptions already do.

**Verified against the code, not assumed:**

| Step | `replayable` | Evidence |
|---|---|---|
| `ValidateProjectStep` | **`True`** | "reads one row and writes nothing, spends nothing, and communicates with no external service" — its own documented exemption, and `execute` reads the project through `ProjectRepository` and returns. |
| `QualityCheckStep` | **`True`** | "inspects a value already in memory. There is no external effect to approve." Deterministic over `context.outputs`; touches no repository and no service. |
| `PlanningAgent` | **`False`** (inherited) | Calls `AIService.complete`, reaching a paid provider. |

#### Admission and acquisition

**Every step passes through one admission function**, whatever its replayability or gating. That is what makes approval consumption independent of the claim (audit question 5):

`app_admit_workflow_step(run_id, step_index, step_name, requires_approval, replayable, job_id, lease_token) → uuid | null`

Inside one function invocation, therefore one transaction and one lock ordering:

1. `SELECT … FROM public.workflow_runs WHERE id = run_id FOR UPDATE` — refuse unless the caller is a live member of that run's workspace (`public.app_current_user_workspaces()`), the run is live, and its status is not terminal.
2. `SELECT … FROM public.workflow_step_runs WHERE (run_id, step_index) = … FOR UPDATE` — creating the row if absent.
3. **If `requires_approval`:** refuse unless `approved_by IS NOT NULL`, then **clear it**. The grant is consumed here, at admission, **not at claim time** — so a step that is gated *and* `replayable = True` still spends its grant exactly once.
4. **If not `replayable`:** refuse unless `claim_token IS NULL` and status is one of `pending`, `awaiting_approval`, `failed`; then write a fresh `claim_token`, `claimed_by_job_id` and `claimed_by_lease_token`, verifying against `public.jobs` under `FOR SHARE` that the job is `running`, holds that exact `lease_token`, and has `enqueued_by = auth.uid()`.
5. Set `status = 'running'`, `started_at = coalesce(started_at, now())`.
6. Return the new claim token, or `NULL` for a replayable step, or raise for a refusal.

The row locks make steps 3–5 one indivisible decision. Two concurrent executions serialise on the step row; the second sees the committed result of the first and is refused. This is `c8f1a3d54e29`'s conditional-claim property, reached through a lock rather than an upsert predicate because the function must also read `jobs`.

**Admission commits before the provider is called.** That is `c8f1a3d54e29`'s central property and ADR-005 §4's transaction shape at once — the long work runs with no transaction open and no row locked. The handler opens one short RLS session to admit, closes it, executes, then opens another to settle: exactly the `JobContext.tenant_session()` factory STEP-30 already provides.

#### Settlement is fenced three ways, atomically

`app_settle_workflow_step(run_id, step_index, status, detail, output, tokens_used, claim_token) → boolean`

**All three predicates are evaluated after both rows are locked, inside one function call.** v1.2 expressed this as a single `UPDATE … FROM … WHERE EXISTS (SELECT … FROM public.jobs …)`, which is one statement but **not** one atomic condition: the `EXISTS` is evaluated at the statement snapshot and is never re-checked, so a concurrent claim could rotate `lease_token` between snapshot and write and a stale settle would pass. That race is closed by locking:

1. `SELECT … FROM public.workflow_step_runs … FOR UPDATE` — **(1)** refuse unless `claim_token` equals the caller's.
2. `SELECT … FROM public.workflow_runs … FOR UPDATE` — **(3)** refuse if `status IN ('completed','failed')` or the row is soft-deleted, and refuse unless the caller is a live member.
3. `SELECT … FROM public.jobs WHERE id = claimed_by_job_id FOR SHARE` — **(2)** refuse unless `status = 'running'` and `lease_token = claimed_by_lease_token`.
4. Only then write the outcome and clear `claim_token`, `claimed_by_job_id`, `claimed_by_lease_token`.

`FOR SHARE` on the job blocks a concurrent claim from rotating the lease until this transaction ends, so predicate (2) cannot go stale between its check and the write. **Returning `false` means ownership was lost. The execution stops, writes nothing, and logs why** — it does not retry, does not fail the run, and does not touch the step row.

A replayable step settles through the same function with a `NULL` claim token, which skips predicate (1) and keeps (2) and (3). A replayable step is still not writable by an execution that has lost its job or whose run is already reconciled.

#### Release

The claim is released only by a fenced write from its holder:

- **Success** → `status = 'completed'`, claim columns cleared. `next_step_index` skips it forever.
- **Ordinary failure** → `status = 'failed'`, claim columns cleared, via `WorkflowRunner._fail`. The call returned and we *know* it failed, so retrying is an ordinary user decision.

Both are reachable only while the worker is alive and still owns the job. That asymmetry is the design, not a gap in it.

#### No expiry, no automatic recovery, no stealing **[Q4]**

A claim held by a dead process is **never** released by elapsed time, by a replacement worker, or by D5's reconciliation. `c8f1a3d54e29` states the reasoning and it transfers unchanged: "A process that crashes *after* the provider accepted the request has already incurred the cost; returning the turn to `pending` on a timer would re-invoke and charge a second time. … **Stuck is honest. Silently double-charging is not.**"

#### Finding a live claim: terminal interruption, never success

**This is the v1.1 correction.** A replacement worker that cannot acquire the claim raises `StepInterruptedError` — a `WorkflowError` subclass, therefore terminal under `classify` — and the handler lets it dead-letter.

**Why not `succeeded`, in full.** The replacement worker **cannot prove the holder is alive.** Reporting success on a dead holder leaves: a job terminally `succeeded`; a run still `running`; the original worker gone; and **no job left that could ever advance or reconcile that run**. Nothing would notice, which is precisely the §26 failure ("a system that can fail in a way nobody would notice") this ADR exists to remove. Between two unprovable states, the safe assumption is interruption, and interruption has an honest terminal outcome available.

**Why the objection v1.1 raised does not survive.** v1.1 declined to dead-letter because D5 would mark `failed` a run a live sibling was executing. Under the three-predicate fencing above, a sibling whose lease has lapsed **cannot persist anything** — predicate (2) already fenced it before the reconciliation, and predicate (3) fences it afterwards. There is no write left to race. The run's `failed` state is therefore accurate: whatever the sibling is still doing, none of it will ever land.

So the replacement worker:

1. writes **nothing** to the step row — clearing or overwriting it would erase the evidence and could re-open the double call;
2. settles its job `dead_lettered` with a fixed public message;
3. D5's CTE marks the run `failed` in the same statement;
4. the claim, `claimed_by_job_id` and `claimed_by_lease_token` survive as the audit record of what was in flight.

**Prevents:** two executions concurrently *persisting* one non-replayable step, and any automatic re-entry into a paid step. **Does not prevent:** duplicate execution of replayable steps (pure, converging, and the accepted at-least-once behaviour), or the window in part 3.

### 3. The unavoidable external-call crash window

**Nothing here closes this, and no design available to STEP-31 closes it.**

1. A worker holds the claim and calls the provider.
2. The provider accepts, generates, and **bills**.
3. The worker loses its lease, or dies, before persisting completion.
4. The outcome of step 2 is unknowable from inside ProjectOne: the provider was paid, and nothing records it.

**What the design buys.** Because the claim never expires and is never stolen, **no automatic re-invocation follows**. Every later delivery loses the claim, calls nothing, and dead-letters into a reconciled `failed` run. The *automatic* duplicate is prevented outright.

**What remains, stated without softening:**

- **A provider may accept work before the worker loses ownership or dies.** That charge is real and unrecorded.
- **`AIRouter` retries inside a single call** — up to 3 attempts per provider across 2 providers. A request the provider accepted whose *response* was lost is retried, and the first generation is still billed. No workflow-layer claim sees inside one `complete()`.
- **Manual recovery may repeat a provider call** — but only after an explicit user decision (D10), never automatically, and the endpoint says so.
- **Both windows close only with provider-side idempotency keys.** ADR-005 §Scope Boundaries already lists that as open and out of scope; `c8f1a3d54e29` says the same. This ADR does not reopen it and does not pretend it is smaller than it is.

**There is no exactly-once provider execution, and this ADR does not claim any.** Cost stays bounded by `ExecutionBudget`, the workspace spend ceiling and `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` = 60 — which bound *how much* a duplicate costs and do not make a duplicate not happen.

### 4. The handler's duplicate-safety statement

ADR-005 §6 requires every handler to state **why** it is duplicate-safe. STEP-31's task list carries: *"states in its docstring why it is duplicate-safe (`next_step_index` counts completed steps)."*

**That statement is insufficient and must not ship as written.** `next_step_index` makes a *sequential* redelivery resume rather than restart. It says nothing about two deliveries alive at once — the case ADR-005 §6 explicitly admits and a lease expiry creates. It would be a true statement about the wrong scenario.

**The required statement is four claims, each naming a mechanism:**

1. **Sequential redelivery is safe** — `next_step_index` counts only `completed` steps, so a later delivery resumes at the first incomplete one.
2. **Concurrent redelivery of a non-replayable step is safe** — entering it requires winning a conditional claim exactly one execution can hold, and persisting a result additionally requires a current lease and a non-terminal run. A losing or superseded execution writes nothing.
3. **Concurrent redelivery of a replayable step is safe by declaration** — `replayable = True` asserts no external effect, verified per step and checked by review.
4. **A gated step cannot restart without a fresh approval** — the grant is durable and single-use, and the claim consumes it (D9).

**And it must name what it does not cover:** a provider call completed before its worker lost ownership is not re-driven automatically and is not recorded, and an explicit recovery may repeat one, until provider-side idempotency exists.

---

## Authenticated-Client Attack Surface

The audit that produced v1.3. Every finding is read from the schema and the grants, not inferred.

### The reachability fact everything turns on

ProjectOne runs on **managed Supabase**, and `authenticated` retains `SELECT, INSERT, UPDATE` on every tenant table (`c4f21a86b3de`). **PostgREST reaches the database as `authenticated`**, and `app/repositories/supabase_auth.py:12` records that with a project's keys set, "`/rest/v1/` … answer[s] 200".

*(`c4f21a86b3de`'s docstring says "the API connects as `authenticator`". That was true for the 42 minutes between it and `d7b95c1f4e08`, which created `projectone_api` and rejected `authenticator` for the request path. Migrations are immutable, so the sentence stands as a record of what was believed when it was written; §The Caller-Identity Boundary states the settled shape.)*

So a member holding their own Supabase JWT can issue `SELECT`, `INSERT` and `UPDATE` against any tenant table directly, bounded **only** by RLS. That is not a hypothetical: `c4f21a86b3de` was written precisely because "RLS was doing all the work here… That is one mistake away from a breach."

`workflow_step_runs` has **no write-guard trigger** — only `trg_workflow_step_runs_touch_row` — and its policies check nothing but workspace membership:

```sql
CREATE POLICY workflow_step_runs_update_member ON public.workflow_step_runs
FOR UPDATE TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));
```

**Against v1.2's design that is a full compromise of the approval gate.** `PATCH /rest/v1/workflow_step_runs?id=eq.…` with `{"approved_by": "<the owner's uuid>", "approved_at": "…"}` satisfies that policy exactly, and the next worker admits the gated step on a grant the member wrote themselves. RLS cannot catch it: the row is in their workspace, which is the whole point.

### The ten questions, answered

**1. Could a member directly write each proposed column?** Under v1.2, **yes to all nine**. Under v1.3, **no to all nine**.

| Column | v1.2 | v1.3 | What stops it |
|---|---|---|---|
| `claim_token` | writable | **no** | `REVOKE UPDATE`; written only by `app_admit_workflow_step` |
| `claimed_at` | writable | **removed** | column no longer exists |
| `claimed_by_job_id` | writable | **no** | `REVOKE UPDATE`; definer function only |
| `claimed_by_lease_token` | writable | **no** | `REVOKE UPDATE`; definer function only |
| superseded claim value | writable | **removed** | evidence moved to `audit_log`, without the token |
| `approved_by` | writable | **no** | `REVOKE UPDATE`; `app_approve_workflow_step` sets it to `auth.uid()` |
| `approved_at` | writable | **removed** | column no longer exists |
| approval-consumed value | writable | **no** | consumption is `approved_by := NULL` inside admission |
| `jobs.workflow_run_id` | UPDATE-writable | **no** on UPDATE | added to the `app_jobs_queue_state_not_client_writable` whitelist; composite FK bounds INSERT to the caller's workspace |

**2. Could a member bypass the owner/admin approval route?** Under v1.2, **yes, five ways**: write the grant directly; name an owner in `approved_by`; clear a claim to re-enable a paid call; re-set a consumed grant; and insert a job row directly with a chosen payload (the write guard is `BEFORE UPDATE` only). Under v1.3, **no**: the grant is writable only by a function that sets `approved_by := auth.uid()` after checking `app_workspace_role(...) IN ('owner','admin')`, so a member forging a grant produces *their own* id and is refused by the role check — and an owner doing it gains nothing they could not do through the route. Job payload carries no authority (D9).

**3. Can the grant be pinned structurally?** **Yes, all six**, and only through D11: `auth.uid()` (never a parameter); workspace (`app_current_user_workspaces()`); run (locked and checked live); step index (must be the one the run is waiting on); run status (`awaiting_approval` required); single use (`approved_by IS NULL` required before, cleared on admission).

**4. Does the handler trust any approval fact from `jobs.payload`?** **No, and it must not** — the payload identifies *which run to advance* and nothing else. Authorization is read from `workflow_step_runs.approved_by`, validated inside the admission function. This is a blocker if it is ever violated, and P25 asserts it.

**5. Is consumption atomic with admission for every gated step, including a future `replayable = True` one?** **Yes.** v1.2 tied consumption to the claim, so a gated *replayable* step would never spend its grant and a redelivery would reuse it. v1.3 moves consumption to **admission**, which every step passes through, inside one function under `FOR UPDATE` on the step row. A duplicate or redelivered job finds `approved_by IS NULL` and is refused.

**6. Are tokens exposed anywhere?** Under v1.3, **no path**: not in API responses (`WorkflowStepRunResponse` carries `step_index`, `step_name`, `status`, `detail`, `tokens_used`, `started_at`, `finished_at` — no token, and `jobs` has no router at all); not in raw tables (column-level `SELECT` removes `claim_token`, `claimed_by_lease_token` and `jobs.lease_token` from every client grant); not in `jobs.result` or `jobs.last_error` (D7); **not in `audit_log`** — supersession is audited as run id, step index, actor, job id and the *fact* of supersession, never the raw value; and not in application logs, where the runner's events carry run id, step index and attempt only.

**7. Can a tenant manipulate claim state to cause harm?** Under v1.2: **yes to all four** — forge a claim to block a run indefinitely, clear one to trigger duplicate provider calls, write a matching lease token (readable!) to make a stale settle pass, and clear another actor's grant. Under v1.3: **no to all four.** The tokens are unreadable and unwritable, and admission additionally requires the caller to own a live job (`enqueued_by = auth.uid()`, `status = 'running'`, matching `lease_token` under `FOR SHARE`), which a client cannot fabricate.

**8. Is three-predicate fencing one atomic condition?** Under v1.2, **no** — the lease was checked by an `EXISTS` subquery evaluated at the statement snapshot and never re-checked, so a concurrent claim could rotate `lease_token` between check and write. Under v1.3, **yes**: the settle function locks the step `FOR UPDATE` and the job `FOR SHARE` before evaluating anything, so no predicate can go stale before the write.

**9. Are all the columns necessary?** No — see §Column Necessity. **Seven become four.**

**10. Does rollback preserve integrity and state its losses?** See §Migration and Rollback Implications. It preserves referential integrity and **destroys enforcement state**, which the ADR now says outright rather than calling it routine.

### The direct-INSERT matrix (`jobs`), added in v1.4

v1.3 closed `workflow_step_runs` and left this open. `jobs_insert_member` pins only `workspace_id` and `enqueued_by`; the write guard is `BEFORE UPDATE`; `authenticated` holds `INSERT`.

| Direct `POST /rest/v1/jobs` attempt | v1.3 | v1.4 | Refused by |
|---|---|---|---|
| `workflow.execute` + own run id | **succeeds — occupies the unique key and blocks every start/approve/resume for that run** | **fails** | `jobs_insert_member` (`workflow_run_id IS NULL`) |
| `workflow.execute` + `NULL` link | succeeds (orphan job) | **fails** | `ck_jobs_workflow_link_matches_type` |
| any other type + a run id | **succeeds — same denial of service, wearing a different type** | **fails** | policy, then the CHECK |
| cross-workspace run id | fails (FK) | **fails** | policy, then `fk_jobs_workflow_run_id_workflow_runs` |
| forged `workspace_id` | fails | **fails** | `jobs_insert_member` |
| forged `enqueued_by` | fails | **fails** | `jobs_insert_member` (`= auth.uid()`) |
| forged payload run id on a legitimate job | ignored in principle | **unreachable** | the handler reads the column, never the payload |

**The v1.3 error was reasoning about forgery and not about denial of service.** v1.3 said a directly-inserted job "grants nothing, because the enqueued job carries no authority" — true, and beside the point. Occupying the partial unique key needs no authority at all, and it silently prevents the workspace from ever starting, approving or resuming that run. It also bypasses the `workflow-run` rate limit, which is the platform's per-user bound on AI spend.

### The direct-RPC matrix

Every function granted to `authenticated` is reachable at `/rest/v1/rpc/<name>`. The question for each is not "does the application call it correctly" but "what does a stranger calling it directly achieve".

| RPC, called directly over `/rest/v1/rpc` | v1.3 | v1.4 | v1.5 |
|---|---|---|---|
| **start a run and enqueue its job** | n/a | **possible for any member — bypasses the `workflow-run` rate limiter, unbounded by the unique index** | **refused at the login guard, nothing written** |
| grant an approval with no job | possible for an owner/admin — detached, spendable grant | not expressible; grant and enqueue are one command | **refused at the login guard** |
| supersede a claim with no recovery state | possible — `failed` run, no job, cleared claim on a `running` step | not expressible; one branch of a complete recovery | **refused at the login guard** |
| enqueue a workflow job on demand | n/a | no such primitive exists | **refused at the login guard** |
| member calls the approval command | refused by role | refused by `app_workspace_role(...)` | **refused at the login guard, before the role check** |
| owner approves the wrong step index | not checked | refused — must be the awaited step | **refused at the login guard**; over the API, refused by the step check |
| owner approves a non-`awaiting_approval` run | not checked | refused under `FOR UPDATE` | **refused at the login guard**; over the API, refused under `FOR UPDATE` |
| re-call approval to reuse a spent grant | possible | refused — `approved_by IS NULL` required | **refused at the login guard**; over the API, refused as consumed |
| call `app_admit_workflow_step` to seize a step | needs `lease_token` | token unreadable; validated under locks | **refused at the login guard**, and the token is still unreadable behind it |
| call `app_settle_workflow_step` to fake a result | needs `claim_token` | token unreadable; validated under locks | **refused at the login guard**, and the token is still unreadable behind it |
| any of the above concurrently, twice | — | unique index serialises | **none of them enter**; over the API the index still serialises |
| forge `session_user` via `SET ROLE`, a JWT `role` claim, any JWT claim, `set_config`, a header, or an RPC parameter | n/a | n/a | **impossible** — `session_user` changes only through superuser-only `SET SESSION AUTHORIZATION` |

**The rule this encodes, in two halves.** *First:* a direct PostgREST call enters no command at all — it is refused at the login guard before any read or write, so no run, job, grant, claim or audit row can result. *Second:* a legitimate invocation over the application login produces a complete valid domain transition or changes nothing. Half-operations are not exposed, and the entrance is not shared, because neither exposure nor the transport is something the application controls.

---

## The Caller-Identity Boundary

The audit that produced v1.5. **Verified against the repository, not assumed** — the owner asked for the shape to be checked rather than trusted, and it holds.

### Two logins, one role

| | Application / worker | Supabase PostgREST |
|---|---|---|
| `session_user` | **`projectone_api`** | **`authenticator`** |
| `current_user` inside the transaction | `authenticated` | `authenticated` |
| `auth.uid()` | the verified actor (`request.jwt.claim.sub`) | the requesting user |

Evidence, file by file:

- **`d7b95c1f4e08_create_api_request_role.py`** creates `projectone_api` `NOLOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER`, grants it `authenticated`, and states outright that Supabase's `authenticator` was **rejected** for the request path — "it cannot be provisioned from here… its definition is Supabase's to change". The two logins are different *by decision*, recorded eleven revisions before this ADR.
- **`apps/api/.env.example`** sets `REQUEST_DATABASE_URL=postgresql://projectone_api.<project-ref>:…`, provisioned by `scripts/sync-request-role-credential.py`, which "generates the password, applies it to the role, PROVES it by connecting as that role".
- **`tests/conftest.py`** exercises the **real** role: `_REQUEST_ROLE_NAME = "projectone_api"`, adding only `LOGIN` and a password so that "what the tests exercise is the real role's attributes rather than a convenient local copy".
- **`tests/test_request_session.py:153`** already asserts `after[0] == "projectone_api"` once the transaction ends — the session's own identity, underneath the role switch.
- **PostgREST is `authenticator` by construction.** `d7b95c1f4e08` records that `postgres` cannot even `ALTER ROLE authenticator` on managed Supabase: it is reserved. It is Supabase's login, not ProjectOne's, and nothing in this repository can make it `projectone_api`.

### Why `session_user` is unforgeable from PostgREST

`current_user` is mutable — that is the whole point of `SET LOCAL ROLE`, and both sides use it to reach `authenticated`. **`session_user` is fixed at authentication and changes only through `SET SESSION AUTHORIZATION`, which PostgreSQL restricts to superusers.** `authenticator` is a `NOBYPASSRLS` request-path login, not a superuser.

So none of the caller-controlled surfaces reach it:

| Forgery attempt | Why it fails |
|---|---|
| `SET ROLE projectone_api` | changes `current_user`, never `session_user` — and PostgREST is not a member of it |
| a `role` claim in the JWT | PostgREST maps it to `SET LOCAL ROLE`; same limitation |
| any other JWT claim | claims become GUCs under `request.jwt.*`; no GUC feeds `session_user` |
| `set_config(...)` | cannot write `session_user`; it is not a settable parameter |
| a request header | reaches the database only as a GUC, same as above |
| an RPC parameter | **no command takes one** — the guard reads `session_user`, it is never passed |

This is why the guard is a *login* check rather than a marker: there is nothing to steal, nothing to replay, and nothing to leak, because the value is asserted by the database at connection time from a credential the client does not hold.

### The guard

**Every one of the five commands begins with this, before any read or write:**

```sql
IF session_user <> 'projectone_api' THEN
    RAISE EXCEPTION 'workflow execution commands are invocable only by the ProjectOne application login'
        USING ERRCODE = '42501';
END IF;

IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'workflow execution commands require a verified actor'
        USING ERRCODE = '42501';
END IF;
```

Four properties, each deliberate:

- **The login name is a literal in the function body.** Never a parameter, never a GUC, never a table lookup, never an allowlist. A single equality against a single hard-coded name is the whole check, and P50's boundary test fails if that stops being true.
- **It runs first.** Before any `SELECT`, any lock, any insert. A direct PostgREST call therefore changes nothing at all — no run, no job, no grant, no claim, no audit row — rather than being rolled back after doing work.
- **`auth.uid()` remains the actor.** `session_user` answers *which process is connected*; `auth.uid()` answers *who is acting*. Attribution, membership, role checks and RLS all continue to resolve through `auth.uid()` exactly as before. **The guard adds a caller check; it does not become the identity.**
- **It does not restore half-transitions.** Each command still performs its whole domain transition or nothing (D11). The guard is an additional precondition on the same complete commands, not a licence to split them.

### Function placement: `public`, and why that is not obscurity

The commands stay in `public`, where every other `app_*` helper already lives.

**They will be discoverable at `/rest/v1/rpc`, and that is harmless**, because discovery is not execution: an unauthenticated or member-authenticated call reaches the guard on its first statement and is refused with `42501` having touched nothing. Nothing about the design depends on a caller not knowing the names.

**A private, unexposed schema was considered and is not the primary mechanism** — for a reason that decides it rather than a preference. PostgREST's exposed-schema list is **Supabase project configuration, not repository state**. It cannot be asserted by a test in this repository, it can be changed in a dashboard by anyone with project access, and a security property whose enforcement lives outside version control is one this project cannot prove it still has. The `session_user` guard is enforced by the function body, which *is* version-controlled and *is* testable. A private schema would be a genuine second layer and is worth adding later as defence in depth; it is not what the boundary rests on, and it must never become a substitute for the guard.

### A documentation defect found while verifying this

`apps/api/app/core/config.py` documents `request_database_url` as "connecting as a role WITHOUT `rolbypassrls` (`authenticator`)". **That names the role `d7b95c1f4e08` rejected**, and it contradicts the migration, `.env.example` and `conftest.py`. The connection is `projectone_api`. The comment is wrong rather than merely imprecise, and it is precisely the note that would mislead the next person reasoning about this boundary. **Reported here for STEP-31 to correct; no code is changed by the task that produced this ADR.**

---

## Column Necessity

The rule applied: a column survives only if it *independently enforces* a required guarantee. Debugging convenience is not a reason.

| # | Column | Invariant it enforces | Writer | Verdict |
|---|---|---|---|---|
| 1 | `workflow_step_runs.claim_token` | I9 — one execution may persist a non-replayable step | `app_admit_workflow_step` | **Keep.** Nothing else identifies the holder. |
| 2 | `workflow_step_runs.claimed_by_job_id` | I9 predicate (2) — locates the job whose lease must still be current | `app_admit_workflow_step` | **Keep.** Without it the lease cannot be checked at all. |
| 3 | `workflow_step_runs.claimed_by_lease_token` | I9 predicate (2) — the lease that was current at admission | `app_admit_workflow_step` | **Keep.** The job's current token alone cannot detect rotation. |
| 4 | `workflow_step_runs.approved_by` | I13 — a gated step runs only on a fresh, pinned, unspent grant | `app_approve_workflow_step`; cleared by `app_admit_workflow_step` | **Keep.** Carries the grant *and* pins the granter to `auth.uid()`. |
| — | `workflow_step_runs.claimed_at` | none | — | **Removed.** v1.2 said outright that "nothing reads it to make a decision". `updated_at` already records the last write. |
| — | `workflow_step_runs.superseded_claim_token` | none | — | **Removed.** Evidence, not enforcement — and storing a raw fencing token where a client could later be granted `SELECT` is the exposure audit question 6 forbids. The supersession is audited in `audit_log` without the value. |
| — | `workflow_step_runs.approved_at` | none | — | **Removed.** Single-use is carried by `approved_by IS NULL`; "when" is history and belongs in `audit_log`, which survives consumption. |
| 5 | `jobs.workflow_run_id` | I3 (live-job uniqueness) and I4 (reconciliation target) | the enqueue path; immutable thereafter | **Keep.** Both invariants are unreachable without it. |

**Four columns on `workflow_step_runs`, one on `jobs`.**

---

## Explicit Recovery

Owner requirement 9. Recovery is a user's decision, and the state change is atomic.

### The recovery transaction

`POST .../runs/{run_id}/resume` on a `failed` run whose last step is interrupted. The whole request is already one tenant transaction (Context fact 2), so atomicity needs no new machinery:

1. Read the run and its first incomplete step. Refuse (409) unless the run is `failed` and the step is interrupted or ordinarily failed.
2. **Supersede the stale claim through `app_recover_workflow_run`** (D11), which clears `claim_token`, `claimed_by_job_id` and `claimed_by_lease_token` after refusing anything but a `failed` run and a live member. **The evidence is preserved in `audit_log`, not in a column** — run id, step index, actor, the superseding job id, and the fact that a stale claim was superseded. The raw token is never written there (audit question 6): a fencing value in an audit table is a value some future grant can expose.
3. **Branch on whether the interrupted step is gated:**
   - **Not gated** → step `status = 'failed'` (claimable), run → `pending`, **enqueue the replacement job**. One user action; execution follows.
   - **Gated** → step `status = 'awaiting_approval'`, `approved_by` remains `NULL` (the grant was consumed at admission), run → `awaiting_approval`, **no job is enqueued**. Continuing requires a *second*, separately authorized action.
4. Write an `audit_log` entry naming the run, the step index, the actor and **the fact that a stale claim was superseded** — never the token itself (I17). A recovery that may cause a second provider charge is exactly the sensitive action §16 requires auditing.

Steps 1–3 commit together. The replacement enqueue is admitted by D4's index because the old job is `dead_lettered` and therefore outside the live set.

**`resume` keeps `VIEW_WORKSPACE`.** For a gated step it grants nothing — it only re-arms the gate. The consequential half is still behind `UPDATE_WORKSPACE`.

### Approval after an interrupted approval-gated step

The path, end to end, and why each hop exists:

1. Run reaches the gated step → step and run `awaiting_approval`.
2. An owner/admin approves → `app_approve_workflow_step` writes `approved_by := auth.uid()` **and** the job is enqueued, in one transaction (D9, D1, D11).
3. A worker claims the job, then admits the step — **consuming the grant** (`approved_by` → `NULL`) inside `app_admit_workflow_step`, under `FOR UPDATE` on the step row — and calls the provider.
4. The worker dies. Step stays `running`, claimed, grant already spent.
5. A replacement worker finds the claim → terminal interruption → job dead-lettered → run `failed` (D5).
6. A member calls `resume`. Because the step is gated, the run returns to `awaiting_approval` and **nothing is enqueued**.
7. An owner/admin must approve **again** to continue.

**Approval is never inferred (requirement 10), and the reason is structural rather than procedural:** the persisted model contains no unspent grant, because admission consumed it at step 3. There is nothing to infer *from*. A design that left the grant set would let a redelivery restart a paid, gated action on the strength of a decision the user made about a different attempt — which is what §15's approval gate exists to prevent. And because consumption happens at **admission** rather than at claim time, this holds for a gated step that is also `replayable = True`, which v1.2's design would have let reuse its grant indefinitely.

### How the original worker is fenced after D5 marks the run failed

Three independent predicates, any one of which is sufficient. They are listed in the order they become true:

| # | Predicate | Becomes true when |
|---|---|---|
| 2 | `jobs.lease_token = claimed_by_lease_token AND status = 'running'` | fails as soon as the replacement worker claims the job — the claim rotates `lease_token` |
| 3 | `workflow_runs.status NOT IN ('completed','failed')` | fails the moment D5's CTE commits |
| 1 | `workflow_step_runs.claim_token = <the worker's token>` | fails once an explicit recovery supersedes the claim |

A stale worker that finishes its provider call minutes later and attempts to persist matches zero rows under **all three**, is told so, and stops. It never marks the step completed, never advances the run, and never overwrites a recovery already in progress. **The three are deliberately redundant:** each closes a different window, and any one surviving a future refactor still fences the write.

---

## Reinterpreting the STEP-31 proof

STEP-31 currently requires: *"An interrupted worker leaves a resumable run, and a redelivery resumes rather than restarting."* Under the owner's Q4 decision that wording is **too broad, and this ADR narrows it deliberately.**

The corrected reading, in four parts:

1. **Automatic redelivery may resume replayable work.** A worker interrupted between steps, or inside `validate` or `quality_check`, is re-delivered and continues from the last completed checkpoint with no user involvement. ADR-005 §6's lease recovery keeps working exactly as designed for everything genuinely idempotent.
2. **Automatic redelivery must fail safely on a claimed non-replayable step.** It acquires nothing, calls nothing, writes nothing to the step, and terminates into a reconciled `failed` run.
3. **A non-replayable interrupted step remains resumable through explicit user action**, from the last completed checkpoint — not from the beginning. `next_step_index` still counts completed steps, so recovery re-enters at the interrupted step and no completed work is repeated.
4. **It is not true that every interrupted workflow automatically resumes**, and the ADR does not claim it. That is a reduction in automatic recovery, taken knowingly.

**Why the narrowing is required rather than merely chosen.** ADR-005 §6 obliges a handler with a non-idempotent external effect to hold its own durable claim; a claim that automatically released itself so the run could self-heal would not be one. And [[CLAUDE|CLAUDE.md]] §40's "AI should think. Users should decide." is not only about features — a platform that silently re-spends a user's money to avoid showing them a failure has made the user's decision for them. §15's default that anything spending money requires approval points the same way. **A stopped run the user can continue in one click is a better product than a run that quietly pays twice**, and it is the only reading consistent with both documents.

STEP-31's proof list is updated by P13 (narrowed) and P14–P21 (new) below. Correcting that note is part of the acceptance transaction, not this task.

---

## Invariants

- **I1.** No workflow continuation executes inside an HTTP request.
- **I2.** A run reachable by a client has exactly one authoritative status, read from `workflow_runs`. No user-facing surface reads or joins `jobs`.
- **I3.** At most one job with `workflow_run_id = R` exists in `pending` or `running` at any instant, enforced by the database. **Bounds enqueue only.**
- **I4.** A job reaching `dead_lettered` while carrying a `workflow_run_id` leaves no non-terminal run behind, in the same commit. A run already `completed` or `failed` is never overwritten.
- **I5.** No handler receives, can reach, or runs while the process holds open a privileged connection.
- **I6.** A handler is never invoked outside an established, proven tenant identity.
- **I7.** No internal exception text reaches `workflow_runs.detail`, `jobs.last_error`, or any HTTP response body.
- **I8.** `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` remains **60**, computed from its three factors.
- **I9.** At most one execution can **persist** a result for a given non-replayable step, enforced by three database predicates: durable claim token, current job lease, non-terminal run.
- **I10.** A step claim is never released by elapsed time, by D5's reconciliation, by a replacement worker, or by any execution not holding its token. It is released only by its holder settling through `app_settle_workflow_step`, or by an explicit authorized recovery through `app_recover_workflow_run`, which records the supersession in `audit_log` without the token value.
- **I11.** **There is no exactly-once provider execution.** A provider may be paid for work never recorded; `AIRouter`'s in-call retry may duplicate a charge whose response was lost; both close only with provider-side idempotency keys.
- **I12.** No job settles `succeeded` on a run it did not advance. An execution that cannot acquire a claim it needs is terminally interrupted, never successful.
- **I13.** A gated non-replayable step never executes on a grant that was already consumed. Every execution of it requires a fresh, durable, single-use approval.
- **I14.** Every automatic path either advances the run or leaves it terminally reconciled. No automatic path leaves a run non-terminal with no live job.
- **I15.** **Fencing state is unreadable; approval state is readable but unwritable.** The two are different things, and v1.5's wording conflated them.
  - **Unreadable and unwritable by any client-reachable role** — `anon` or `authenticated`, through the API or through PostgREST — are the three fencing tokens: `workflow_step_runs.claim_token`, `workflow_step_runs.claimed_by_lease_token`, and `jobs.lease_token`. Each is a **capability**: a role that could read one could satisfy a settlement predicate it never earned. None appears in any client grant, and `SELECT *` on either table is refused for want of column privilege.
  - **`workflow_step_runs.approved_by` is tenant-readable audit metadata, and is client-unwritable.** It is in the `authenticated` `SELECT` grant (§D11) because it is not a capability: it names a workspace member the reader can already see, and *knowing* that a step was approved confers no ability to approve one. It appears in no client `INSERT` or `UPDATE` grant — `authenticated` holds `UPDATE (deleted_at)` on that table and nothing else — so it is written only by `app_approve_workflow_step`, which sets it to `auth.uid()`, and consumed only by `app_admit_workflow_step`, which clears it. **I16's single-use property is untouched.**
  - Execution state is changed only by the D11 commands, in every case.

  Testable as three separate statements rather than one: reading a fencing token is refused by privilege (P23); reading `approved_by` succeeds (P24); writing `approved_by` by any client path is refused by privilege, and forging it through the command is refused by role (P22).
- **I16.** An approval grant names `auth.uid()` and no one else, is valid for exactly one run, one step index and one `awaiting_approval` state, and is spendable exactly once.
- **I17.** No fencing token appears in any API response, any client-readable column, any job result or error field, any audit record, or any application log.
- **I18.** A workflow-linked job exists only where `app_start_workflow_run`, `app_approve_workflow_step` or `app_recover_workflow_run` created it. No direct client INSERT can produce one, and `job_type = 'workflow.execute'` and a non-null `workflow_run_id` imply each other.
- **I19.** Every client-callable command completes its whole domain transition or changes nothing. No granted function exposes a grant without its job, a supersession without its next state, or an enqueue on its own.
- **I20.** A handler's run target is `jobs.workflow_run_id`. No code path reads a run id from `jobs.payload`.
- **I21.** **The immutable login boundary is part of the security model.** Every workflow execution command refuses any session whose `session_user` is not the dedicated ProjectOne application login, before any read or write. The accepted login is a literal in each function body — never a parameter, a GUC, a table lookup or an allowlist — and `authenticator` is never accepted. **This invariant must be revalidated whenever the request-path or worker connection role changes, whenever Supabase's connection roles or pooler configuration change, and whenever a second application login is proposed.** A change to any of those is a change to this ADR's security model, not a configuration detail.

- **I22.** **An approval leaves a record that outlives the grant.** `app_approve_workflow_step` writes exactly one `workflow.approved` audit row in the same transaction as the grant and the job, naming the workspace, the actor from `auth.uid()`, the run, the step index and the created job id — and no fencing token of any kind. `audit_log.created_at` is the durable approval time, which is why no `approved_at` column exists. A refused or rolled-back approval leaves no row, and concurrent approvals leave exactly one grant, one job and one row.
- **I23.** **A step outcome and the run transition it causes are one transaction.** Settling a step and moving its run commit together or not at all, with the run, step and job locks the settlement takes held across both writes. No observer can see a completed final step under a non-terminal run, and no execution can act on a step between the two writes. A run transition that cannot be written rolls its step settlement back with it. An intermediate successful step moves no run state and writes none.
- **I24.** **No run is advanced against a definition it did not start under.** Before execution, recovery **and** approval, the definition this deployment would use must match the run's recorded `workflow_type` and `definition_version`. A mismatch fails closed with a fixed public-safe message: no provider is called, no step is admitted, and no claim or approval is consumed. The run is preserved unchanged, because what happens to it is a product decision rather than a runtime one.

---

## Security Boundary

**Unchanged.** Tenancy still reaches the worker as the enqueuing user's identity through `RequestSessionFactory.authenticated_as`. A handler's database access is indistinguishable from a route's. A missed role switch still fails closed (`projectone_api` is `NOINHERIT`, `rolbypassrls = false`). A revoked actor's job still dead-letters before reaching a handler.

**Changed.** One privileged statement shape may now name `workflow_runs`, bounded as D6 states.

**D8, D9 and D10 change nothing here.** Every one of them is an ordinary tenant write over an RLS-subject session — the claim, the fenced settle, the approval grant, the recovery transaction — subject to the same policies the runner already writes under. They require no privilege, add no role, and are invisible to the privileged path, which D6 forbids from touching `workflow_step_runs` at all. `JobContext` gains `lease_token`, an opaque identifier that opens nothing.

**Why the D5 widening is the smallest that works.** Three narrower options fail against the code:

1. **Reconcile over the actor's tenant session.** Fails for the revoked-membership case by construction: `b8e1d94c50a7` removes the workspace from `app_current_user_workspaces()` on soft delete, so the actor's session cannot see the run and `update_run_status` matches zero rows. The one case reconciliation exists for is the one it cannot serve.
2. **A second single-purpose privileged repository.** `AISpendRepository`-style methods each open their own connection, so the write lands in a different transaction. A crash between the two leaves exactly the inconsistency being fixed.
3. **A background sweeper.** Not atomic by definition, and a sweeper that stops running is invisible.

**And the shape adds no privilege.** A `SECURITY DEFINER` trigger on `jobs` would also be atomic and keep the dispatcher naming one table — but it creates a **new privileged principal** writing a tenant table, invocable by any path that updates `jobs`. Given a connection that already holds the access, inventing a principal to avoid widening a sentence is the worse trade. **Rejected; re-opening it requires a superseding ADR.**

**Audit.** ADR-005 §5 constraint 5 unchanged. `job_claimed` and `job_dead_lettered` already log both dead-letter sites; STEP-31 adds the reconciliation outcome to the existing event. The runner adds `workflow_step_claimed`, `workflow_step_claim_unavailable` and `workflow_step_settle_fenced`, carrying run id, step index and attempt — **never a token**. An explicit recovery writes an `audit_log` entry (§Explicit Recovery step 4).

---

## API Contract

| Endpoint | Today | Under ADR-006 |
|---|---|---|
| `POST /workspaces/{ws}/workflows/runs` | 201, run in terminal state | **202**, run `pending`, `Location: …/runs/{run_id}` |
| `POST …/runs/{run_id}/approval` | 200, run continued inline | **202**, run `pending`, `Location`; writes the durable grant (D9) |
| `POST …/runs/{run_id}/resume` | 200, run continued inline | **202**, `Location`; also the recovery endpoint (D10) |
| `GET …/runs/{run_id}` | unchanged | unchanged — and now the status monitor |
| `GET …/runs` | unchanged | unchanged |

- **Body:** `WorkflowRunResponse` throughout (D2). `Location` points at `GET .../runs/{run_id}` — for a 202 that names a status monitor, which is what the run now is.
- **Clients learn the outcome by polling.** Notification is [[STEP-34 Notifications Domain]].
- **Resume on a gated interrupted step returns 202 with the run in `awaiting_approval` and no job enqueued.** The response is honest about what happened: the gate was re-armed, and someone must approve.
- **Error statuses unchanged.** `WorkflowError` → 422, `RunNotFoundError` → 404, `RunNotResumableError` → 409. A second live job is **409**. Whether that is `RunNotResumableError` or a new sibling is **[Implementation — open to evidence]**.
- **`StepInterruptedError` never reaches a client.** It is raised inside the worker; a `WorkflowError` subclass for `classify`'s benefit, converted to a job outcome before any HTTP surface exists.
- **Permissions unchanged.** Approval stays `UPDATE_WORKSPACE`; start and resume stay `VIEW_WORKSPACE`; all three share the `workflow-run` rate-limit bucket.
- **What a caller loses:** a start that used to return `completed` or `failed` now returns `pending`.

---

## Failure Reconciliation

Under Q1, **every** dead-lettered job carrying a `workflow_run_id` reconciles:

| Cause of dead-letter | Job ends | Run ends | Written by |
|---|---|---|---|
| Revoked actor (pre-handler) | `dead_lettered`, attempt 1 | `failed` | `record_outcome` leg |
| Unregistered type (pre-handler) | `dead_lettered`, attempt 1 | `failed` | `record_outcome` leg |
| Worker died, attempts exhausted | `dead_lettered` by the reap | `failed` | `claim` leg |
| Handler raised a terminal error | `dead_lettered`, attempt 1 | `failed` **if not already terminal** | `record_outcome` leg |
| Retryable failure, attempts exhausted | `dead_lettered` | `failed` **if not already terminal** | `record_outcome` leg |
| **Replacement worker found a live claim** | `dead_lettered`, **terminally interrupted** | `failed`, interrupted message | `record_outcome` leg |

Cases that must **not** move: a run already `completed`; a run already `failed` by the runner (its specific `detail` is preserved); a job `succeeded` while the run is `awaiting_approval` (the healthy pause); a retryable failure with attempts remaining (the job returns to `pending`, stays live under I3, run untouched).

**In every case the step row is untouched and the claim survives** (I10) — evidence, fencing and cost safety at once.

---

## Concurrency and Recovery State Machine

```
NORMAL
  run pending --[job claimed; identity proven]--> run running
    replayable step      : execute freely (duplicate execution harmless)
    non-replayable step  : acquire claim (token T, job J, lease L)   [commit]
                           -> call provider
                           -> fenced settle: T current AND lease L current
                                             AND run not terminal
                           -> completed, claim cleared
  --> run completed | awaiting_approval | failed(by runner, claim cleared)

LEASE LOSS  (worker A alive, lease lapsed; worker B claims job)
  worker A : finishes in-flight provider call
             -> fenced settle matches ZERO rows (lease L superseded)
             -> writes nothing, logs workflow_step_settle_fenced, stops
  worker B : identity -> run -> reaches step
             -> acquire claim FAILS (claim_token held)
             -> raise StepInterruptedError  (terminal under classify)

DEAD-LETTER RECONCILIATION      [one CTE, one commit]
  job -> dead_lettered (safe public message)
  run -> failed        (guard: never overwrites completed | failed)
  step-> UNTOUCHED     (claim, job id and lease token preserved as evidence)

STALE-WORKER FENCING   (any ONE predicate suffices; all three apply)
  (1) workflow_step_runs.claim_token          = worker's token
  (2) jobs.lease_token = claimed_by_lease_token AND jobs.status = running
  (3) workflow_runs.status NOT IN (completed, failed)

EXPLICIT RECOVERY               [one tenant transaction]
  POST .../resume on a failed run
    app_recover_workflow_run: claim columns := NULL (audited, no raw token)
    step NOT gated -> step failed(claimable), run pending,  ENQUEUE job
    step IS gated  -> step awaiting_approval, run awaiting_approval, NO job
                      (grant was consumed at claim time; a fresh
                       POST .../approval by owner/admin is required,
                       which writes the grant AND enqueues atomically)
    audit_log entry: run, step index, actor, the FACT of supersession
                     (never the token itself -- I17)
```

---

## Rejected Alternatives

**API contract** — blocking the request until the run finishes (re-rejected from ADR-005: a browser cannot hold a multi-minute render, and a disconnecting client abandons a run still spending money); returning `job_id` (makes the queue a public contract); a new async envelope (a second response shape for one resource).

**Authority and reconciliation** — deriving run status by joining `jobs` (leaves the run row wrong and teaches readers to consult two sources); reconciling over the actor's session, a second privileged repository, a sweeper, or a `SECURITY DEFINER` trigger (each fails as set out in §Security Boundary); reconciling only pre-handler dead-letters (**superseded by Q1**).

**Execution safety**

- **`next_step_index` alone.** The v1.0 position; wrong for concurrent delivery.
- **The step-index unique constraint alone.** Deduplicates the row after every caller has been charged — tried and rejected for chat turns in `c8f1a3d54e29`.
- **The job `lease_token` alone.** Fences the settle of the *job row*; not a mutual exclusion over the work, and it does not reach the workflow tables.
- **`ExecutionBudget` and the spend ceiling.** Bound cost; do not deduplicate calls.
- **Settling `succeeded` when a claim is found held.** The v1.1 position. **Rejected by the owner and wrong on the merits:** the finder cannot prove the holder is alive, and on a dead holder it leaves a succeeded job, a `running` run, and nothing able to advance or reconcile it.
- **A lease or timeout on the step claim.** **Rejected by Q4.** An expiring claim permits exactly the overlap it was added to prevent, and re-charges a provider already paid.
- **A replacement worker expiring or stealing the claim.** Same defect, reached deliberately instead of by a timer.
- **A run-level claim instead of a step-level one.** Simpler, but strands the whole run on a kill during a pure step, so every hard restart leaves runs needing attention.
- **A PostgreSQL advisory lock keyed on the run id.** Held for a transaction, not for the life of a queued job.
- **An application-level "is a job already live?" check.** A check-then-insert is a race; §13 requires integrity from constraints.
- **Approval carried in the job payload.** Puts an authorization decision in an opaque blob with no audit trail and no record of who granted it.
- **A persisted approval that is *not* consumed by the claim.** Would let a redelivery restart a paid, gated action on a decision made about a different attempt — the inference requirement 10 forbids.

---

## Consequences

**Easier**

- Long-running workflows become expressible; [[STEP-32 Media Processing Pipeline]] unblocks.
- **The platform stops being able to silently double-charge a workspace for one workflow step.** Today nothing prevents it and nothing records it.
- **A stranded run stops being possible.** Every automatic path ends either advancing the run or reconciling it terminally (I14).
- Approval becomes an auditable record of who approved what and when, which it is not today.
- "Why did this run never move?" stops being askable.

**Harder, and what it costs**

- **One more table is reachable from the privileged path**, bounded to one statement and asserted by a rewritten guard — but the answer to "how many tables can the dispatcher touch" is permanently two.
- **A run interrupted inside a paid step does not self-heal.** It ends `failed`, visible, and a person clicks resume. **Taken knowingly under Q4**, and it narrows a STEP-31 proof (§Reinterpreting the STEP-31 proof).
- **A gated step interrupted mid-call costs the approver a second approval.** Correct under §15 and requirement 10, and it will be reported as friction at least once.
- **Seven new nullable columns across two tables.** Each traces to a stated requirement; none has a default; none rewrites a table.
- **Every future step author inherits a declaration.** `replayable` defaults safe, so forgetting costs a redundant claim rather than a duplicate charge — but a step wrongly declaring itself replayable is a defect only review catches, exactly as `requires_approval` already is.
- **Every existing API caller of start/approve/resume changes.**
- **A run can sit in `pending` while the queue is backed up**, with no notification until [[STEP-34 Notifications Domain]].

---

## Migration and Rollback Implications

One new migration, `down_revision = ca213a665ad7` (current head; the chain is linear and single-headed). `f3c82b19d4a7` (workflow_runs) precedes `a1b7c3e94f6d` (jobs), so the composite FK is constructible.

**Expand/contract, additive throughout** (§13):

1. `jobs`: `ADD COLUMN workflow_run_id uuid` — nullable, no default, no rewrite.
2. `jobs`: composite FK and the partial unique index.
3. `jobs`: `CREATE OR REPLACE FUNCTION app_jobs_queue_state_not_client_writable` adding `workflow_run_id` to the whitelist.
4. `workflow_step_runs`: the **four** columns in D8's schema block — all nullable, no defaults, no rewrite.
5. The four `SECURITY DEFINER` functions of D11, each with `SET search_path = ''` and the three containment lines (`REVOKE ALL … FROM PUBLIC`, `REVOKE ALL … FROM anon`, `GRANT EXECUTE … TO authenticated`).
6. **The grant narrowing of D11** — `REVOKE UPDATE`/`INSERT` on `workflow_step_runs` from `authenticated` with a column-level `GRANT UPDATE (deleted_at)`, and column-level `SELECT` grants on `workflow_step_runs` and `jobs` that omit every token column.

**Step 6 is not additive**, and v1.3 concluded from that it needed three ordered deployments. **The owner has withdrawn that requirement, and the reasoning behind the withdrawal matters more than the conclusion.**

**STEP-31 ships as one coordinated pre-production cutover — one branch, one PR, one commit on `main`.** The three-deploy sequence exists to protect a fleet in which old and new application instances run **at the same time**: the grant narrowing removes privileges the pre-cutover code relies on, so a still-running old instance would lose the ability to record a step. **ProjectOne has no production deployment and no rolling fleet.** There is no old instance to protect, so the sequence protects nothing and would split one coherent change across three Build Plan steps for a hazard that does not exist — which [[CLAUDE|CLAUDE.md]] §30a's one-step-one-PR rule and §35's prohibition on speculative architecture both weigh against.

What STEP-31 owes instead:

- **The migration and the code cutover land together**, so the schema and the only code that can use it are never separated in the repository.
- **Tests prove a clean-database bootstrap** — every migration from an empty database to head — and **a full migration cycle**, upgrade and downgrade, through the existing pipeline drill.
- **`projectone-dev` is migrated only after merge**, once the code on `main` matches the schema.

**For a future production system this is different, and the obligation is recorded here so it is not rediscovered under pressure.** Once ProjectOne runs instances that are replaced gradually, the grant narrowing must follow **expand → code cutover → contract**: add the columns and commands first, deploy the code that uses them, and only then withdraw the direct grants — because between the second and third steps both code versions must work against one schema (§13). **That is a deployment-planning obligation and belongs to [[STEP-82 Staging Environment and Deployment Pipeline]], not to STEP-31.** It does not split this step today.

**Rollback is not routine, and calling it reversible would be wrong.**

*Referential integrity survives.* Dropping the columns, index and functions leaves every row valid and every constraint satisfied; nothing is orphaned and no foreign key dangles.

*Enforcement state is destroyed, and some of it is unrecoverable.*

| Downgrade step | What is destroyed |
|---|---|
| Restoring the broad `authenticated` grants | The isolation itself. Every column becomes client-writable again, and the forgery paths in §Authenticated-Client Attack Surface reopen — **while the code still trusts `approved_by`**, which is strictly worse than before ADR-006, because now something depends on it. |
| Dropping `approved_by` | Every **unspent approval grant in flight**. Runs waiting at a gate lose the record that they were approved and must be approved again. The *history* survives in `audit_log`; the *entitlement* does not. |
| Dropping `claim_token`, `claimed_by_job_id`, `claimed_by_lease_token` | All fencing evidence for steps in flight, and with it the duplicate-execution protection. A step that was safely stranded becomes an ordinary `running` row that a redelivery will re-enter — **re-invoking a provider that has already been paid**. |
| Dropping `workflow_run_id` | Reconciliation, and the live-job uniqueness guard. |

**A downgrade taken while any step is claimed converts a deliberately stranded run into an automatically replayable one.** That is a cost event, not a schema event. The downgrade path must therefore refuse to run silently: it is a decision, taken with the queue drained, and the ADR records it as such rather than as reversibility.

**No backfill.** Jobs enqueued before the migration are `TenantProbeHandler` jobs with no run; steps recorded before it are complete or failed, and an unclaimed historical row is correct.

**v1.2 left this as “consider, do not assume” and that was the defect.** It noted that `workflow_step_runs` has no write guard, then reasoned that “no endpoint exposes an arbitrary column write today” — which is exactly the *the UI does not expose it* argument the audit forbids, and it is wrong here because PostgREST is an endpoint the application does not control. The question is settled in D11 rather than deferred: the grant is withdrawn, so there is nothing left for a guard to guard.

---

## Callers and Tests That Must Change

**Application code**

- `app/routers/workflows.py` — all three routes enqueue, 202, `Location`; `approval` writes the durable grant; `resume` carries the recovery transaction.
- `app/jobs/handlers.py` — the workflow handler; builds repository and definition inside `context.tenant_session()`; converts `StepInterruptedError` into a dead-lettered outcome; carries the four-part duplicate-safety docstring.
- `app/jobs/registry.py` — `REGISTERED_HANDLERS` gains it.
- `app/jobs/contract.py` — `JobContext` gains `lease_token` and `workflow_run_id`; `StepInterruptedError` classified terminal.
- `app/jobs/worker.py` — passes `lease_token` into `JobContext`.
- `app/repositories/jobs.py`, `app/jobs/service.py` — the workflow enqueue path calls the D11 commands rather than inserting directly; translate 23505. `JobService.enqueue` keeps its direct INSERT for non-workflow types, which the new policy still permits.
- `app/repositories/job_dispatch.py` — the two reconciliation legs; `claim`'s `RETURNING` adds `workflow_run_id` (still `jobs` alone, so D6's bound is unaffected).
- `app/repositories/workflows.py` — conditional claim, three-predicate fenced settle, approval grant, recovery supersession.
- `app/workflows/models.py` — `WorkflowStep.replayable`, `StepInterruptedError`.
- `app/workflows/runner.py` — claim before a non-replayable step; stop cleanly when fenced, writing nothing.
- `app/workflows/agents.py` — `ValidateProjectStep` and `QualityCheckStep` declare `replayable = True` with the reasoning verified above; `PlanningAgent` inherits `False`.
- `migrations/versions/` — one new revision.

**Public API callers**

- `apps/api/tests/test_workflows_api.py` — **the only caller of the three endpoints in the repository.** Roughly a dozen tests assert a terminal run in the POST response. Each becomes enqueue → drive the worker → assert persisted state.
- **`apps/web` has no caller.** `lib/api.ts` exposes `listWorkflowRuns` only; `ApiRunStatus` already includes `pending` and `started_at` is already nullable, so no type changes.

**Tests that change because a rule changed**

- `tests/test_job_boundary.py` — `TestConstraintOneOneTable` rewritten per P8, plus an assertion that `workflow_step_runs` never appears in the dispatcher.
- `tests/test_job_queue.py` — the index, both reconciliation legs, the write-guard whitelist entry.
- `tests/test_job_worker.py` — the revoked-membership test gains the run-state assertion.
- `tests/test_workflow_engine.py` — **changes, where v1.0 said it would not.** D8 alters how the runner enters a step, so `FakeWorkflowRepository` must model the conditional claim and the fencing predicates. `WorkflowRunner`'s execution *semantics* are unchanged; its *entry and settle protocol* is not. v1.0's claim was wrong once D8 exists and is corrected here rather than quietly dropped.

---

## Required Proofs

Proven by test, against a real database wherever the claim is about the database.

- **P1.** A run started via the API is `pending` in the 202 response and reaches its terminal state **in the worker**, asserted from persisted state.
- **P2.** All three endpoints return 202 with `Location` resolving to `GET .../runs/{run_id}`.
- **P3.** Approval enqueues and does not execute inline — asserted directly, not from timing.
- **P4.** **Duplicate enqueue:** two concurrent enqueues for one run produce one job and one 409.
- **P5.** A revoked actor's job dead-letters without reaching the handler **and** leaves the run `failed`.
- **P6.** A job dead-lettered by the reap leaves the run `failed`, asserted with no worker alive.
- **P7.** A job dead-lettered while its run is `completed` leaves it `completed`. Repeated for `failed`.
- **P8.** **The rewritten boundary guard**, asserting all of: exactly **two** SQL literals in `job_dispatch.py` name `workflow_runs`; each is an `UPDATE` carrying the workspace match, `deleted_at IS NULL`, and the `NOT IN ('completed','failed')` guard; neither returns any column but `r.id`; **no literal contains a `SELECT … FROM public.workflow_runs`**; `workflow_step_runs` appears **zero** times; every other tenant table appears zero times; every statement still names `public.jobs`; and the guard fails if the reconciliation SQL is deleted. **The count is asserted, so a third `workflow_runs` statement fails the build.**
- **P9.** `JobContext` exposes `tenant_session` and `lease_token` and nothing from the forbidden set; no handler module reaches `JobDispatchRepository`, `Settings` or `psycopg.connect`.
- **P10.** A handler is never invoked before identity is established and proven.
- **P11.** No internal exception text appears in `workflow_runs.detail`, `jobs.last_error`, or any response body.
- **P12.** `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` is still 60 and still computed from its factors; the handler declares `max_attempts` within `MAX_JOB_ATTEMPTS`.
- **P13.** **Narrowed:** a sequential redelivery interrupted **between steps or inside a replayable step** resumes rather than restarts. An approval granted in one process releases a run executing in another.
- **P14.** **A stale worker cannot persist.** Claim a step under job J with lease L1; re-claim the job so `lease_token` rotates; the original execution's fenced settle matches **zero rows**, the step row is byte-for-byte unchanged, and the run is unchanged. Repeated for each predicate independently: wrong claim token; superseded lease; run already reconciled `failed`.
- **P15.** **The replacement worker calls no provider.** With a step claimed and the lease expired, a second worker claims the job, fails to acquire the step, and the provider stub's call count is **unchanged**. Asserted on the stub, not on logs.
- **P16.** **The replacement worker does not report success.** Its job ends `dead_lettered`, never `succeeded`, and the run ends `failed` with the interrupted public message — the v1.1 defect, asserted directly.
- **P17.** **The claim survives reconciliation.** After D5 marks the run `failed`, the step still holds its `claim_token`, `claimed_by_job_id` and `claimed_by_lease_token`.
- **P18.** **Explicit recovery continues, and only explicitly.** `resume` on the interrupted run supersedes the claim through `app_recover_workflow_run`, enqueues exactly one job, and a worker then completes the run with **exactly one further provider call**. No provider call occurs between the interruption and the resume request.
- **P19.** **Approval is never inferred.** For an interrupted *gated* step: `resume` returns the run to `awaiting_approval`, enqueues **nothing**, and the provider call count is unchanged; a fresh approval by an owner/admin then enqueues and completes; a member's approval is 403.
- **P20.** **The claim is conditional**, proven with concurrent callers: N executions attempt one step, exactly one receives a token — the shape `c8f1a3d54e29` verified with four callers.
- **P21.** `replayable` defaults to `False` on a step that does not declare it, mirroring `test_approval_defaults_to_required`; `PlanningAgent` is claimed; `ValidateProjectStep` and `QualityCheckStep` are not.

**Security proofs, added in v1.3. Each is run over the `authenticated` role directly — not through the API — because that is the role a PostgREST client holds.**

- **P22.** **A member cannot forge a grant.** Connected as `authenticated` with a member's claim, a direct `UPDATE public.workflow_step_runs SET approved_by = <owner uuid>` is refused by privilege, and `app_approve_workflow_step` called by a member is refused by role. Repeated for `INSERT`.
- **P23.** **A member cannot touch claim state.** Direct `UPDATE` of `claim_token`, `claimed_by_job_id` or `claimed_by_lease_token` is refused by privilege; `UPDATE … SET deleted_at = now()` still succeeds, so erasure is unbroken.
- **P24.** **No token is readable by a client.** `SELECT claim_token FROM public.workflow_step_runs` and `SELECT lease_token FROM public.jobs` are both refused for `authenticated`, while a full `SELECT` of the granted columns succeeds — so a member still sees their runs and queue.
- **P25.** **The handler trusts no approval fact from the payload.** A job whose payload asserts approval does not admit a gated step whose `approved_by` is null; asserted on the provider stub's call count.
- **P26.** **The grant is single-use, including for a gated replayable step.** A step declared `requires_approval = True` **and** `replayable = True` consumes its grant at admission; a redelivery of the same job is refused and calls no provider.
- **P27.** **The grant is pinned six ways.** `app_approve_workflow_step` is refused for: a non-member; a member (wrong role); a run in another workspace; a run not `awaiting_approval`; a step index the run is not waiting on; and a step whose `approved_by` is already set.
- **P28.** **Settlement cannot race the lease.** With the settle function blocked between its locks and its write, a concurrent job re-claim cannot rotate `lease_token` past it: either the settle wins with a lease that was current under `FOR SHARE`, or it is refused. Asserted with two concurrent sessions against real PostgreSQL.
- **P29.** **Every function fails closed.** Each of the four is called with, in turn: a forged actor id in a parameter (there is none to pass — asserted structurally); a wrong workspace; a wrong run; a wrong step index; a stale status; a consumed approval; a stale lease token; and a claim token belonging to another execution. All refuse.
- **P30.** **No token reaches an audit record or a log line.** The `audit_log` row for a supersession carries run id, step index, actor and job id, and no token value; the runner's log events carry no token. Asserted by scanning the written record and the captured log output for the token's text.

**Enqueue-surface and RPC proofs, added in v1.4. All are executed AS `authenticated` — direct SQL and direct `/rest/v1/rpc` — because that is the role a PostgREST client holds.**

- **P31.** **A direct INSERT cannot set `workflow_run_id`.** `INSERT INTO public.jobs (…, workflow_run_id) VALUES (…, <own run>)` is refused by `jobs_insert_member`, for every job type.
- **P32.** **A direct INSERT cannot construct a workflow execution job.** `job_type = 'workflow.execute'` with a `NULL` link is refused by `ck_jobs_workflow_link_matches_type`; with a non-null link it is refused by the policy. No combination of `job_type` and `payload` produces a valid workflow job, and a payload asserting a run id on a non-workflow job drives nothing.
- **P33.** **A direct INSERT cannot cross a workspace.** A run id from another workspace is refused by the policy and, with the policy suspended in the test harness, again by `fk_jobs_workflow_run_id_workflow_runs`. Both gates are asserted independently, so neither is load-bearing alone.
- **P34.** **Every command carries its containment.** Reading `pg_proc` for the five: `prosecdef` true, `proconfig` contains `search_path=`, every table reference in `prosrc` is `public.`-qualified, and no body contains `EXECUTE`, `format(` or any string-built statement.
- **P35.** **Execution is granted only where required.** `has_function_privilege('anon', …)` is false and `has_function_privilege('authenticated', …)` is true for all five; `PUBLIC` holds none.
- **P36.** **No command takes an actor.** No parameter of any of the five is an actor id, asserted from `pg_proc.proargnames`; each body references `auth.uid()`.
- **P37.** **The statement boundary holds.** The five bodies reference only `public.workflow_runs`, `public.workflow_step_runs`, `public.jobs`, `public.audit_log` and the two existing helpers, and contain no `DELETE` or `TRUNCATE`.
- **P38.** **No half-transition is reachable by RPC.** Calling `app_approve_workflow_step` produces a grant **and** exactly one live job, or neither; calling `app_recover_workflow_run` produces either a superseded claim with a live job, or a superseded claim with the gate re-armed and no job — never a `failed` run with a cleared claim and neither.
- **P39.** **Duplicate approval RPC.** Two concurrent calls for one run consume **one** grant and create **one** live job; the loser raises and rolls its grant back. Repeated serially: the second call is refused because `approved_by` is already consumed.
- **P40.** **Duplicate resume RPC.** Two concurrent `app_recover_workflow_run` calls create **one** live job.
- **P41.** **A forged payload run id is unreachable.** A workflow job whose `payload` names run B while its `workflow_run_id` names run A advances **run A only**; run B is untouched. Asserted on persisted state.

**Added in v1.7**, and every one of them proves a property this ADR already asserted:

- **P42.** **An approval is audited.** `app_approve_workflow_step` writes exactly one `workflow.approved` row naming the workspace, `auth.uid()`, the run, the step index and the created job id, with `created_at` as the approval time. No lease or claim token appears in it.
- **P43.** **A refused approval writes nothing.** A member's refusal and an approval named at the wrong step each leave the audit table exactly as they found it. Four concurrent approvals leave one grant, one job and one audit row.
- **P44.** **The history survives consumption.** After admission clears `approved_by`, the `workflow.approved` row and its actor are still readable. This is the property §Column Necessity relies on when it declines an `approved_at` column.
- **P45.** **No observer sees every step complete under a live run.** With the settling transaction held open, a second connection sees neither write; after commit it sees both. The contradictory state is unobservable at every instant.
- **P46.** **A failed claimed step cannot be re-entered across the boundary.** An execution attempting admission while the settlement is uncommitted blocks on the locks the settlement holds, and after commit is refused by the terminal run. It never admits.
- **P47.** **A failed run transition rolls its step settlement back.** Driven through the real runner against a real database: the step row the pair would have written does not exist, while an unrelated intermediate step committed earlier is untouched.
- **P48.** **The lock order is uniform.** Every command takes run, then step, then job — asserted against the installed function bodies, not the migration source.
- **P49.** **A redelivery after completion is a success.** It calls no provider, changes no workflow state, settles `succeeded`, and is never dead-lettered.
- **P50.** **The worker refuses a run whose version moved.** No provider call and no step admitted.
- **P51.** **Recovery refuses before reading `requires_approval`.** The failed run is left exactly as it was; 422 with the fixed message.
- **P52.** **Approval refuses rather than enqueueing work the worker will reject.** `approved_by` stays null and no job is created.
- **P53.** **A matching version is unaffected.** The ordinary path is unchanged, asserted on a completed run and one provider call.
- **P54.** **Both new child foreign keys lead a covering index**, and the index is not narrowed by `status` — terminal linked rows are exactly the ones referential maintenance must still find. The whole-schema advisor check runs alongside it against a recorded baseline of pre-existing findings.
- **P42.** **Authorization boundaries on the approval command.** A member is refused; an owner/admin is refused for a run that is not `awaiting_approval`, for a step index the run is not waiting on, and for a step whose grant is already consumed. Each refusal changes nothing.
- **P43.** **Commands return no tenant data.** Each of the five returns only a uuid, a boolean or `NULL` — asserted against `pg_proc.prorettype`, so a future change returning a row or a `SETOF` fails the guard.
- **P44.** **The index is still the final authority.** With every command's checks passing concurrently, the partial unique index alone decides: exactly one live job survives, proven with concurrent sessions against real PostgreSQL.

**Caller-identity proofs, added in v1.5. These are the ones that make D11's boundary real rather than described.**

- **P45.** **The application connection is what this ADR says it is.** From the real request-path connection: `session_user = 'projectone_api'`; `current_user = 'authenticated'` inside the transaction; `auth.uid()` is the intended actor. Extends `test_request_session.py`, which already asserts the session reverts to `projectone_api`.
- **P46.** **All five commands work through the repository path.** Start, approve, recover, admit and settle each succeed over the application connection with a legitimate actor, and their transitions land in full.
- **P47.** **Direct PostgREST is refused, and writes nothing.** Each command called at `/rest/v1/rpc` as a member, as an owner/admin, and as an unrelated-workspace user raises `42501`, and **no run, job, approval grant, claim, audit row or status change exists afterwards** — asserted by comparing full table snapshots taken before and after, not by checking the error alone.
- **P48.** **`session_user` cannot be forged.** From a PostgREST-shaped session (`session_user = authenticator`): `SET ROLE projectone_api`; a `role` claim in the JWT; an arbitrary JWT claim; `set_config('session_user', …)`; a request header; and an attempt to pass the login as an RPC parameter. Each either errors or leaves `session_user` unchanged, and the commands still refuse.
- **P49.** **A direct caller bypasses nothing, because it enters nothing.** Workflow-type validation, definition-version validation, the `workflow-run` rate limiter and approval routing are all unreachable from `/rest/v1/rpc`, asserted by the absence of any state change rather than by reasoning about the route.
- **P50.** **The boundary test.** Fails if: the `session_user` check is removed from any command; the accepted login becomes a parameter, a GUC, a table lookup or a list; `authenticator` appears anywhere in a command body; or a second login is accepted. Asserted by reading the function bodies from `pg_proc`, the way `test_job_boundary.py` reads the dispatcher's SQL.
- **P51.** **The route still limits before it invokes.** `POST .../runs`, `.../approval` and `.../resume` each still carry `limit_by_user("workflow-run", limit=20, window_seconds=60)`, and the 21st call in a window is refused **without** the command being invoked — asserted on the absence of a new run and job, not only on the 429.
- **P52.** **The worker's access does not widen.** Admit and settle succeed from the worker under `session_user = projectone_api`, `current_user = authenticated` and the enqueuing actor's `auth.uid()`, while that same session still reads nothing outside the actor's workspaces and still cannot read `lease_token`, `claim_token` or `claimed_by_lease_token`.

---

## What of ADR-005 Remains Binding

| ADR-005 decision | Under ADR-006 |
|---|---|
| §1 — PostgreSQL table queue, `FOR UPDATE SKIP LOCKED`, polling not push | **Unchanged and binding** |
| §2 — no task framework | **Unchanged and binding** |
| §3 — worker is a second entrypoint; one job at a time; strict startup validation | **Unchanged and binding** |
| §4 — tenancy is the enqueuing user's identity replayed through RLS; revoked membership fails permanently; short discrete transactions; system actors deferred to STEP-74 | **Unchanged and binding** |
| §5 constraint 1 — one table | **Superseded by D6** — two tables, one by a single statement shape |
| §5 constraint 2 — three statements | **Superseded by D6** — three operations, two carrying the reconciliation leg |
| §5 constraints 3, 4, 5, 6 | **Unchanged and binding**; 5 extended to log reconciliation and recovery |
| §6 — at-least-once, bounded by a lease; **handlers must be duplicate-safe, and a handler with a non-idempotent external effect must hold its own durable claim** | **Unchanged and binding — D8 is how the workflow handler finally satisfies its second half** |
| §7 — retries classified then counted; ceilings per handler; **60 upstream requests per enqueue**; dead-lettering is an observability event | **Unchanged and binding** |
| §Scope Boundaries — scheduling, notifications, `LISTEN`/`NOTIFY`, **provider idempotency keys**, hosting | **Unchanged and still out of scope**; provider idempotency re-confirmed as the only thing that closes I11 |

Every tenant protection survives intact. Every retry ceiling survives intact. The composed ceiling of 60 survives intact and is re-asserted by P12.

---

## Acceptance Gate

- **Approved by:** the project owner, 2026-08-20. Claude drafted and recommended; it does not self-approve architectural proposals (§7).
- **Classification:** Critical under §21 — multi-tenancy boundary, database schema, and a public API contract.
- **Implementation may now begin.** STEP-31's readiness contract has been synchronized against this note; the step itself stays `Not Started` until implementation actually starts, and the [[Build Plan]] index is unchanged.
- **Q1–Q5 are all resolved** and applied. **No question is left open for the owner.**
- **D11 is approved only if an unforgeable boundary separates application and worker calls from direct PostgREST calls** (owner, 2026-08-20). §The Caller-Identity Boundary establishes it from `d7b95c1f4e08`, `.env.example` and `conftest.py`: the application connects as `projectone_api`, PostgREST as `authenticator`, and `session_user` is superuser-only to change. P45–P52 prove it.
- **D11's other containment conditions** are asserted by P34–P37. v1.4 consolidates it from four functions to five commands so that no client-callable half-transition remains, and adds the protected workflow enqueue that v1.3 was missing.
- **D11 is also the condition on which D9 was accepted.** The owner accepted durable single-use approval "only if the persisted approval and claim state cannot be forged, cleared, reused, or manipulated through a normal authenticated database path." Under v1.2 it could be, through PostgREST, by any member. D11 is what makes the condition true, and it is the one decision in this ADR that adds a privilege — four `SECURITY DEFINER` functions, bounded and contained exactly as `app_workspace_role` already is. **It needs the owner's explicit sign-off as a privilege decision, not as an implementation detail.**
- **STEP-31 ships as one coordinated pre-production cutover**, one branch and one PR (§Migration and Rollback Implications). The three-deploy sequence v1.3 proposed is withdrawn: there is no production fleet to protect, and it is recorded instead as a future obligation belonging to [[STEP-82 Staging Environment and Deployment Pipeline]].
- **The acceptance transaction, performed 2026-08-20:** ADR-006 → `Accepted`; ADR-005 → `Superseded`, naming ADR-006; both Navigation blocks linked; STEP-31's readiness contract corrected — its duplicate-safety wording, its "redelivery resumes rather than restarting" proof (§Reinterpreting the STEP-31 proof), its surfaces and its proof list. **The architecture notes [[Async Job Execution]], [[Workflow Execution]] and [[Table - jobs]] are updated by STEP-31 itself**, in the same change that makes their descriptions true — documentation follows the implementation it describes ([[CLAUDE|CLAUDE.md]] §19), and editing them now would describe behaviour the code does not yet have.
- **This note is now closed to amendment.** A `proposed` ADR is edited in place; an accepted one is superseded by a successor, never rewritten (§Status).

---

## Related

- Supersedes (on acceptance, in part): [[ADR-005 Async Job Queue and Worker Execution Model]]
- Implements the first task of: [[STEP-31 Workflow Async Execution]]
- Builds on: [[STEP-30 Async Job Infrastructure]] · [[STEP-22 Minimum Workflow Engine]] · [[STEP-23 AI Chat End to End]]
- Unblocks: [[STEP-32 Media Processing Pipeline]]
- Governed by: [[CLAUDE|CLAUDE.md]] §7 · §13 · §14 · §15 · §15a · §16 · §21 · §23 · §26 · §39 · §40

---

## Navigation

- **Previous:** [[ADR-005 Async Job Queue and Worker Execution Model]]
- **Next:** —
- **Parent:** [[Home]]
- **Related Notes:** [[STEP-31 Workflow Async Execution]] · [[Async Job Execution]] · [[Workflow Execution]] · [[AI Cost Governance]] · [[API Conventions]] · [[API Endpoints]] · [[Security Architecture]]
