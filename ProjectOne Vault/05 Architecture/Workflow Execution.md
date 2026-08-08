---
title: Workflow Execution
category: Architecture
status: stable
version: "1.0"
last_updated: 2026-08-08
tags: [architecture, ai, workflow, backend, standards]
aliases: ["Workflow Runner", "Run Execution", "Approval Gate"]
---

# Workflow Execution

**How a workflow run actually executes**, and where each of [[Workflow Engine]]'s five execution principles lives in code. Implemented by `apps/api/app/workflows/` ([[STEP-22 Minimum Workflow Engine]]).

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

### Resuming is not approving

`resume` **refuses** a run in `awaiting_approval` with a 409. Otherwise anyone able to restart a run — including an automated retry — could bypass the human §15 put behind the gate.

### Who may approve

**Owner and admin only** (`UPDATE_WORKSPACE`) — the project owner's decision on 2026-08-08. A gated step spends money or acts externally, which is the same class of consequence already guarding AI provider keys and spend ceilings.

Starting, reading and resuming a run are `VIEW_WORKSPACE`, matching projects: a member who cannot run a workflow on their own project cannot use the product. **No new permission was added** — introducing `workflow:approve` would change the role model, which is a decision about authorization rather than a detail of a build step.

## Failure Is a Run State, Not an HTTP Error

A run whose step fails comes back as **201 with the run in `failed`**. The request succeeded: the run was created, executed, and recorded its outcome.

Reporting it as a 500 would tell the client its call did not happen when it did, and would lose the run id they need to investigate.

What *is* an error status is a request that could never have produced a run:

| Condition | Status |
|---|---|
| Unknown workflow type | **422** |
| Run absent, or hidden by RLS | **404** |
| Run's state refuses the action | **409** |
| A step failed mid-run | **201/200 with `status: failed`** |

### `failed` is resumable; `completed` is not

[[Workflow Engine]]'s Failure Recovery allows a failed run to retry or resume from a checkpoint. A `resume` refusing failed runs would leave every transient provider outage as a run the user must recreate from scratch, losing the steps that already succeeded.

Retrying picks up **at the failed step**, because `next_step_index` counts completed steps and the failed one never recorded completion.

`completed` is refused because there is nothing to continue.

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

## Known Limitations

Stated rather than left to be discovered:

- **Execution is synchronous**, on the request thread. A background queue is infrastructure needing its own ADR ([[CLAUDE|CLAUDE.md]] §10/§28). The run's wall-clock ceiling (300s) bounds how long a request can take meanwhile. **The persistence model is already the one a queue would need**, so moving execution off the request thread later changes where `_execute_from` is called from and nothing else.
- **No branching, scheduling or parallel execution.** Explicitly out of [[STEP-22 Minimum Workflow Engine]]'s scope.
- **No UI.** Runs are reachable over HTTP only.
- **One workflow and one AI agent.** The interface is the deliverable; the agent chain [[Agent Architecture]] describes is later work.
- **A resumed run re-executes an interrupted step.** Step execution is effectively at-least-once. Every current step is safe under that — validation and quality checks are pure reads, and planning produces a new outline rather than mutating anything — but a future step with an external side effect needs idempotency of its own.

---

## Navigation

- **Previous:** [[Project Lifecycle]]
- **Next:** [[AI Cost Governance]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[Workflow Engine]] · [[Agent Architecture]] · [[AI Cost Governance]] · [[Project Lifecycle]] · [[Table - workflow_runs]] · [[API Endpoints]]
