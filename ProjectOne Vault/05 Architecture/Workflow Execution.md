---
title: Workflow Execution
category: Architecture
status: stable
version: "2.0"
last_updated: 2026-08-20
tags: [architecture, ai, workflow, backend, standards]
aliases: ["Workflow Runner", "Run Execution", "Approval Gate"]
---

# Workflow Execution

**How a workflow run actually executes**, and where each of [[Workflow Engine]]'s five execution principles lives in code. Implemented by `apps/api/app/workflows/` ([[STEP-22 Minimum Workflow Engine]]), moved onto the worker by [[STEP-31 Workflow Async Execution]] under [[ADR-006 Workflow Async Execution and Run Reconciliation]].

> [!important] A run executes in a worker, not in the request that asked for it
> Starting a run, approving a step and continuing a stopped run all **enqueue** and answer `202 Accepted`. What executes is a job, and the run row is the status monitor a client polls. The engine's *semantics* did not change; where they run, and what fences them, did.

[[Workflow Engine]] gives the lifecycle and the principles; it does not say how they are achieved. This note records the mechanisms, because each one is a decision that a later step could accidentally undo.

## The Five Principles, and What Provides Each

| Principle | Mechanism |
|---|---|
| **Deterministic** | Steps run in definition order, one at a time. No branching, scheduling or parallelism. |
| **Observable** | Every run and step is logged with the correlation id; every outcome is a persisted row. |
| **Resumable** | State is written after *each* step; `next_step_index` reads it back from the database. |
| **Versioned** | The definition's version is stamped on the run at creation and never re-read. |
| **Independently executable** | A run is identified by its id alone — resuming needs no in-memory context. |

## The Seven Phases Are Not Seven Classes

[[Workflow Engine]] gives: Trigger → Validation → Planning → Agent Execution → Quality Checks → User Approval → Completion.

**Trigger and Completion are the runner's own boundaries** — a run starting and finishing — rather than steps a definition lists. The phases in between are `WorkflowStep` implementations, which is what makes a definition a *sequence* rather than a hardcoded pipeline.

That distinction is load-bearing: [[Agent Architecture]] requires that "new agents can be added, replaced or upgraded without affecting existing workflows", and a runner with the phases baked into it could not do that.

## Persistence Is the Resumability Mechanism

The runner writes each step's outcome **before starting the next one**. The last committed row is therefore always an honest answer to *"where did this run get to"* — including when the answer is "it crashed during step 3".

The cost is one round trip per step. That is the correct trade: an engine batching its writes would lose exactly the runs worth investigating.

### A step's outcome and the run transition it causes are one transaction

**Writing them separately leaves a gap, and a job's lease can rotate inside it.** Three things follow, and two of them cost money:

- the final step commits `completed` while its run is still `running`, so a replacement seeing every step complete can reconcile that run to `failed`;
- a failed non-replayable step commits with its **claim cleared**, and a replacement arriving before the run turns `failed` can admit and re-execute a step that has already been paid for;
- any observer — a poll, the UI, a support query — can read a step and a run that contradict each other.

So the pair is written in one transaction. `app_settle_workflow_step` locks the run, the step and the job, and PostgreSQL holds those locks until the *transaction* ends rather than until the function returns, so both writes happen with every relevant row still locked. If the run transition cannot be written, the step settlement rolls back with it.

Three outcomes are pairs — gated pause, ordinary failure, and the final successful step. An **intermediate** successful step moves no run state and writes none: the run is `running` and stays there.

There is deliberately **no in-memory registry of running workflows**. A process holding run state loses every in-flight run when it restarts, and "resumable" would then mean "resumable as long as nothing goes wrong".

### Step outputs are persisted, and this is not optional

`workflow_step_runs.output` (`jsonb`) stores what each step returned, and `_rebuild_outputs` reads it back when a run resumes.

> [!warning] This was a real defect, found by running the workflow rather than reasoning about it
> The first implementation held outputs in memory and documented that as a harmless limitation, on the reasoning that a resumed run would re-execute its earlier steps. **It does not** — a completed step is not re-run, because `next_step_index` counts completed steps.
>
> The consequence: the planning agent resumed after approval, could not see the validation step's result, and failed the run. The engine's own unit tests all passed, because their steps ignore their inputs.
>
> **A resumable engine whose steps cannot see earlier outputs is resumable only for workflows whose steps do not communicate** — which is not the engine [[Agent Architecture]] describes. `test_an_earlier_steps_output_survives_a_resume` guards it permanently, and was verified to fail when the fix is reverted.

Only **completed** steps contribute outputs. A step that failed or is awaiting approval produced nothing, and including a partial result would hand a later step an output its predecessor never returned.

## The Approval Gate

**Any step that writes data, spends money, publishes, or acts externally requires approval by default** ([[CLAUDE|CLAUDE.md]] §15). `WorkflowStep.requires_approval` therefore **defaults to `True`**, so a step author who does not consider the question gets the safe behaviour.

A step overriding it to `False` is asserting the step is read-only, internal, or trivially reversible — and owes that reasoning in its docstring, which is the documented exemption §15 requires.

### The gate stops the run; it does not skip the step

Reaching a gated step without approval marks **both** the run and the step `awaiting_approval` and returns. Nothing executes. Two alternatives were rejected:

- Letting the run continue and merely flagging the step would be a gate in name only.
- Marking the step `skipped` would silently drop the work the user was asked to approve.

### One approval covers one step

Approving clears the gate for **the step the run is currently waiting on**. The run continues until it finishes or reaches the *next* gated step, where it stops again.

There is no "approve everything from here", deliberately: that is autonomous execution, which §15 requires to be an explicitly configured, documented opt-in rather than a side effect of clicking approve once.

### The grant is durable, single-use, and spent at admission

Synchronously the approving request *was* the executing request, so `approved=True` could be an in-memory parameter. Asynchronously the decision has to reach a different process, so it is **persisted**: `workflow_step_runs.approved_by`, non-null meaning *granted and unspent*, written only by `app_approve_workflow_step` and pinned to `auth.uid()`.

- **The grant and the job are inseparable.** The command writes the grant and enqueues the job that will spend it in one transaction. A grant without its job would be a live entitlement some later, differently authorized path could spend.
- **Admission consumes it**, not the claim — so a step that is gated *and* replayable still spends its grant exactly once.
- **An interrupted gated step has therefore already spent its approval**, and no later delivery can execute it without a fresh one. **Approval is never inferred**, because the persisted model contains nothing to infer it from.

### Resuming is not approving

`resume` **refuses** a run in `awaiting_approval` with a 409. Otherwise anyone able to restart a run — including an automatic redelivery — could bypass the human §15 put behind the gate.

### Who may approve

**Owner and admin only** (`UPDATE_WORKSPACE`) — the project owner's decision on 2026-08-08. A gated step spends money or acts externally, which is the same class of consequence already guarding AI provider keys and spend ceilings.

Starting, reading and resuming a run are `VIEW_WORKSPACE`, matching projects: a member who cannot run a workflow on their own project cannot use the product. **No new permission was added** — introducing `workflow:approve` would change the role model, which is a decision about authorization rather than a detail of a build step.

## Failure Is a Run State, Not an HTTP Error

A run whose step fails is **not** an error response. The request succeeded: the run was accepted, queued, executed by a worker, and its outcome recorded.

Reporting it as a 500 would tell the client its call did not happen when it did, and would lose the run id they need to investigate.

What *is* an error status is a request that could never have produced a run:

| Condition | Status |
|---|---|
| Start, approve or continue accepted | **202**, with `Location` naming `GET .../runs/{run_id}` |
| Unknown workflow type | **422** |
| Run absent, or hidden by RLS | **404** |
| Run's state refuses the action | **409** |
| A step failed mid-run | **`status: failed` on the run**, read by polling |

**No job identifier is exposed.** Doing so would make the queue a public contract and turn [[ADR-005 Async Job Queue and Worker Execution Model]] §1's broker-migration escape hatch into a breaking client change. `workflow_runs` is authoritative for everything a user sees; `jobs` is operational delivery state and no client surface joins the two.

### `failed` is recoverable; `completed` is not

[[Workflow Engine]]'s Failure Recovery allows a failed run to retry or resume from a checkpoint. A `resume` refusing failed runs would leave every transient provider outage as a run the user must recreate from scratch, losing the steps that already succeeded.

Recovery picks up **at the interrupted step**, because `next_step_index` counts completed steps and that step never recorded completion.

`completed` is refused because there is nothing to continue, and so is every other non-`failed` state: under the async model a live run always has a live job, so there is nothing for a second caller to restart.

### A definition that loses steps fails loudly

A run recording more completed steps than the definition now has cannot continue coherently — and the execution loop cannot detect this on its own, because `range(n, n)` is empty and would fall straight through to the completion path, **reporting a truncated run as `completed`**.

Guarded explicitly. Reachable whenever a definition is edited without a version bump while a run is paused.

## Governance

Every AI call a workflow makes goes through `AIService.complete`, which is the single choke point enforcing [[CLAUDE|CLAUDE.md]] §15a. A step holding an `AIRouter` would be a path that spends money without passing a single control.

### One `ExecutionBudget` per execution, shared by every step

Passed to every step through `StepContext` and handed to every AI call. **A budget per step would reset the tally each time**, and a ten-step workflow would silently get ten times the allowance — the runaway §15a's chained-invocation cap exists to prevent.

A **resumed** run gets a fresh budget, deliberately: the ceiling bounds one *execution*, not the run's whole lifetime. A run paused overnight for approval must not fail on wall-clock time that elapsed while a human was deciding.

### Nothing is retried by the runner

`AIRouter` owns retries for AI calls. A runner retrying on top of that would multiply a ceiling nobody wrote down.

### Spend is attributed to the workflow

A run's AI calls carry `workflow_type` matching the workflow's own name, which is what per-workflow ceilings meter on. A mismatch would make "set a limit on project planning" silently govern nothing.

## Definitions Are Code, Not Data

There is **no `workflows` table**. A definition's steps are executable Python, and a definitions table would be a second source of truth able to disagree with the code that actually runs — a disagreement that would only surface mid-run.

Definitions are built **per request** rather than held as module constants, because a definition holds steps and steps hold request-scoped services (a repository over the tenant connection, an `AIService` wired to that request's settings). A module-level definition would hold whichever tenant's connection built it first.

What *is* stored is which definition and which version a run executed.

### Versioning

Bump a definition's version when the **step sequence** changes — adding, removing or reordering steps — so a stored run keeps describing what actually happened.

Editing a step's internals without changing the sequence does not require a bump: the run executed that step, and the row says so.

**The stored version is enforced, not recorded.** Before a run is executed, recovered or approved, the definition this deployment would use must match the run's `workflow_type` and `definition_version`. Synchronously this could not diverge — the definition that started a run necessarily finished it inside one request. Asynchronously a run can sit at a gate, or interrupted awaiting recovery, across a deploy.

Continuing such a run is not a degraded version of correct behaviour but a different execution: `next_step_index` counts completed rows, so an inserted step shifts every index after it, and a step that stopped being `replayable` would be re-entered without a claim.

So it **fails closed**, with a fixed message that names no version. Approval is checked as well as execution and recovery, because an approval that enqueues work the worker will refuse spends the grant and dead-letters the job.

On every path the guarantee is the same and it is the expensive part: **no provider call, no step admitted, no approval or claim consumed**, and the run's steps, outputs and history stay readable.

**The run's status is where the paths differ, and it is worth being exact.** Approval and recovery refuse in the route, before any command runs, so the run keeps the state it had. A worker is already holding a job: its refusal is terminal, the job dead-letters, and [[Async Job Execution]]'s reconciliation moves the linked run to `failed`. That is the reconciliation rule working as specified rather than an oversight — a dead-lettered job against a live run is the stranded pair it exists to prevent — so no exception is carved out for this case.

What happens to an incompatible run afterwards — migrate it, restart it, abandon it — is a product decision somebody takes on purpose.

## Duplicate Delivery, and the Four Problems Behind One Symptom

Delivery is at-least-once ([[ADR-005 Async Job Queue and Worker Execution Model]] §6): a job's lease can lapse under a worker that is still running it. Four different problems wear the symptom "a run executed twice", and each has a different answer.

| Problem | Mechanism | Guarantee |
|---|---|---|
| **Duplicate enqueue** — two requests create two jobs for one run | partial unique index on `jobs.workflow_run_id`, plus the INSERT policy and the type/link CHECK | no two live jobs for one run |
| **Replayable-step redelivery** — a pure step runs twice | none needed; the step declares `replayable = True` | duplicate execution has no external effect |
| **Non-replayable redelivery** — two executions in one paid step | a durable step claim plus three-predicate fenced settlement | at most one execution can *persist* the step |
| **Provider completed before persistence** — the worker died after the call was billed | **nothing closes this** | no automatic re-invocation; a deliberate recovery may repeat the call |

**`next_step_index` alone is not an answer to any of the last three.** It makes a *sequential* redelivery resume rather than restart, and says nothing about two deliveries alive at once.

### `replayable` defaults to `False`

The identical defaulting decision `requires_approval` makes, for the identical reason: a step author who never considered whether re-running their step costs money ships the guarded behaviour.

| Step | `replayable` | Why |
|---|---|---|
| `ValidateProjectStep` | `True` | reads one project row and returns; no external effect for a claim to protect |
| `QualityCheckStep` | `True` | deterministic over values already in memory |
| `PlanningAgent` | `False` (inherited) | reaches a paid provider |

### The claim, and the three predicates behind a write

A non-replayable step is entered by winning a **durable claim** exactly one execution can hold — written by `app_admit_workflow_step`, which commits *before* the provider is called, so the long work runs with no row locked underneath it.

Persisting a result then requires all three of:

1. the step's `claim_token` is the caller's;
2. the caller's job is still `running` on the lease that took the claim;
3. the run is not already terminally reconciled.

All three are evaluated with the run, the step and the job already locked. **A settlement that fails writes nothing at all** — it does not retry, does not fail the run and does not touch the step row, because the claim is the record of what was in flight and erasing it would re-open the double call.

### No expiry, no stealing, no automatic recovery

A claim held by a dead process is never released by elapsed time, by a replacement worker, or by reconciliation. `c8f1a3d54e29` states the reasoning for chat turns and it transfers unchanged: **stuck is honest; silently double-charging is not.**

A replacement worker that finds a claim held is **terminally interrupted** — its job dead-letters and the run is reconciled to `failed` in the same statement. It must never report success: it cannot prove the holder is alive, and a false success would leave a succeeded job, a `running` run and nothing able to advance it.

### Recovery is an explicit user action

`POST .../runs/{run_id}/resume` on a `failed` run supersedes the stale claim and completes one of two transitions, never neither:

- **the interrupted step is not gated** → it becomes claimable again, the run returns to `pending`, and a replacement job is enqueued;
- **the interrupted step is gated** → the gate is re-armed with no job, and continuing needs a fresh approval from an owner or admin.

The supersession is written to `audit_log` — run, step, actor, replacement job, and the *fact* of supersession, never the token value. A recovery that may cause a second provider charge is exactly the sensitive action [[CLAUDE|CLAUDE.md]] §16 requires auditing.

**There is no exactly-once provider execution, and nothing here claims one.** A provider that accepted and billed a request before its worker died has already been paid, and nothing records it. That window closes only with provider-side idempotency keys, which ADR-005 §Scope Boundaries leaves open.

## Known Limitations

Stated rather than left to be discovered:

- **No branching, scheduling or parallel execution.** Explicitly out of [[STEP-22 Minimum Workflow Engine]]'s scope.
- **No completion notification.** A client learns the outcome by polling `GET .../runs/{run_id}`; [[STEP-34 Notifications Domain]] is where that changes.
- **No UI for approving or continuing a run.** Runs are reachable over HTTP only.
- **One workflow and one AI agent.** The interface is the deliverable; the agent chain [[Agent Architecture]] describes is later work.
- **Not every interrupted run resumes automatically**, and that is a deliberate narrowing rather than a shortfall. Automatic redelivery resumes replayable work; an interrupted claimed non-replayable step fails safely and waits for a person. A platform that silently re-spends a user's money to avoid showing them a failure has made the user's decision for them ([[CLAUDE|CLAUDE.md]] §40).
- **The privileged spend connection is held across a provider call, deliberately.** `AISpendService.guard` keeps one connection for a guarded call rather than opening eight, and holds it *idle* rather than mid-transaction. A **step** holds nothing: it reads through readers that open and close a session per call, so no `projectone_api` backend exists while a provider is being called. The remaining hold is a decision about the AI service as a whole rather than about workflows, and it is measured rather than assumed — see [[Async Job Execution#What a running step occupies]].

---

## Navigation

- **Previous:** [[Project Lifecycle]]
- **Next:** [[Async Job Execution]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[Workflow Engine]] · [[Agent Architecture]] · [[AI Cost Governance]] · [[Async Job Execution]] · [[Project Lifecycle]] · [[Table - workflow_runs]] · [[Table - jobs]] · [[API Endpoints]] · [[ADR-006 Workflow Async Execution and Run Reconciliation]]
