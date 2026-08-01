---
title: STEP-08 Users and Workspaces Schema
category: Development/Build Step
status: draft
version: "1.2"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, database]
step_id: STEP-08
step_status: Done
---

# STEP-08 — Users and Workspaces Schema

**Status:** Done

> [!warning] Owner review required before STEP-09
> This is a **Critical change** ([[CLAUDE|CLAUDE.md]] §21 — database schema). Its Definition of Done is satisfied and it is committed, but [[Execution Protocol#Owner Approval Gates]] holds the queue: **[[STEP-09 Row Level Security Policies]] does not begin until the project owner confirms this step.** Silence is never approval.
>
> What to review: `users` as a profile keyed to Supabase Auth with **no foreign key** to `auth.users`; `RESTRICT` on workspace ownership versus `CASCADE` on membership; partial unique indexes so soft deletion does not permanently reserve an email or block re-invitation; roles as `text` + `CHECK` rather than an `ENUM`; and the standard column set in [[Table Conventions]], which every later table will inherit.

## Goal

The two foundational tables — `users` and `workspaces` — plus the column conventions every later table inherits.

## Prerequisites

- [[STEP-07 Supabase Provisioning]] — `Done`

## Required Documentation

- [[Database Architecture]] — core domain tables
- [[Database Table Template]] — the required documentation format
- [[Chapter 07 - Database Standards]] — naming, constraints, indexing
- [[CLAUDE|CLAUDE.md]] §13 — expand/contract, soft deletion, auditability
- [[CLAUDE|CLAUDE.md]] §16 — workspace as tenant boundary

## Tasks

1. Write the migration creating `users` and `workspaces` with the membership relationship between them.

   **Tooling exists** as of [[STEP-07 Supabase Provisioning]]: create the file with `./scripts/migrate.sh new "<message>"`, write plain SQL through Alembic's `op` API (there is no ORM, so no autogenerate), and apply with `./scripts/migrate.sh up`. Write the `downgrade()` body at the same time as `upgrade()` — Validation requires a clean rollback, and it is far easier to write while the schema is fresh in mind.

   **Also remove migration `e37e521504a3`** (`migration_pipeline_check`). It was STEP-07's throwaway table proving the pipeline works, carries no application meaning, and should not survive into a schema with real tables. Deleting it is a migration of its own, not an edit to the existing file — history stays append-only.
2. Apply the standard column set to both: primary key, `created_at`, `updated_at`, soft-deletion column, and version/audit columns per [[CLAUDE|CLAUDE.md]] §13. **This step sets the pattern every later table copies** — get it right here rather than reconciling twelve tables later.
3. Add constraints enforcing integrity at the database layer, not in application code.
4. Index only the columns queried on the known access paths — no speculative indexing ([[CLAUDE|CLAUDE.md]] §13).
5. Document both tables using [[Database Table Template]] in the vault.
6. Confirm the migration is expand/contract-safe and independently rollback-safe.

## Tasks — explicitly out of scope

RLS policies. They are [[STEP-09 Row Level Security Policies]], deliberately separated so the policy work gets its own focused session and validation.

**Note:** this means STEP-08 leaves tenant tables temporarily without RLS. That is an incomplete state, not a shippable one — no application code touches these tables until STEP-09 is `Done`. Nothing between the two steps reads or writes tenant data.

## Validation

- Migration applies cleanly and rolls back cleanly.
- Both tables exist with the full standard column set.
- Constraints reject invalid data — test at least one violation per constraint and observe the rejection.
- Vault documentation for both tables exists and matches the actual schema, column for column.

## Definition of Done

`users` and `workspaces` exist via tracked migration, follow the column conventions later tables will inherit, enforce integrity through constraints, and are documented in the vault. RLS follows immediately in STEP-09.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — database schema): flag for owner review.

## Outcome

Three tables exist via tracked migration — `users`, `workspaces` and `workspace_members` — with the column conventions every later table inherits, integrity enforced by constraints, and full vault documentation.

| | Detail |
|---|---|
| Migrations | `4c310926e967` (drop throwaway table), `8a6f39b07c12` (create the three tables) |
| Head revision | `8a6f39b07c12` |
| Tables | `users`, `workspaces`, `workspace_members` |
| Standard columns | `id uuid`, `created_at`, `updated_at`, `deleted_at`, `version` |
| Documentation | [[Schema Overview]] · [[Table Conventions]] · [[Table - users]] · [[Table - workspaces]] · [[Table - workspace_members]] |

### A third table was created, not two

The step's title names two tables; three were built. `workspace_members` is the many-to-many join between them and is not separable from either — a user belongs to many workspaces and a workspace holds many users. Putting `workspace_id` on `users` instead would have to be undone by the first invite feature, and [[STEP-09 Row Level Security Policies]] needs a membership table to write its policies against. This is the relationship the step's Task 1 calls for ("the membership relationship between them"), not scope widening.

### Defect found and fixed during validation

The `touch_row` trigger initially used `now()` for `updated_at`. **`now()` returns transaction start time**, so a row inserted and then updated inside a single transaction kept an `updated_at` identical to its `created_at` — the column silently stopped meaning anything while still looking populated. Caught by a validation check comparing the two timestamps, fixed with `clock_timestamp()`, and re-verified (observed delta: 54 ms).

Worth recording because it is invisible in review: the SQL reads correctly, and the failure only appears when insert and update share a transaction. `created_at` keeps `now()` deliberately — rows written by one transaction should share a creation instant.

The migration file was corrected in place rather than by a follow-up migration, because it had not yet been committed or applied anywhere but the development database, which was rolled back first. Once a migration is pushed, history is append-only ([[Table Conventions#Migration Discipline]]).

### Decisions and notes for later steps

- **`users` is a profile, not an identity store.** Supabase Auth's `auth.users` owns passwords, MFA, sessions and OAuth links; `public.users.id` carries the same value. **No foreign key to `auth.users`** — that schema is owned and migrated by Supabase, and an FK would couple ProjectOne's migrations to it. [[STEP-10 Authentication Backend]] owns establishing and enforcing that link.
- **`email` is denormalized** from `auth.users` so member listings need not read a schema the API's role may not have access to. STEP-10 owns keeping the copy current.
- **Soft-delete uniqueness is partial.** `uq_users_email_active` and `uq_workspace_members_active` exclude soft-deleted rows, so deletion does not permanently reserve an email address or block re-inviting a removed member.
- **`RESTRICT` on `workspaces.owner_id`, `CASCADE` on both membership FKs.** Deleting a user must not destroy workspaces holding other people's work; a membership row is meaningless without both ends. Verified: deleting an owning user is rejected.
- **Roles are `text` + `CHECK`, not a PostgreSQL `ENUM`** — altering an enum's values requires rewriting the type, which locks a live table. [[STEP-11 Authorization and RBAC]] owns what the roles permit; this only fixes the vocabulary.
- **`version` has no consumer yet.** It is an optimistic-concurrency counter added now because backfilling one across every table later is far more expensive. The first read-modify-write endpoint will use it.
- **RLS is not enabled** — deliberately deferred to [[STEP-09 Row Level Security Policies]]. The tables hold no data and no application code touches them in the interval. [[Table Conventions#Row Level Security]] records this as a one-time exception that does not generalize.
- **No API code was written.** This step is schema only: no repository, no service, no endpoint reads these tables. The `/health` readiness check still passes untouched.

---

## Navigation

- **Previous:** [[STEP-07 Supabase Provisioning]]
- **Next:** [[STEP-09 Row Level Security Policies]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Database Architecture]] · [[Database Table Template]]
