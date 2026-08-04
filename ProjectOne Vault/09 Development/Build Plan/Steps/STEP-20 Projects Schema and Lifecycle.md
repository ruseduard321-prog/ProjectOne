---
title: STEP-20 Projects Schema and Lifecycle
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-04
tags: [engineering, workflow, build-step, database,backend]
step_id: STEP-20
step_status: Not Started
detail_level: full
---

# STEP-20 — Projects Schema and Lifecycle

**Status:** Not Started
**Detail level:** full — expanded by [[STEP-19 Settings and BYOK UI]], per [[Execution Protocol]].

## Goal

`projects` and `assets` tables with RLS in the same migration, plus lifecycle states and transitions.

## Scope

Lifecycle states and transitions only — Generation, Publishing and Analytics stages are later phases. Projects are versioned per [[Projects]].

## Prerequisites

- [[STEP-19 Settings and BYOK UI]] — `Done`

## Required Documentation

- [[Projects]] — the product specification, and the source of the lifecycle states
- [[Table Conventions]] — the standard column set and the teardown obligation
- [[RLS Policy Pattern]] — **read the `deleted_at` rule before writing a SELECT policy**
- [[Database Architecture]]
- [[CLAUDE|CLAUDE.md]] §13/§16

**Reference only, not required reading:** [[Design Backlog and UI Vision]]. It binds nothing and must not change what this step builds.

## Inherited from STEP-19

Recorded during expansion, while the context was loaded. These are the load-bearing facts, not a substitute for reading the notes.

- **A SELECT policy must not filter `deleted_at IS NULL`.** It makes soft-deleting the table impossible — the `UPDATE` setting `deleted_at` produces a row the policy no longer matches, and PostgreSQL refuses it with a row-level-security error naming the wrong policy. This has now cost two steps ([[STEP-11a Membership Removal Policy]], [[STEP-19 Settings and BYOK UI]]). Liveness goes in the queries. `projects` and `assets` are soft-deleted, so this applies directly.
- **Every query must then state `deleted_at IS NULL` itself**, including the export and erase methods of any `REGISTERED_STORES` entry.
- **A new table taking an FK to `workspaces` must be added to `_WORKSPACE_DEPENDANTS` in `tests/conftest.py`** in the same change. `test_teardown_covers_workspace_dependants` asserts the list against the live FK graph in both directions, so an omission fails by name rather than as a confusing violation elsewhere.
- **A new store holding user data must be registered in `REGISTERED_STORES`** for export and erasure, or a workspace erasure silently leaves it behind — the [[CLAUDE|CLAUDE.md]] §16 defect STEP-18 found on `provider_credentials` and STEP-19 found again on its erase path.
- **A column-level grant is the tool for "this column is not client-writable."** RLS is per-row and cannot express it. Any counter or state column that application code maintains (a version, a computed status) should be considered for one, as `ai_budgets.spent_usd` now is.
- **The web application resolves the caller's *first* workspace** (`lib/workspace.ts`) and has no switcher. A projects list is workspace-scoped, so this step inherits that constraint — a switcher is a plan change to surface, not something to build inside this step.
- **`requires(...)` gates a route declaratively**; authorization that must hold for a non-HTTP caller goes in the service instead. Both patterns are in `app/routers/workspaces.py` with the reasoning stated.

## Tasks

1. **Migration** — `projects` and `assets`, both with the standard column set from [[Table Conventions]], `workspace_id` FK `ON DELETE RESTRICT`, RLS **enabled and forced** in the same migration, per-command policies routing through `app_current_user_workspaces()`, and **no `deleted_at` filter in any SELECT policy**. Grants stated explicitly; no DELETE, no TRUNCATE.
2. **Lifecycle states** — the [[Projects]] sequence (Idea → Planning → Generation → Review → Editing → Approval → Publishing → Analytics → Archive) as a `text` column with a CHECK constraint, following the `audit_log.action` precedent rather than an ENUM. Decide and document which transitions are legal; a state machine that permits every transition is a status field with extra steps.
3. **Repositories and a service** — `ProjectRepository` over `TenantConnectionDep`, `ProjectService` owning transition rules so they hold for any caller.
4. **Register for export and erasure** — add both stores to `REGISTERED_STORES`, and both tables to `_WORKSPACE_DEPENDANTS`.
5. **Tests** — isolation tests in the STEP-09 shape (cross-tenant read, update, delete), transition tests, and a **negative control** confirming each isolation test fails with the policy removed.

## Validation

- **A soft delete of a project actually succeeds**, asserted through the service — the defect STEP-19 found, guarded before it can recur.
- **Cross-tenant read, update and delete are refused**, and each assertion **fails when the policy is removed**.
- **An illegal lifecycle transition is refused**, and a legal one succeeds — both halves.
- **A workspace erasure reports non-zero counts for both new stores**, proving registration rather than assuming it.
- `test_teardown_covers_workspace_dependants` passes with the new tables present.
- Lint, type-check, tests and build pass for both apps in CI.

## Definition of Done

`projects` and `assets` exist with RLS in the same migration, lifecycle states are enforced with documented transitions, both tables are registered for export and erasure and in the test teardown list, and isolation is proven by tests that fail without the policies.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — database schema, multi-tenancy/RLS) and carries an **owner approval gate**.

---

## Navigation

- **Previous:** [[STEP-19 Settings and BYOK UI]]
- **Next:** [[STEP-21 Projects UI]]
- **Parent:** [[Build Plan]]
