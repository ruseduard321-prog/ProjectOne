---
title: Schema Overview
category: Architecture/Schema
status: stable
version: "1.0"
last_updated: 2026-08-01
tags: [database, schema, architecture]
aliases: ["Database Schema", "Current Schema"]
---

# Schema Overview

The tables that actually exist in ProjectOne's database right now, and the migrations that created them. This note describes **implemented schema**; [[Database Architecture]] describes the intended data model across all planned domains.

If the two disagree, this note describes reality and the other describes intent — neither is wrong, but only this one tells you what a query will find.

## Current Tables

As of [[STEP-18 AI Cost Governance Controls]]:

| Table | Purpose | Tenant-scoped | RLS |
|---|---|---|---|
| [[Table - users]] | Application-side profile, keyed to Supabase Auth identity | No | ✅ Enabled + forced |
| [[Table - workspaces]] | The tenant boundary | Is the boundary | ✅ Enabled + forced |
| [[Table - workspace_members]] | User ↔ workspace membership with role | Yes | ✅ Enabled + forced |
| [[Table - audit_log]] | Who changed what, and when — append-only | Yes | ✅ Enabled + forced (SELECT only) |
| [[Table - provider_credentials]] | Workspace AI provider keys (BYOK), encrypted at rest | Yes | ✅ Enabled + forced |
| [[Table - ai_spend_records]] | The AI spend ledger — append-only | Yes | ✅ Enabled + forced (SELECT only) |
| [[Table - ai_budgets]] | Spend ceilings, running totals and the spend breaker | Yes | ✅ Enabled + forced |
| [[Table - ai_shutdown_switches]] | Emergency stop for AI spend, at three scopes | Yes, **except the platform row** | ✅ Enabled + forced |

Two tables deliberately break [[Table Conventions]], and in both cases the departure **is** the security property:

- [[Table - audit_log]] — no `deleted_at`, no `version`, no `touch_row` trigger, and a single SELECT policy. An audit record its own subject can edit or remove is not an audit record.
- [[Table - ai_spend_records]] — keeps the standard columns but has no INSERT or UPDATE policy and no trigger. A client-writable spend ledger is forgeable, and a workspace could flood it to poison its own anomaly baseline.

[[Table - ai_shutdown_switches]] holds the schema's one **nullable** tenant column: `workspace_id IS NULL` means platform-wide, so that row belongs to no tenant and is deliberately unreachable by every RLS policy.

`alembic_version` also exists — Alembic's own migration tracking table, not application schema.

```mermaid
erDiagram
    users ||--o{ workspaces : "owns (RESTRICT)"
    users ||--o{ workspace_members : "member of (CASCADE)"
    workspaces ||--o{ workspace_members : "has members (CASCADE)"

    users {
        uuid id PK
        text email UK
        text display_name
    }
    workspaces {
        uuid id PK
        text name
        uuid owner_id FK
    }
    workspace_members {
        uuid id PK
        uuid workspace_id FK
        uuid user_id FK
        text role
    }
```

Every table also carries `created_at`, `updated_at`, `deleted_at` and `version` — see [[Table Conventions]].

## Migration History

Applied in order. History is append-only: a correction is a new migration, never an edit to an applied file.

| Revision | Description | Step |
|---|---|---|
| `e37e521504a3` | Create the throwaway `migration_pipeline_check` table, proving the pipeline works | [[STEP-07 Supabase Provisioning]] |
| `4c310926e967` | Drop `migration_pipeline_check` — it carried no application meaning | [[STEP-08 Users and Workspaces Schema]] |
| `8a6f39b07c12` | Create `users`, `workspaces`, `workspace_members`, plus the `touch_row` trigger function | [[STEP-08 Users and Workspaces Schema]] |
| `860a798d204b` | Enable and force RLS on all three tables, add the membership helper and eight policies | [[STEP-09 Row Level Security Policies]] |
| `c4f21a86b3de` | Narrow table grants to `SELECT/INSERT/UPDATE` for `authenticated`, nothing for `anon`, and correct the schema's default privileges so future tables inherit the same | [[STEP-10 Authentication Backend]] |
| `d7b95c1f4e08` | Create `projectone_api`, the request-path role that does **not** bypass RLS | [[STEP-10 Authentication Backend]] |
| `9f4d2c7a1b83` | Make the UPDATE policies role-aware, and add the role-filtered membership helper | [[STEP-11 Authorization and RBAC]] |
| `b8e1d94c50a7` | Make membership removal possible; move the `deleted_at` filter out of the SELECT policy and add the last-owner trigger | [[STEP-11a Membership Removal Policy]] |
| `a3c07d5e91f4` | Create the append-only `audit_log` with its SELECT-only policy and grants | [[STEP-13 Auth Users Workspaces Endpoints]] |
| `f1a4c8d29b57` | Create `provider_credentials` for BYOK keys, with membership-scoped reads and role-scoped writes | [[STEP-17 AI Router and Provider Abstraction]] |
| `b2e6f0a71c94` | Create `ai_spend_records`, `ai_budgets` and `ai_shutdown_switches` — the spend ledger, the ceilings, and the emergency stop | [[STEP-18 AI Cost Governance Controls]] |

Apply with `./scripts/migrate.sh up` (or `.\scripts\migrate.ps1 up`); see `scripts/README.md`.

## Database Objects Beyond Tables

| Object | Type | Purpose |
|---|---|---|
| `touch_row()` | Function (plpgsql) | Maintains `updated_at` and `version` on update — see [[Table Conventions#The touch_row Trigger]] |
| `app_current_user_workspaces()` | Function (sql, SECURITY DEFINER) | Returns the workspace ids the caller belongs to, read outside RLS to break policy recursion — see [[RLS Policy Pattern#The Membership Function]] |
| `trg_users_touch_row` | Trigger | Attaches `touch_row()` to `users` |
| `trg_workspaces_touch_row` | Trigger | Attaches `touch_row()` to `workspaces` |
| `trg_workspace_members_touch_row` | Trigger | Attaches `touch_row()` to `workspace_members` |
| `trg_provider_credentials_touch_row` | Trigger | Attaches `touch_row()` to `provider_credentials` |
| `trg_ai_budgets_touch_row` | Trigger | Attaches `touch_row()` to `ai_budgets` |
| `trg_ai_shutdown_switches_touch_row` | Trigger | Attaches `touch_row()` to `ai_shutdown_switches` |

`ai_spend_records` deliberately has **no** `touch_row` trigger: it is append-only, so there is no UPDATE for one to fire on.

## Roles

| Role | Bypasses RLS | Used by |
|---|---|---|
| `postgres` | **Yes** (`rolbypassrls` + `rolsuper`) | Alembic migrations only — `DATABASE_URL` |
| `projectone_api` | No | Every API request — `REQUEST_DATABASE_URL` |
| `service_role` | **Yes** (`rolbypassrls`) | Nothing on the request path |

`postgres` and `service_role` bypassing RLS is not fixable in a migration; the control is architectural, and [[STEP-10 Authentication Backend]] resolved it by giving the request path its own non-bypassing role. See [[RLS Policy Pattern#The Two Connections]].

## Outstanding

- **Roles have no meaning yet.** `workspace_members.role` fixes a vocabulary; what each role permits is [[STEP-11 Authorization and RBAC]].
- **Workspace creation has no service path.** The INSERT policies deliberately cannot bootstrap a workspace and its first membership row from a client — [[STEP-13 Auth Users Workspaces Endpoints]] owns the audited path.
- **`supabase_admin`'s default privileges are untouched.** `postgres` cannot alter them (it is not a superuser on managed Supabase). They govern tables Supabase creates, not ProjectOne's — see [[RLS Policy Pattern#Grants Are a Second, Independent Gate]].
- **No ORM.** Migrations are hand-written SQL through Alembic's `op` API. Adopting an ORM would be an ADR ([[08 ADR]]), not a quiet change.

---

## Navigation

- **Previous:** [[Web Session Handling]]
- **Next:** [[Table - users]]
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table Conventions]] · [[RLS Policy Pattern]] · [[Table - users]] · [[Table - workspaces]] · [[Table - workspace_members]] · [[Table - audit_log]] · [[Database Architecture]] · [[Chapter 07 - Database Standards]]
