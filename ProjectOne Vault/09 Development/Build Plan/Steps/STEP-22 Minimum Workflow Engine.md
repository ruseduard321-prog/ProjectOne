---
title: STEP-22 Minimum Workflow Engine
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-08
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-22
step_status: Not Started
detail_level: full
---

# STEP-22 — Minimum Workflow Engine

**Status:** Not Started
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

## Navigation

- **Previous:** [[STEP-21 Projects UI]]
- **Next:** [[STEP-23 AI Chat End to End]]
- **Parent:** [[Build Plan]]
