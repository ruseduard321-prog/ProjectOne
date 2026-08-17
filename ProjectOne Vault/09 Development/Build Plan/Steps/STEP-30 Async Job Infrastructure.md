---
title: STEP-30 Async Job Infrastructure
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-17
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-30
step_status: Not Started
detail_level: full
phase: "Platform Substrate"
---

# STEP-30 — Async Job Infrastructure

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** full — expanded 2026-08-17 by [[STEP-29 Asset Management UI]], per [[Execution Protocol#The Loop]] item 11, against `main` @ `1a5f1e3`.

> [!important] Implementation cannot begin until an ADR is `Accepted`
> This step introduces a **queue technology and a second deployed process**. Both are §10 stack-table decisions, so [[CLAUDE|CLAUDE.md]] §7 and §39 require an ADR before any production code is written — and §7's lifecycle is explicit that code written against a `Draft` or `Review` ADR is a spike, not the step.
>
> **The first task below is therefore to write ADR-005, not to write a worker.** The step stops there until the project owner moves it to `Accepted`; that gate is a real stop and silence is not approval.

## Objective

Introduce a worker and queue so work can outlive the HTTP request that started it.

## Why This Step Exists Now

The audit's second-largest blocker. `WorkflowRunner` executes every step synchronously inside the request that started it, so a multi-minute render cannot be a workflow — the client would wait for it, and any timeout anywhere between the browser and the API would abandon a run that is still charging money. [[STEP-31 Workflow Async Execution]], [[STEP-32 Media Processing Pipeline]] and every long-running capability after them are blocked on this.

## Dependencies

- [[STEP-27 Storage Provider Abstraction]] — `Done`.
- [[STEP-28 Asset Upload and Download]] — `Done`. Not named in the outline, but it is the step that made storage configuration **required at startup**, which a second process now has to satisfy too.

## Inherited from earlier steps

Recorded during synchronization, not expansion.

- **`WorkflowRunner` is already resumable, and that changes what this step builds.** Its docstring states the property and the code provides it: state is written after *each* step, and `next_step_index` counts only `completed` steps, so a run identified by its id alone can be resumed with no in-memory context. **The queue's job is therefore to drive an existing resumable engine, not to become one.** A job handler is "advance run X from wherever it got to" — see [[#What expansion found that the outline did not anticipate]] item 1.
- **The runner already fails loudly and does not retry.** Its own words: `AIRouter` owns retries for AI calls, and "a runner retrying on top of that would multiply a ceiling nobody wrote down" (§15a). A job-level retry is a **third** layer over those two, and this step owns proving the total is bounded rather than adding to it blindly.
- **Storage configuration is required at startup** since STEP-28 Task 1. A worker process that touches assets must satisfy the same `PROJECTONE_R2_*` validation, or it will fail at a user's first job rather than at deploy.
- **Every AI call already draws against a budget and a circuit breaker** (`app/ai/governance.py`). Moving execution into a worker must not move it outside that accounting — an async run that escapes the ceiling is §15a's central failure.

## What expansion found that the outline did not anticipate

Five facts came out of reading the merged code rather than the plan.

**1. Idempotency is mostly already paid for, and the outline overstates the work.** The Scope asks for "idempotency expectations on handlers, since at-least-once means a handler will eventually run twice." For the one handler this step will actually have, duplicate delivery is close to harmless already: `next_step_index` counts completed steps, so a second delivery of "advance run X" resumes from the same place the first one reached. **What is not yet safe is two workers running the same job concurrently** — nothing claims a run, so both would execute the same step and both would charge for it. That is a claim/lease problem, not a general idempotency problem, and it is the one this step must solve.

**2. There is no `infrastructure/` directory.** [[CLAUDE|CLAUDE.md]] §9 specifies one and the repository does not have it — the only deployment artefact is `.github/workflows/ci.yml`. "Deployed alongside the API" therefore has nowhere to be written down, and this step either creates that home or ships a worker nobody can deploy.

**3. No queue dependency exists, and adding one is a stack decision.** `apps/api/pyproject.toml` has no broker, no task library and no Redis client. Whatever is chosen is an addition to the §10 table and needs the ADR named above.

**4. A database-backed queue would be the third consumer of the same PostgreSQL, and the tenant question is sharper than the outline states.** The Risks section already flags that a worker without tenant context is a cross-tenant bug no route test would catch. Reading the storage work makes the mechanism concrete: RLS filters on a workspace id that arrives with the *request*, and a worker has no request. **Whatever carries tenancy into the worker becomes a security control**, and it must be one that cannot be forgotten by the next handler's author rather than one each handler remembers.

**5. Retry ceilings would become three layers deep.** `AIRouter` retries a provider call; `ExecutionBudget` bounds a run; a job queue would retry the job. Three independent ceilings multiply unless someone states the product. §15a requires "a hard maximum retry count" and a total ceiling — so this step owes an explicit statement of the worst-case number of provider invocations one enqueue can cause, not three separately reasonable limits.

## Scope

- A queue and a worker process, deployed alongside the API.
- A job contract — enqueue, execute, record outcome — with **at-least-once** semantics stated explicitly.
- A **claim or lease** so two workers cannot execute the same job concurrently (item 1 above).
- Idempotency expectations on handlers, documented as a rule handlers must satisfy.
- Failure, retry ceiling and dead-letter handling, bounded per [[CLAUDE|CLAUDE.md]] §15a — including the **composed** ceiling across all three retry layers (item 5).
- Tenant context carried into the worker by construction, and enforced there.
- Observability: a job's state is inspectable without attaching a debugger.

## Out of Scope

- No workflow engine integration — [[STEP-31 Workflow Async Execution]]. **This step ships the infrastructure and proves it on a trivial handler**; making workflow runs actually asynchronous is the next step.
- No scheduling or cron — [[STEP-74 Workflow Scheduling and Triggers]].
- No new product feature, and no user-visible surface.
- **No change to `WorkflowRunner`'s execution semantics.** It is already resumable; this step drives it, it does not rewrite it.
- **No notification of job completion** — that is [[STEP-31 Workflow Async Execution]] onward. A user watching a job finish is a different problem from a job finishing.

## Surfaces Affected

**Backend:** `app/jobs/`, a worker entrypoint, and configuration validation for the second process. **Infrastructure:** a queue service, a worker deployment, and CI coverage — plus, per item 2, the `infrastructure/` directory itself. **Database:** job state, if the ADR chooses a database-backed queue.

## Required Documentation

A candidate list, not a reading list ([[Execution Protocol#Context Discipline]] rule 2).

| Document | The question it answers | Likely needed |
|---|---|---|
| `app/workflows/runner.py` | What is already resumable, and what is not? | **Yes** — read during expansion; the handler drives it |
| `app/ai/governance.py` | Where are the existing ceilings, and what do they bound? | **Yes** — the composed ceiling depends on it |
| `app/core/config.py`, `main.py` | How is startup configuration validated, and how does a second process reuse it? | **Yes** |
| [[Workflow Engine]] | Which execution principles are binding? | **Yes** — the five the runner names |
| [[Infrastructure]] | What deployment shape is specified? | **Yes** — item 2 says the repository does not match it |
| [[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]] | How was the last vendor choice argued? | As the template for ADR-005 |
| [[Security Architecture]], [[Authentication and Authorization]] | How is tenant context established today? | **Yes** — item 4 makes this the Critical surface |

## Tasks

### 1. ADR-005 — the queue, and the second process

Write it first, and stop. Nothing below may begin until the owner moves it to `Accepted` (§7).

It must decide, with alternatives named and rejected:

- **The queue itself.** A PostgreSQL-backed queue (`SELECT … FOR UPDATE SKIP LOCKED`) adds no infrastructure and no dependency, at the cost of polling and of putting queue load on the primary database. A dedicated broker is the conventional answer and is a new service to run, secure and pay for. The honest comparison is at this product's scale, not at a hypothetical one.
- **Whether a task framework is adopted at all**, or the contract is written directly. A framework brings retries, dead-lettering and a worker loop; it also brings its own configuration surface and its own opinions about serialization.
- **How tenancy reaches the worker** (item 4). This is the security half and must be argued as such, not left as an implementation detail.
- **Where the worker is deployed and how it is configured**, given that `infrastructure/` does not yet exist.

### 2. The job contract

- Enqueue, execute, record outcome. **At-least-once, stated in the contract's own docstring** rather than implied — a handler author who has to infer the delivery guarantee will infer the convenient one.
- A job carries its workspace id as a required field, not an optional one, so tenancy cannot be omitted by a handler that forgot.
- Handlers declare their retry ceiling explicitly; no default that silently permits unbounded work (§15a).

### 3. Claim or lease

- A job in flight is claimed, so a second worker does not execute it concurrently (item 1).
- A claim expires, or a worker that dies holds a job forever.
- **State plainly what happens when a lease expires mid-execution**: the job becomes eligible again while the original may still be running, which is exactly the at-least-once case handlers were told to expect.

### 4. Retry, dead-letter, and the composed ceiling

- A bounded retry count per job, then a dead-letter state that is visible rather than a silently dropped row.
- **Write down the product of all three retry layers** (item 5): provider retries × job retries, against the run's execution budget. The number belongs in the code as a named constant with the arithmetic beside it, so the next person to raise one layer sees what they are multiplying.
- A dead-lettered job is a §26 observability event, not just a status.

### 5. Tenant context in the worker

- The workspace id travels with the job and establishes the same RLS context a request would.
- **Proven by a test that fails if the context is dropped** — a worker executing a job for workspace A must not be able to read workspace B, asserted directly rather than assumed from the presence of a parameter.
- No "the worker is internal so it can use elevated access" path. §16 forbids it for admin tooling and forbids it here for the same reason.

### 6. Observability

- A job's state, attempts, last error and dead-letter status are inspectable without a debugger.
- Correlation ids carry from the enqueuing request into the worker's logs, or an async failure cannot be traced back to what caused it.

### 7. Tests

Every proof in [[#Required Tests and Proofs]], plus:

- A test that the composed retry ceiling is what Task 4 says it is.
- Worker startup fails without the configuration it needs, matching what STEP-28 Task 1 established for the API.

### 8. Documentation

- Record the deployment shape in `infrastructure/`, creating it if the ADR calls for it.
- Update [[Infrastructure]] and [[Workflow Engine]] where this changes what they describe.
- Update this note's status and the [[Build Plan]] index row together.
- Expand [[STEP-31 Workflow Async Execution]] to full detail.

## Decisions

Everything in [[#Task 1 — ADR-005 — the queue, and the second process]] is a decision this step cannot take alone, and none is resolved. They are deliberately gathered into one ADR rather than listed here as D1–D4, because they are a single coupled choice: the queue, the framework, the tenancy mechanism and the deployment shape each constrain the others.

## Required Tests and Proofs

- A job survives an API process restart.
- A handler that fails is retried up to its ceiling and then dead-lettered, not retried forever.
- Duplicate delivery does not duplicate effects, proven on a real handler.
- **Two workers cannot execute the same job concurrently**, proven rather than assumed from the presence of a claim.
- Tenant context is carried into the worker and enforced there — a job for one workspace cannot read another's rows.
- Worker startup fails loudly when its configuration is absent.

## Definition of Done

A job can be enqueued, executed by a separate worker, retried within a bounded ceiling, dead-lettered on exhaustion, and observed throughout — with tenant scoping proven inside the worker.

Additionally, per [[Execution Protocol#Step Completion]]:

- [ ] **ADR-005 `Accepted` by the project owner** before implementation began.
- [ ] The composed retry ceiling stated as a number, with its arithmetic.
- [ ] Required CI green, and the manual checklist complete.
- [ ] Owner approval obtained — this step is Critical.
- [ ] Status synchronized between this note and the [[Build Plan]] index.
- [ ] [[STEP-31 Workflow Async Execution]] expanded to full detail.

## Risks and Governance Gates

**Critical** — infrastructure, a new execution context where RLS is easy to lose, and a technology addition to the §10 stack table. Owner approval is required before merge, and ADR-005 must be `Accepted` before implementation begins.

- **A worker that runs without tenant context.** The failure the outline named, and expansion sharpened: RLS filters on a workspace id that arrives with a request, and a worker has no request. A cross-tenant read here would pass every route test in the suite.
- **A ceiling that is three ceilings multiplied.** §15a's worst case — "an infinite retry loop that degrades gracefully into an infinite bill" — reached not by anyone removing a limit but by three reasonable limits composing.
- **A queue on the primary database becoming its load problem.** If the ADR chooses that shape, polling frequency and index behaviour are part of the decision, not a later tuning exercise.
- **A dead-letter state nobody looks at.** A job that failed silently and is recorded silently is §26's "a system that can fail in a way nobody would notice".

## Audit Gaps Closed

**Background / async execution** — *Foundation / Partial, P0, no step*

---

## Navigation

- **Previous:** [[STEP-29 Asset Management UI]]
- **Next:** [[STEP-31 Workflow Async Execution]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]] · [[Workflow Engine]] · [[Infrastructure]]
