---
title: STEP-20 Projects Schema and Lifecycle
category: Development/Build Step
status: stable
version: "2.0"
last_updated: 2026-08-08
tags: [engineering, workflow, build-step, database,backend]
step_id: STEP-20
step_status: Done
detail_level: full
---

# STEP-20 — Projects Schema and Lifecycle

**Status:** Done
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

## Outcome

`projects` and `assets` exist, isolated by RLS, with a lifecycle enforced in one place. Migration `e5a91c34d7f2` creates both tables with RLS **enabled and forced**, per-command policies routing through `app_current_user_workspaces()`, explicit grants, partial indexes and `touch_row` triggers. `ProjectRepository` reads and writes them over the tenant connection; `ProjectService` owns the state machine. **No HTTP routes were built** — the step's Tasks named none, and [[STEP-21 Projects UI]] owns them.

### The lifecycle gap in the specification was a decision, not an inference

[[Projects]] gives the sequence and never says which transitions are legal. Rather than guess ([[CLAUDE|CLAUDE.md]] §34), the question went to the project owner, who decided on 2026-08-08: **forward one step, plus the Review → Editing loop, plus Archive from anywhere, terminal.** Recorded in [[Project Lifecycle]].

Two smaller decisions were taken at the same time: `assets.project_id` is `NOT NULL` (an asset always belongs to a project), and this step ships schema and service only.

**The map is derived from three rules rather than written as a nine-entry literal**, because a literal is a fourth place the rules live and the one most likely to drift. The test suite inverts that — it writes the specification out as data and asserts it against the derivation across **all 81 ordered pairs, in both directions**. Asserting the legal moves proves the map has entries; asserting every pair proves it has no *extra* ones, which is the property a state machine exists for. A permissive bug passes every "the legal move works" test ever written.

### The denormalized `workspace_id` on `assets` needed a second mechanism

`assets` carries `workspace_id` as well as `project_id` so its RLS policy is identical in shape to every other tenant table's — a policy that joined through `projects` would be evaluated per row, read a second table under RLS, and make this table's tenant boundary depend on another table's policy rather than on the membership helper.

**That denormalization opens a hole RLS structurally cannot see**, and closing it is the step's most interesting piece of design. An INSERT naming the caller's **own** workspace — satisfying the policy, which only tests `workspace_id` — while pointing `project_id` at another tenant's project would be accepted, silently attaching a foreign asset to a project the caller cannot read. The composite foreign key to `projects (id, workspace_id)` refuses it. Observed: the insert fails with `ForeignKeyViolation`, not with an RLS error, which is exactly the point.

### The twice-paid `deleted_at` defect did not recur

Both tables are soft-deleted and **shipped without `deleted_at IS NULL` in their SELECT policies**, the first time that rule has been followed at creation rather than paid for in a later step ([[STEP-11a Membership Removal Policy]], [[STEP-19 Settings and BYOK UI]]). Liveness is filtered in every query, including both stores' export and erase methods. `test_soft_deleting_a_project_succeeds` asserts the soft delete **through the service**, so reintroducing the filter fails immediately rather than silently breaking an erasure path nothing covers.

Both stores were registered in `REGISTERED_STORES` and both tables in `_WORKSPACE_DEPENDANTS` **in the same change**, rather than in the later step that discovers the omission.

### Validation

No defect was found in the implementation. Three environment facts shaped how it was verified:

- **The pytest harness still cannot reach the development database** — STEP-19's recorded defect (`conftest.request_database_url` rebuilds the DSN with a bare `projectone_api` username, which the Supabase session pooler rejects). Unchanged and unfixed here; it is not this step's scope.
- **This machine has no local PostgreSQL and no Docker**, so the throwaway-container path is unavailable too.
- The 21 database-backed tests therefore **first execute in CI**.

Rather than leave the step's Validation unobserved until then, the same properties were driven in-process over the **real** `RequestSessionFactory` — the same connection, role and claim mechanism a request uses. **43 checks passed**, including every item the Validation section names:

- The soft delete succeeds through the service, and the row is *marked* rather than removed.
- Cross-tenant read, update, insert and delete are each refused; naming another tenant's project id returns nothing.
- The `WITH CHECK` half refused moving a project into another workspace.
- An illegal transition was refused **and wrote nothing**; a legal one succeeded and the trigger bumped `version`.
- All nine status values are accepted by the constraint and a tenth (`'shipped'`) is refused.
- Both stores export and erase non-zero counts, and cannot reach another tenant.
- `anon` holds nothing; `authenticated` holds no `DELETE` and no `TRUNCATE`.
- **A negative control disabled RLS on `projects`, observed the breach directly** (alice read bob's row), restored it, and confirmed isolation returned.
- `_WORKSPACE_DEPENDANTS` matches the catalog exactly at 8 tables.

The migration was applied, **downgraded, and re-applied** to verify the rollback path rather than assume it. Every probe row was removed and the database confirmed back to its prior contents by query — `projects` and `assets` both at zero.

Offline: `apps/api` grew from 325 tests to **343**, all passing; `ruff` and `mypy app` clean. `apps/web` is untouched and stays at 97 tests, with lint, typecheck and build all passing.

> [!warning] One probe run crashed before its cleanup
> An import error in the throwaway validation script aborted it after the assertions passed but before teardown, leaving 11 projects, 1 asset and 2 seeded tenants in the development database. Found immediately, removed by a marker-keyed cleanup script, and the database verified empty of both tables. Recorded rather than omitted: the failure mode is exactly why probe rows carry a marker, and a validation script that leaves state behind is a defect in the validation even when the code under test is correct.

### Recorded rather than forgotten

- **Two error types have no HTTP handler yet.** `ProjectNotFoundError` and `IllegalTransitionError` are unmapped because this step built no routes; STEP-21 owes them 404 and 409 respectively.
- **`assets.storage_path` points at nothing.** No storage backend is chosen, and the step that adds one also owes it a deletion path ([[CLAUDE|CLAUDE.md]] §16) — soft-deleting the row does not remove bytes.
- **`POST /projects` will need idempotency keys** when it exists, joining `POST /workspaces` in that still-unbuilt category.
- **[[Schema Overview]] was two migrations out of date** (`c9d3b71e08af` and `d1f70a4c62be` from STEP-19 were absent from a table claiming to be the full history). Added alongside this step's row, since the omission made the note actively misleading.
- **One stale line in [[Schema Overview]] is left as found**: *"Roles have no meaning yet"* has been untrue since STEP-11. Out of this step's scope ([[CLAUDE|CLAUDE.md]] §29) and flagged here rather than fixed silently.

---

## Navigation

- **Previous:** [[STEP-19 Settings and BYOK UI]]
- **Next:** [[STEP-21 Projects UI]]
- **Parent:** [[Build Plan]]
