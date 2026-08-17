---
title: STEP-30 Async Job Infrastructure
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-17
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-30
step_status: In Progress
detail_level: full
phase: "Platform Substrate"
---

# STEP-30 — Async Job Infrastructure

**Status:** In Progress
**Tasks 1–8 implemented; awaiting CI, review and the owner's approval.** [[ADR-005 Async Job Queue and Worker Execution Model]] was `Accepted` by the project owner on 2026-08-17, clearing the §7 gate; Tasks 2–8 were implemented on the owner's instruction the same day. The step stays `In Progress` until its Pull Request's required CI is green and its owner gate is satisfied — [[Execution Protocol#Step Completion]] makes those completion conditions, not formalities.
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** full — expanded 2026-08-17 by [[STEP-29 Asset Management UI]], per [[Execution Protocol#The Loop]] item 11, against `main` @ `1a5f1e3`.

> [!success] The ADR gate is cleared
> This step introduces a **queue technology and a second deployed process**. Both are §10 stack-table decisions, so [[CLAUDE|CLAUDE.md]] §7 and §39 required an ADR before any production code was written.
>
> [[ADR-005 Async Job Queue and Worker Execution Model]] reached `Accepted` on 2026-08-17. Everything below was built against it.

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

Everything in [[#Task 1 — ADR-005 — the queue, and the second process]] is a decision this step cannot take alone. They are deliberately gathered into one ADR rather than listed here as D1–D4, because they are a single coupled choice: the queue, the framework, the tenancy mechanism and the deployment shape each constrain the others.

**Resolved 2026-08-17.** All four are answered in [[ADR-005 Async Job Queue and Worker Execution Model]], which the owner moved to `Accepted` on that date. The decisions are now binding on this step: a PostgreSQL queue claimed with `FOR UPDATE SKIP LOCKED`, no task framework, a worker as a second entrypoint of the API application, tenancy carried as the enqueuing user's identity replayed through `authenticated_as`, and a cross-tenant dispatch path bounded to the `jobs` table by six constraints of which three must be proven by test.

Two numbers this step must honour, set at review: **2 job attempts per enqueue**, giving a composed ceiling of **60 upstream provider requests**; and a job whose actor lost workspace membership **fails terminally**, never reaching its handler.

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

- [x] **ADR-005 `Accepted` by the project owner** before implementation began — 2026-08-17.
- [x] The composed retry ceiling stated as a number, with its arithmetic — `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` = **60**, computed from its three factors rather than written down.
- [ ] Required CI green, and the manual checklist complete.
- [ ] Owner approval obtained — this step is Critical.
- [x] Status synchronized between this note and the [[Build Plan]] index.
- [x] [[STEP-31 Workflow Async Execution]] expanded to full detail.

## Outcome

Implemented 2026-08-17 on branch `step-30-async-jobs`. **Every decision below was already settled by [[ADR-005 Async Job Queue and Worker Execution Model]]**; what follows is what the implementation added, found or had to reconcile.

### What was built

| Surface | What exists now |
|---|---|
| Migration `a1b7c3e94f6d` | `public.jobs` — RLS enabled and forced, three policies, a client write guard, the composed ceiling as a CHECK constraint |
| `app/jobs/contract.py` | The contract, the two ceilings, `JobStatus`, `JobHandler`, `JobContext`, and the retry classification |
| `app/jobs/registry.py` | Handler registry; refuses a duplicate type, a blank type, or a ceiling outside `1..2` **at import** |
| `app/jobs/handlers.py` | `TenantProbeHandler` — the trivial handler the step's scope calls for |
| `app/jobs/service.py` | Enqueue, on the tenant connection, refusing an unknown type at the request |
| `app/jobs/worker.py` | The loop, the lease heartbeat, the retry policy, signal handling, and the identity check |
| `app/repositories/jobs.py` | Tenant-scoped enqueue and read |
| `app/repositories/job_dispatch.py` | The bounded cross-tenant path: claim, extend lease, record outcome |
| `infrastructure/` | Created. `README.md` and `process-model.md` — the first thing in the repository to need the directory §9 has always specified |

Documented in [[Async Job Execution]] and [[Table - jobs]].

### Three things found by building it rather than by planning it

**1. A `SECURITY DEFINER` role guard silently never fires.** The client write guard on `jobs` tests `current_user = 'authenticated'`. Written as `SECURITY DEFINER` — copying `app_messages_immutable` — `current_user` is the function's *owner*, so it read `postgres` on every call and refused nothing. It passed a reading and protected nothing; a test caught it against a real database. It is now `SECURITY INVOKER`, and the trap is recorded in [[RLS Policy Pattern#A grant given for erasure is a grant given for everything]] because it will recur on the next table whose only client write is an erasure.

**2. `coalesce` will not unify `json` with `jsonb`.** An INSERT casts on assignment and hides the difference; `coalesce(%s, result)` does not. Fixed with an explicit `::jsonb`. Worth recording only because the failure appears in the one statement that is not an insert.

**3. A rolled-back transaction reverts `SET ROLE`.** In tests, a refused statement followed by `rollback()` left the session as `projectone_api`, which holds no privileges at all — so the *next* assertion failed with "permission denied" and looked like the test under examination breaking. It is the same fail-closed property the request path depends on, surfacing where nobody expects it. `session_as` in `tests/test_job_queue.py` now opens one connection per refused statement.

### Where the ADR needed reconciling, and how

ADR-005 §5 constraint 4 requires the user's RLS context to be established *before execution begins*, stated as an ordering guarantee. ADR-005 §4 separately requires the handler to open **short, discrete** sessions, and rejects holding one transaction across a multi-minute render.

Read literally together, the first suggests a session open at invocation and the second forbids exactly that. The implementation satisfies both: the worker opens an RLS-subject session and **proves** the actor's live membership through the same policies the handler will meet, closes it, and then invokes the handler with a *factory* that opens further short sessions as the same user. Identity is established and verified before the handler's first statement; no transaction is held while the long work runs.

This is recorded here rather than settled quietly because it is the one place the implementation had to choose a reading. **It is reported to the project owner as part of this step's review.** If the intended meaning was a session held open at invocation, that is a change to §4's transaction shape and belongs in a superseding ADR rather than in code.

### Deliberately not built

- **No workflow integration.** The only handler is an infrastructure probe — [[STEP-31 Workflow Async Execution]] writes the first real one.
- **No HTTP surface for jobs.** Nothing routes to `JobService` yet, because nothing yet has a reason to enqueue.
- **No system-originated jobs.** Every job carries an enqueuing user; the service-actor question is deferred to [[STEP-74 Workflow Scheduling and Triggers]] with its own ADR (ADR-005 §4).
- **No hosting decision.** The process model is documented and runnable; which platform runs it is [[STEP-82 Staging Environment and Deployment Pipeline]]'s.
- **No `LISTEN`/`NOTIFY`.** Available later without a superseding ADR; adopting it now would be optimizing without measurement (§17).

### Known gap, stated rather than left implicit

**A worker that is not running logs nothing.** Its in-process sibling is closed — ten consecutive dispatch failures stop the process with a non-zero exit — but external liveness monitoring is [[STEP-81 Observability and Alerting]]'s, and until then a platform where nothing finishes and nothing errors is possible. Recorded in `infrastructure/process-model.md` and in [[Async Job Execution]].

### Validation

| Check | Result |
|---|---|
| `ruff check .` | Passed |
| `ruff format --check .` | Passed |
| `mypy app` (strict) | Passed — 93 source files |
| `pytest` | **1120 passed, 4 skipped** against PostgreSQL 17 |
| New tests | 4 files, 79 tests: contract and ceilings, the queue against a real database, the worker, and the architectural boundary |

The suite grew from 1039 to 1120. The four skips are the opt-in live-R2 integration tests, unchanged.

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
