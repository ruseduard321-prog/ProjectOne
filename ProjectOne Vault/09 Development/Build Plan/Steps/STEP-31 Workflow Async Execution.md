---
title: STEP-31 Workflow Async Execution
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-17
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-31
step_status: Not Started
detail_level: full
phase: "Platform Substrate"
---

# STEP-31 — Workflow Async Execution

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** full — expanded 2026-08-17 by [[STEP-30 Async Job Infrastructure]], per [[Execution Protocol#The Loop]] item 11, against the code that step actually built.

## Objective

Move workflow runs off the request path and onto the worker, without changing what a run means.

## Why This Step Exists Now

[[STEP-22 Minimum Workflow Engine]] built a runner that is deterministic, resumable and versioned but **synchronous**: every step executes inside the HTTP request that started it. A multi-minute render cannot be a workflow under that model, and [[STEP-32 Media Processing Pipeline]] onward are blocked on it.

[[STEP-30 Async Job Infrastructure]] removed the reason it could not change. The queue, the worker, the tenant boundary and the retry ceiling all exist and are proven; what does not exist is a handler that drives a run.

## Dependencies

- [[STEP-30 Async Job Infrastructure]] — the queue, the worker, and the contract this step writes its first real handler against.

## Inherited from STEP-30

Recorded during synchronization, against what was built rather than what was planned. Each of these changes what this step has to do.

- **The infrastructure is complete and proven on a probe.** `app/jobs/` holds the contract, the registry, the handler ABC and the worker; `app/repositories/job_dispatch.py` holds the bounded cross-tenant dispatcher. The only registered handler is `TenantProbeHandler`, an infrastructure probe. **This step's core is one new handler and the route change that enqueues it**, not new infrastructure.
- **A handler receives `JobContext`, and its only database access is `tenant_session()`** — a factory opening RLS-subject sessions as the enqueuing user. `WorkflowRunner` currently takes a `WorkflowRepository` built over a request connection, so the handler must construct the repository per unit of work inside a session rather than holding one. That is a real change to how the runner is *composed*, and it is not a change to its semantics.
- **`WorkflowStep` implementations close over request-scoped services.** `app/workflows/definitions.py` documents that a module-level definition would be a cross-tenant leak. The handler must therefore build its definition inside the job's tenant context, from the job's workspace and actor — this is the sharpest design question in the step, and it is an existing constraint rather than a new one.
- **Handlers declare `max_attempts` explicitly**, bounded to `MAX_JOB_ATTEMPTS` (2). The composed ceiling of 60 upstream provider requests per enqueue already assumes a workflow handler; this step is where that assumption becomes real, and the arithmetic must not change.
- **A job whose actor lost workspace membership fails terminally, before the handler runs.** A run enqueued by a since-removed member is dead-lettered rather than executed. The run row will still say `pending` or `running`, which is a **state this step must reconcile** — see the tasks below.
- **Delivery is at-least-once.** The runner is already safe under it: `next_step_index` counts completed steps, so a second delivery resumes from where the first reached. That is why this handler is nearly free where a handler with an external side effect would not be — and the reasoning belongs in the handler's docstring, not only here.
- **`jobs.result` and `jobs.last_error` are tenant-readable.** A run's failure detail must not be duplicated into them in a form that carries internal detail.

## What expansion found that the outline did not anticipate

**1. There are now two records of one run's state, and they can disagree.** A `workflow_runs` row and a `jobs` row both describe the same work. A job dead-lettered by the tenant-context check leaves a run that never moves; a run failed by the engine leaves a job that succeeded (the handler did its job — the run failed). **This step owes an explicit statement of which is authoritative for each question**, and a reconciliation for the one case where the job fails without the runner being reached.

**2. The API contract change is larger than "202 instead of 200".** `POST .../runs` currently returns the run in its *finished* state, because it has finished. Asynchronously it returns a run in `pending`, and every existing caller — including the STEP-22 tests and any frontend surface — reads the response expecting terminal state. This is the Critical part of the step and needs the response shape decided before the handler is written.

**3. Approval crosses a process boundary and is already designed for it.** `WorkflowRunner.approve` reads persisted state and continues; nothing about it assumes the approving request is the executing process. **What it does assume is that it executes the continuation inline**, so approval must become an enqueue as well, or approving would put a multi-minute render back inside a request — which is the defect this step exists to remove, reintroduced through the one path nobody would check.

**4. `resume` and the queue can race.** A run that is `running` because a worker holds its job could be resumed by a second enqueue. The job lease stops two *workers* colliding; it does not stop a second job being created for the same run. A run-level guard is needed, and `jobs.status` is not it.

## Scope

- Starting a run **enqueues** it rather than executing it inline.
- A workflow job handler that drives the existing `WorkflowRunner` to completion, pause or failure.
- Approval and resume also enqueue, so no continuation runs inside a request.
- A guard preventing two live jobs for one run.
- Run status reporting for a run that has not finished.
- Reconciliation between a dead-lettered job and the run it was for.
- Execution budgets, ceilings and the approval gate behaving exactly as they do synchronously.

## Out of Scope

- No branching, parallelism or scheduling — [[STEP-51 Workflow Branching]], [[STEP-52 Workflow Parallel Execution]], [[STEP-74 Workflow Scheduling and Triggers]].
- No new workflow type, and no change to what the existing definition does.
- No change to `WorkflowRunner`'s execution semantics. It is already resumable; this step drives it.
- **No notification of completion** — [[STEP-34 Notifications Domain]]. A user watching a run finish is a different problem, and this step leaves polling as the answer.
- No new queue capability. If this step wants something the queue does not have, that is a finding to report, not a widening.

## Surfaces Affected

**Backend:** `app/jobs/handlers.py`, `app/jobs/registry.py`, `app/routers/workflows.py`, `app/services/` composition for the handler. **Database:** likely none — the run-level guard should be expressible with existing columns, and a migration here needs justifying. **Frontend:** run status handling for in-flight runs.

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

### 1. Decide the response contract

`POST .../runs` becomes *accepted*, not *finished*. Decide and document the status code, the body, and how a client learns the outcome. **Do this before writing the handler** — it is the part that breaks existing callers, and the handler is easy once it is settled.

### 2. The workflow job handler

- Drives `WorkflowRunner` for one run id, to completion, pause or failure.
- Builds its repository and definition **inside** `context.tenant_session()`, per unit of work, never holding one session across the whole run.
- Declares `max_attempts` explicitly, and states in its docstring why it is duplicate-safe (`next_step_index` counts completed steps).
- Registered in `REGISTERED_HANDLERS`.

### 3. Enqueue on start, approve and resume

All three paths enqueue. **Approval especially** — item 3 above; an approval that continues inline reintroduces the defect this step removes.

### 4. One live job per run

A guard so a second enqueue for a run already queued or running is refused rather than duplicated. State plainly what it keys on and why the job lease is not sufficient.

### 5. Reconcile a dead-lettered job with its run

A job dead-lettered *before* the handler is reached — a revoked actor, an unregistered type — leaves a run nothing will advance. Decide what the run row says, and make it say it.

### 6. Tests

Every proof below, plus:

- The approval path enqueues rather than executing inline, asserted directly.
- A dead-lettered job leaves a run in a state a user can understand.

### 7. Documentation

- Update [[Workflow Execution]] and [[Async Job Execution]] where this changes what they describe.
- Update [[API Endpoints]] and [[API Conventions]] for the contract change.
- Remove the "execution is still synchronous" note from [[Workflow Engine]].
- Update this note's status and the [[Build Plan]] index row together.
- Expand [[STEP-32 Media Processing Pipeline]] to full detail.

## Required Tests and Proofs

- A run started via the API completes **in the worker**, proven by persisted state rather than by the response.
- An interrupted worker leaves a resumable run, and a redelivery resumes rather than restarting.
- An approval granted in one process releases a run executing in another.
- Ceilings still trip, and still fail loudly, across the process boundary.
- Two enqueues for one run do not produce two executions.

## Definition of Done

Workflow runs execute asynchronously with resumability, approvals and ceilings behaving exactly as they did synchronously — proven by the existing STEP-22 suite plus new cross-process assertions.

Additionally, per [[Execution Protocol#Step Completion]]:

- [ ] The API contract change is documented, and every existing caller updated.
- [ ] Required CI green, and the manual checklist complete.
- [ ] Owner approval obtained — this step is Critical.
- [ ] Status synchronized between this note and the [[Build Plan]] index.
- [ ] [[STEP-32 Media Processing Pipeline]] expanded to full detail.

## Risks and Governance Gates

**Critical** — AI/agent architecture and a public API contract change. The response shape moves from *finished* to *accepted*, which every client must handle.

- **Two records of one run's state.** Item 1 above: a job and a run can disagree, and the disagreement is invisible until someone asks why a run never moved.
- **An approval that continues inline.** The one path that would quietly keep a multi-minute execution inside a request.
- **A definition built outside tenant context.** `definitions.py` already warns that a module-level definition is a cross-tenant leak; building one in a worker is where that warning is easiest to forget.
- **The ceiling composing differently than stated.** The 60-request bound assumes one job attempt drives one run execution. A handler that resumed a run in a loop would break the arithmetic without changing a single constant.

## Audit Gaps Closed

**Background / async execution** — *Foundation / Partial, P0*

---

## Navigation

- **Previous:** [[STEP-30 Async Job Infrastructure]]
- **Next:** [[STEP-32 Media Processing Pipeline]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]] · [[Async Job Execution]] · [[Workflow Execution]] · [[ADR-005 Async Job Queue and Worker Execution Model]]
