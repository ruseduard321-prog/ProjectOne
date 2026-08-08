---
title: STEP-22 Minimum Workflow Engine
category: Development/Build Step
status: stable
version: "3.0"
last_updated: 2026-08-08
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-22
step_status: Done
detail_level: full
---

# STEP-22 — Minimum Workflow Engine

**Status:** Done
**Detail level:** full — expanded by [[STEP-21 Projects UI]], per [[Execution Protocol]].

## Goal

The minimum viable engine: Trigger → Validation → Planning → Agent Execution → Quality Checks → optional Approval → Completion.

## Scope

Branching, scheduling and parallel execution can wait. Deterministic, observable, resumable, versioned execution and the default-approval-required gate cannot ([[CLAUDE|CLAUDE.md]] §15).

**This is the first step where AI spend can occur without a human watching**, which makes §15a's controls the centre of the step rather than a checklist at the end.

**Out of scope:** conditional branching, scheduled/cron triggers, parallel step execution, a workflow *editor* UI, and any agent that is more than a single AI call behind a defined interface. Chat is [[STEP-23 AI Chat End to End]].

## Prerequisites

- [[STEP-21 Projects UI]] — `Done`, and owner-approved (it carries an approval gate)

## Required Documentation

- [[Workflow Engine]] — the execution model this must implement
- [[Agent Architecture]] — what an agent is, and what it owes its caller
- [[AI Cost Governance]] — the ceilings a run executes inside
- [[Project Lifecycle]] — what a workflow may do to a project's status

**Reference only:** [[Design Backlog and UI Vision]]. It binds nothing.

## Inherited from STEP-21

Recorded during expansion, while the context was loaded. These are the load-bearing facts, not a substitute for reading the notes.

- **`ProjectService` is the only path that changes a project's status**, and a workflow is exactly the non-HTTP caller [[Project Lifecycle#Where the Rules Live]] anticipated. A workflow step that advances a project calls `transition` and handles `IllegalTransitionError` — **it must not write `projects.status` directly**, and `ProjectRepository.update_status` will happily let it if asked.
- **The lifecycle refuses skipping.** A workflow driving Generation → Review moves one step at a time, or it fails. A run that wants to jump is a run whose design disagrees with the state machine, and the state machine wins.
- **`AIService.complete` is the only sanctioned path to a provider** and already enforces budgets, breakers and shutdown. `test_no_ai_call_path_bypasses_governance` asserts nothing else reaches `AIRouter`. A workflow calls the service; it never constructs a router.
- **`ExecutionBudget` already exists** in `app/ai/governance.py` with `max_invocations`, `max_seconds`, `max_tokens`, a `check()` called *before* each invocation, and `record_invocation()`. **One instance per run, never shared** — it is mutable accumulated state, and sharing one would make each run consume its predecessors' allowance. This step's job is to *thread it through the engine*, not to invent it.
- **`workflow_type` is already a parameter** of `AIService.complete` and the key for per-workflow ceilings. A workflow's name must be passed as its `workflow_type` or its spend lands in the wrong bucket.
- **Errors are translated in `app/core/errors.py`, never in a router.** Any new error type this step introduces needs an entry there *before* a route can raise it — STEP-18 recorded what omitting one costs (a correct control reported as a 500), and STEP-21 added two more entries the same way.
- **A new tenant-scoped table ships its RLS policy in the same migration**, and must be added to `_WORKSPACE_DEPENDANTS` in `tests/conftest.py` in the same change. `test_teardown_completeness` fails loudly if it is not. See [[Table Conventions#A `RESTRICT` foreign key to `workspaces` is also a test-teardown obligation]].
- **A SELECT policy must never filter `deleted_at IS NULL`** — it makes soft deletion impossible. This has cost the project two steps ([[STEP-11a Membership Lifecycle Repair]], STEP-19). STEP-20 avoided it at creation time; this step must too.
- **The web app still resolves the caller's first workspace** and has no switcher.
- **Wherever the database constrains a value to a set, the outermost schema enumerates the same set.** A run status vocabulary is exactly this shape. STEP-21 paid for learning it — see [[Table - assets#`kind` is a closed vocabulary, and the API must mirror it exactly]].

## Tasks

1. **Migration** — `workflow_runs` and `workflow_step_runs`. Standard column set, RLS enabled *and* forced, per-command policies following [[RLS Policy Pattern]], `text` + CHECK for both status vocabularies, composite FK from step runs to `(run_id, workspace_id)` as `assets` does. Register both in `_WORKSPACE_DEPENDANTS`.
2. **Versioning** — a workflow definition carries a version, and a run records **which version it executed**. A run whose definition has since changed must still be readable as what actually ran ([[CLAUDE|CLAUDE.md]] §7 — versioned).
3. **The engine** — `app/workflows/`: a step interface, a runner that executes steps in order, persists state after **each** step, and can resume a run from its last completed step. Resumability is a Definition of Done item, not an optimization.
4. **Agent interface** — a single-responsibility agent with defined inputs/outputs and a measurable success criterion ([[CLAUDE|CLAUDE.md]] §15). One real agent is enough; the interface is the deliverable.
5. **Governance wiring** — one `ExecutionBudget` per run, `check()` before each step, `record_invocation()` after each AI call, and `workflow_type` set to the workflow's name. A tripped ceiling fails the run **loudly** and records why.
6. **The approval gate** — any step that writes data, spends money, publishes, or acts externally **requires approval by default**. Autonomous execution is opt-in and documented, never a silent default (§15). A run pauses at the gate and is resumable from it.
7. **Observability** — every run and every step is logged with its correlation id, its decision, and its outcome. A run must be reconstructable from logs without reproducing it (§26).
8. **Endpoints** — start a run, read a run and its steps, approve a paused run. `requires(...)` on each; approval is the one plausibly needing more than `VIEW_WORKSPACE`, and that is a decision to state rather than assume.
9. **Tests** — resumability proven by interrupting a run and resuming it; the approval gate proven to *block*; ceilings proven to trip; isolation proven through the route layer.

## Validation

- **A run resumes from its last completed step**, asserted by interrupting one mid-run and resuming it — not by reading the code.
- **A gated step does not execute without approval**, and the run is genuinely paused rather than merely reporting so.
- **A run that exceeds its execution ceiling fails loudly** and records which ceiling tripped.
- **No AI call in the engine bypasses `AIService`**, asserted the way `test_no_ai_call_path_bypasses_governance` already does.
- **A run cannot be read or started across the tenant boundary**, proven against real response bodies.
- **A workflow advancing a project uses `ProjectService.transition`**, and an illegal advance fails rather than writing the status.
- Lint, type-check, tests and build pass for both apps in CI.

## Definition of Done

A workflow runs end to end through its seven phases, persists state after every step, resumes correctly after interruption, refuses to execute a gated step without approval, fails loudly on a ceiling, and is fully observable in logs — with isolation proven through the route layer.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — AI/agent architecture, database schema, multi-tenancy, public API contract) and carries an **owner approval gate**.

---

## Outcome

Two tables, six routes, one engine, one real agent and 79 new tests. A workflow runs end to end through its seven phases, persists after every step, resumes correctly, refuses to execute a gated step without approval, and fails loudly on a ceiling.

### What was built

**Engine** — `app/workflows/`: `models.py` (vocabularies, the step contract, definitions), `agents.py` (three steps including the planning agent), `definitions.py` (the registry), `runner.py` (execution, persistence, the gate).

**Persistence** — migration `f3c82b19d4a7` creating `workflow_runs` and `workflow_step_runs`, plus `WorkflowRepository` and two registered erasure stores.

**HTTP** — `app/routers/workflows.py`, `app/schemas/workflow.py`, three new error handlers, and dependency wiring.

### Architecture decisions

**The seven phases are not seven classes.** Trigger and Completion are the runner's own boundaries; the rest are `WorkflowStep` implementations. A runner with the phases baked in could not satisfy [[Agent Architecture]]'s requirement that agents be addable without touching existing workflows.

**`requires_approval` defaults to `True`.** A step author who does not consider the question gets the safe behaviour. Overriding it to `False` is an assertion that the step is read-only or trivially reversible, and owes the reasoning in its docstring — the documented exemption [[CLAUDE|CLAUDE.md]] §15 requires. The planning agent *inherits* the default rather than overriding it, which is itself the decision: it spends money.

**Approval is `UPDATE_WORKSPACE`** — the project owner's decision on 2026-08-08. A gated step spends money or acts externally, the same class of consequence guarding AI keys and budgets. **No new permission was added**; `workflow:approve` would change the role model, which is an authorization decision rather than a detail of a build step.

**One approval covers one step**, and **resuming is not approving** (409). Anything else would be autonomous execution, which §15 requires to be a configured opt-in rather than a side effect of clicking approve.

**A failed run is a 201, not a 500.** The request succeeded — the run was created, executed and recorded its outcome. Now generalized in [[API Conventions]]: an error status describes the *request*; a resource's state describes the outcome.

**An action gate is not an RLS policy.** Approval is enforced at the route, not by a role-scoped policy, because a policy would make a member's approval match zero rows and return success — the silent no-op an honest 403 exists to replace. Recorded in [[RLS Policy Pattern]].

### Defects found and fixed

**Three, and the tests found all three before any of this was committed.**

**1. `resume` refused a failed run.** The most common thing a user resumes is a run that failed on a transient condition, and refusing it would force them to recreate the run from scratch, losing every completed step. [[Workflow Engine]]'s own Failure Recovery says otherwise. Now `completed` is refused and `failed` is resumable, picking up at the failed step.

**2. A shortened definition reported a truncated run as `completed`.** With `start_index == len(steps)` the execution loop is empty, so a run whose definition lost steps while it was paused fell straight through to the completion path — **claiming work that never happened**. Guarded explicitly, scoped to resumption so a fresh run is unaffected.

**3. Step outputs were not persisted, which made resumption incorrect.** The load-bearing one, and it was found by running the real workflow rather than by reasoning about it.

The first implementation held outputs in memory and *documented that as a harmless limitation*, on the reasoning that a resumed run re-executes its earlier steps. **It does not** — a completed step is never re-run. So the planning agent resumed after approval, could not see the validation step's result, and failed the run.

Every engine unit test passed, because their steps ignore their inputs. Fixed by adding `workflow_step_runs.output` (`jsonb`) and rebuilding the context from completed steps. `test_an_earlier_steps_output_survives_a_resume` was **verified to fail when the fix is reverted**.

**A fourth, found in the same probe run:** a cross-tenant `project_id` was refused by the composite foreign key — correctly — but surfaced as an **unhandled 500**. Now translated to `ProjectNotFoundError`, giving the same 404 as any other unreachable project. The refusal itself is stronger than the test originally expected: **no run row is created at all**, rather than one in a failed state.

### Validation

- **60/60 checks against the live development database**, driving the real routes in-process through `TestClient`. Every seeded row removed afterwards and verified to zero across six tables.
- The Definition of Done items specifically: a run resumes from its last completed step; a gated step **does not execute** and the provider is **never called** before approval; a tripped ceiling fails the run loudly with the reason on the row; no AI call bypasses `AIService` (proven against the spend ledger); a run cannot be read or started across the tenant boundary.
- Migration applied, **downgraded and re-applied** to verify the rollback path — twice, since the `output` column was added after the first probe.
- API: ruff, ruff format, `mypy app` (68 files), 393 passed locally.
- Web: unchanged and re-verified — typecheck, lint, 113 tests.

**The 29 database-backed API tests skip locally** (STEP-19's unfixed pooler mismatch, no local PostgreSQL), which is exactly why the probe exists — and in this step it earned its keep, finding two defects the offline suite structurally could not.

### Limitations, stated rather than discovered

- **Execution is synchronous**, on the request thread, bounded by the run's 300s wall-clock ceiling. A queue needs an ADR — but **the persistence model is already the one a queue would need**, so moving execution later changes where `_execute_from` is called from and nothing else.
- **No branching, scheduling or parallel execution** — explicitly out of scope.
- **No UI.** Runs are reachable over HTTP only.
- **One workflow, one AI agent.** The interface is the deliverable.
- **A resumed run re-executes an interrupted step**, so step execution is at-least-once. Every current step is safe under that; a future step with an external side effect needs its own idempotency.

---

## Navigation

- **Previous:** [[STEP-21 Projects UI]]
- **Next:** [[STEP-23 AI Chat End to End]]
- **Parent:** [[Build Plan]]
