---
title: STEP-07 Supabase Provisioning
category: Development/Build Step
status: draft
version: "1.4"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, database]
step_id: STEP-07
step_status: Done
---

# STEP-07 — Supabase Provisioning

**Status:** Done

> [!success] Approved by the project owner on 2026-08-01
> This is a **Critical change** ([[CLAUDE|CLAUDE.md]] §21 — database/infrastructure), so [[Execution Protocol#Owner Approval Gates]] held the queue after it was marked `Done`. **The project owner approved it on 2026-08-01**, clearing the gate; [[STEP-08 Users and Workspaces Schema]] proceeded.
>
> Approved as reviewed: Alembic as the migration tool, `/health` becoming a readiness check that returns 503 when the database is down, CI running against deliberately fake database credentials, and the unresolved Supabase REST 401 noted in [[#Outcome]] — the last accepted as a known issue to resolve by [[STEP-10 Authentication Backend]] rather than a blocker.

> [!note] Was `Blocked` on provisioning; resolved 2026-08-01
> Task 1 — *"provision a Supabase project"* — is an owner action: it creates a resource on an external service and produces credentials Claude must not handle ([[CLAUDE|CLAUDE.md]] §16). The step was `Blocked` before any code was written.
>
> **The project owner provisioned a development project and placed `SUPABASE_URL`, `SUPABASE_SECRET_KEY` and `DATABASE_URL` into `apps/api/.env`** (git-ignored). Connectivity was verified against the live database before implementation began: PostgreSQL 17.6, authenticated as `postgres`.
>
> **Migration tool: Alembic**, chosen by the owner over the Supabase CLI and hand-rolled SQL — see [[#Migration tool]].

## Goal

A provisioned development database with a tracked migration tool wired up — the mechanism for schema change, before any schema exists.

## Prerequisites

- [[STEP-06 Continuous Integration]] — `Done`

## Required Documentation

- [[Database Architecture]] — the data layer's shape
- [[Chapter 07 - Database Standards]] — migration and naming discipline
- [[CLAUDE|CLAUDE.md]] §13 — version-controlled schema, no manual SQL
- [[06 AI/MCP/Supabase|Supabase MCP]] — available tooling

## Tasks

1. Provision a Supabase project for **development only**. Staging and production come later, per [[CLAUDE|CLAUDE.md]] §28a.
2. Wire the connection through the STEP-05 config system — add the fields to `apps/api/app/core/config.py` and the corresponding placeholders to `apps/api/.env.example`, following the "Adding a Variable" sequence in [[Environment and Secrets]]. Credentials go in the local `.env`, never the repository. **Server-only credentials belong in `apps/api`; a service-role key must never carry the `NEXT_PUBLIC_` prefix or reach `apps/web`** — that prefix publishes the value into the browser bundle.
3. Set up the migration tool so every schema change is a tracked, version-controlled file. Manual SQL against a live database is forbidden ([[CLAUDE|CLAUDE.md]] §13).
4. Add migration commands to `scripts/`, idempotent and documented.

   **CI now exists** ([[STEP-06 Continuous Integration]]). Any variable added to `app/core/config.py` as *required* must also be added to the `api` job's `env:` block in `.github/workflows/ci.yml`, or CI goes red on the next push — the app refuses to start without it. Use a non-secret placeholder; a real credential belongs in a non-production repository secret, never in the workflow file.
5. Create one no-op or trivial migration and apply it, proving the pipeline works end to end.
6. Confirm `apps/api` can connect and report database health through `/health`.

## Validation

- The migration tool applies the trivial migration successfully.
- The migration is recorded in the tool's tracking table.
- Rolling that migration back succeeds — verify rollback works *now*, not during an incident.
- `/health` reports database connectivity.
- No credential appears in any tracked file (`git grep` for the project ref and key prefix).

## Definition of Done

A development Supabase project exists, migrations apply and roll back through a tracked tool, the API connects successfully, and no credential is committed. No application tables yet.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — database/infrastructure): flag for owner review.

## Outcome

A development Supabase project (PostgreSQL 17.6) is connected, Alembic applies and rolls back migrations through tracked files, and `/health` reports real database connectivity.

| | Detail |
|---|---|
| Database | Supabase, PostgreSQL 17.6, development only |
| Driver | `psycopg` 3.2.10 |
| Migrations | Alembic 1.18.5, `apps/api/migrations/` |
| Commands | `scripts/migrate.{sh,ps1}` — `up`, `down`, `status`, `history`, `new`, `sql` |
| First migration | `e37e521504a3` — creates and drops a throwaway table |

### Migration tool

**Alembic**, chosen by the project owner over the Supabase CLI and hand-written SQL. It runs anywhere Python does, so CI needs no extra toolchain; migrations live beside the code that depends on them; and it supports scripted `downgrade`, which this step's rollback check requires. The Supabase CLI favours forward-only migrations, which sits awkwardly with verifying rollback before an incident forces it.

Used in **plain-SQL mode**: `target_metadata` is `None` and autogenerate is unavailable. ProjectOne has no ORM decision yet, and wiring Alembic to SQLAlchemy models would pre-empt one silently. Adopting an ORM is an ADR, not a change to `env.py`.

### Decisions and notes for later steps

- **`/health` became a readiness check, not a liveness check.** It now reports per-dependency health and answers **503 `degraded`** when the database is unreachable. This was flagged as an open question in [[STEP-04 API App Skeleton]] and is now settled: an instance that is running but cannot reach its database must be pulled from a load balancer, and that only happens if the check says so. Both paths were observed against a live database and a deliberately unreachable one.
- **`repositories/` has its first occupant**, `DatabaseRepository`. Driver access lives there, not in the service — so pooling or swapping the driver later touches one file ([[Backend Architecture]]).
- **Credentials are `SecretStr`.** `repr()` renders `**********`, so a connection string cannot leak through a log line, a traceback or an error response. A test asserts this rather than trusting it.
- **The health check swallows driver exceptions and returns a boolean.** A `psycopg` error message can contain the connection string, and a health endpoint must never emit one ([[CLAUDE|CLAUDE.md]] §16, §24). Verified: the 503 response body carries no credential.
- **`DATABASE_URL` is stored in plain `postgresql://` form** and rewritten to `postgresql+psycopg://` inside `migrations/env.py`. SQLAlchemy reads the bare scheme as psycopg2, which is not installed. Normalizing there keeps `.env` copy-pasteable from the Supabase dashboard instead of making the driver a trap for whoever fills it in next.
- **No connection string is in `alembic.ini`.** That file is committed; `env.py` reads `DATABASE_URL` through the same validated `Settings` the application uses, so migrations and the app cannot disagree about which database they target.
- **CI uses deliberately fake database credentials.** No CI job touches a database — the tests substitute the repository — so wiring a real credential in would grant CI access it has no use for ([[CLAUDE|CLAUDE.md]] §16). A job that genuinely needs a database gets a throwaway one, never the development project.
- **Ruff exempts `migrations/versions/`** from docstring and naming rules. Alembic generates those from its own template with names it requires verbatim; enforcing house style there means hand-editing every new migration to satisfy a linter.
- **The Supabase REST API returns 401** with the provided `sb_secret_...` key, while the database connection works perfectly. Nothing in this step or the current codebase uses the REST API — the API talks PostgreSQL directly — so it is not a blocker. Most likely the key needs enabling for the REST role in the dashboard, or a different key type is required. **Deadline: [[STEP-10 Authentication Backend]]**, which is the first step likely to call Supabase Auth's admin API over HTTP and therefore the first real consumer of `SUPABASE_URL`/`SUPABASE_SECRET_KEY`. Recorded there so it cannot slide.
- **Only a development project exists.** Staging and production get their own projects with their own credentials, never shared ([[Environment and Secrets]]).

---

## Navigation

- **Previous:** [[STEP-06 Continuous Integration]]
- **Next:** [[STEP-08 Users and Workspaces Schema]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Database Architecture]] · [[Chapter 07 - Database Standards]]
