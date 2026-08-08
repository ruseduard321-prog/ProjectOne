---
title: Table - workflow_runs
category: Architecture/Schema
status: stable
version: "1.0"
last_updated: 2026-08-08
tags: [database, schema, multi-tenancy, workflow, ai]
aliases: ["workflow_runs", "workflow_step_runs", "Workflow Run Tables"]
---

# Table - workflow_runs

**A workflow run and its step history.** Created by [[STEP-22 Minimum Workflow Engine]] in migration `f3c82b19d4a7`, covering two tables that only make sense together.

These are the first tables recording **what the platform did on a user's behalf**, rather than what a user made. Everything before was either platform machinery or user-created content.

## `workflow_runs`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | Primary key |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | Maintained by `touch_row()` |
| `deleted_at` | `timestamptz` | Soft deletion |
| `version` | `integer` | Maintained by `touch_row()` |
| `workspace_id` | `uuid` NOT NULL | FK → `workspaces(id)` `ON DELETE RESTRICT` |
| `workflow_type` | `text` NOT NULL | Which definition ran. Not an FK — see below |
| `definition_version` | `integer` NOT NULL | The version that **actually executed** |
| `status` | `text` NOT NULL | CHECK: `pending`, `running`, `awaiting_approval`, `completed`, `failed` |
| `project_id` | `uuid` | Nullable; part of the composite FK below |
| `detail` | `text` | Why it failed, or which step it awaits |
| `triggered_by` | `uuid` NOT NULL | **Not** an FK |
| `started_at` | `timestamptz` | |
| `finished_at` | `timestamptz` | |

## `workflow_step_runs`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | Primary key |
| `created_at` / `updated_at` / `deleted_at` / `version` | | Standard column set |
| `workspace_id` | `uuid` NOT NULL | FK → `workspaces(id)` `ON DELETE RESTRICT` |
| `run_id` | `uuid` NOT NULL | Part of the composite FK below |
| `step_index` | `integer` NOT NULL | Zero-based position in the definition |
| `step_name` | `text` NOT NULL | Denormalized, so history survives a rename |
| `status` | `text` NOT NULL | CHECK: `pending`, `running`, `awaiting_approval`, `completed`, `failed`, `skipped` |
| `detail` | `text` | |
| `output` | `jsonb` | **What the step produced** — see below |
| `tokens_used` | `integer` NOT NULL | Defaults to 0 |
| `started_at` / `finished_at` | `timestamptz` | |

Both follow [[Table Conventions]] in full.

## `output` is what makes resumption correct

`workflow_step_runs.output` stores each step's result so a later step can read it after a resume.

> [!warning] Not a convenience — a correctness requirement, and it was learned the hard way
> A run that pauses for approval resumes in a **different request**. Outputs held only in memory are gone by then, and a later step reading them finds nothing.
>
> The first implementation did exactly that and documented it as harmless, reasoning that a resumed run would re-execute its earlier steps. It does not: a completed step is never re-run. The planning agent resumed after approval, could not see the validation step's result, and failed the run.
>
> Found by running the real workflow against a real database. Every unit test passed, because their steps ignore their inputs. See [[Workflow Execution#Step outputs are persisted, and this is not optional]].

`jsonb` rather than `text`: a step's output is structured, and storing JSON as text means every reader parses it — and one of them eventually parses it differently.

## `definition_version` is stored, not looked up

A run records the version of the definition it executed. Reading the *current* version at display time would report a run that executed version 1 as having executed version 2 the moment the definition changes — rewriting history to match the present, which is what [[CLAUDE|CLAUDE.md]] §7's versioning requirement exists to prevent.

## `workflow_type` is not a foreign key

There is no `workflows` table. Definitions are declared in code (`app/workflows/definitions.py`) because a workflow's steps are executable Python; a definitions table would be a second source of truth able to disagree with the code that actually runs.

## The step index is unique per run

`uq_workflow_step_runs_run_id_step_index` makes it impossible for one run to hold two rows for the same step.

Without it, a resumed run that re-executed a step would insert a second row, the run's history would show that step twice with no indication which one counted, and the "resume from the last completed step" query would have to guess. The engine's `record_step` is an upsert on this constraint for exactly that reason.

## Composite foreign keys, twice

Both tables use the pattern [[Table - assets]] established, and for the same reason: a denormalized id is otherwise a client-supplied claim RLS cannot check.

- **`workflow_runs (project_id, workspace_id)` → `projects (id, workspace_id)`** — a run cannot name another tenant's project. Proven: a cross-tenant `project_id` is refused by the database, so **no run row is created at all**, which is stronger than creating one in a failed state.
- **`workflow_step_runs (run_id, workspace_id)` → `workflow_runs (id, workspace_id)`** — a step cannot attach to another tenant's run.

> [!important] The refusal must be translated, or it is a 500
> The first `create_run` let `ForeignKeyViolation` propagate, and a cross-tenant request surfaced as an **unhandled 500**. It now raises `ProjectNotFoundError`, producing the same 404 every other unreachable project gives — so a run request cannot distinguish "another tenant's project" from "no such project".
>
> Caught rather than pre-checked with a SELECT: the constraint is the actual guarantee, and check-then-insert would also be a race.

## Neither SELECT policy filters `deleted_at`

Both tables are soft-deleted by workspace erasure, so a SELECT policy filtering `deleted_at IS NULL` would make that erasure impossible — the defect that cost [[STEP-11a Membership Removal Policy]] and [[STEP-19 Settings and BYOK UI]] a step each.

Held at creation time here, as it was for `projects` and `assets`. `test_an_erased_run_disappears_from_the_listing` asserts the soft delete end to end, so a future migration reintroducing the filter fails immediately.

## Both are registered for export and erasure

`WorkflowRunStore` and `WorkflowStepRunStore` are in `REGISTERED_STORES` in the same change that created the tables ([[CLAUDE|CLAUDE.md]] §16).

A run records what the platform did on a user's behalf — arguably more sensitive than the project it acted on, since it says what they automated and when. An erasure leaving runs behind would leave a behavioural record of a workspace that asked to be forgotten.

Worth contrasting with `audit_log`, which is deliberately **un**-erasable: an audit entry records a security-relevant action and exists precisely to outlive the events it describes (a documented legal exception). A workflow run is ordinary product usage and carries no such exception.

## Teardown ordering

Both are registered in `_WORKSPACE_DEPENDANTS`, and **STEP-22 is where that list stopped being alphabetical**. `workflow_runs` references `projects`, so it must be deleted first — but sorts after it. `workflow_step_runs` references `workflow_runs` for the same reason.

[[STEP-20 Projects Schema and Lifecycle]] recorded that `assets` before `projects` was satisfied by alphabetical order as *luck rather than design*. This is where that luck ran out. See [[Table Conventions#A `RESTRICT` foreign key to `workspaces` is also a test-teardown obligation]].

---

## Navigation

- **Previous:** [[Table - assets]]
- **Next:** —
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Workflow Execution]] · [[Table - projects]] · [[Table - assets]] · [[RLS Policy Pattern]] · [[Table Conventions]] · [[Schema Overview]]
