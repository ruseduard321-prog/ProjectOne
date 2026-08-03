---
title: "Table - ai_shutdown_switches"
category: Database Table
status: stable
version: "1.0"
last_updated: 2026-08-03
tags: [database, schema, ai, cost, security, multi-tenancy]
table_name: "ai_shutdown_switches"
---

# Table — ai_shutdown_switches

Created by migration `b2e6f0a71c94` ([[STEP-18 AI Cost Governance Controls]]).

## Purpose

The **emergency stop for AI spend**, at three scopes: one workspace, one workflow type, or the entire platform. [[CLAUDE|CLAUDE.md]] §15a requires a documented, fast path to disable spend "without a code deploy" — this is that path, and it is infrastructure rather than a hypothetical.

## Why a Table and Not an Environment Variable

An environment variable fails the requirement in the way that matters: changing it requires restarting every worker, which is a deploy in all but name and exactly the wrong operation to be performing during a cost incident.

A row is read on the next call, in every worker, with no restart. Demonstrated rather than asserted by `test_shutdown_takes_effect_without_a_restart`: the same service object serves a call, is shut down, and refuses the next one.

## Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Primary key. |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | When it was thrown. Newest matching switch wins. |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | Maintained by `touch_row()`. |
| `deleted_at` | `timestamptz` | — | Lifting a switch is a soft delete, so the record of an incident survives the incident. |
| `version` | `integer` | NOT NULL, default `1` | Maintained by `touch_row()`. |
| `workspace_id` | `uuid` | FK → `workspaces.id` `ON DELETE RESTRICT` | **NULL means platform-wide.** The one nullable tenant column in the schema. |
| `workflow_type` | `text` | — | NULL means every workflow type in this scope. |
| `reason` | `text` | NOT NULL | Why. A kill switch with no stated reason is one nobody can safely decide to turn off. |
| `activated_by` | `uuid` | — | Who threw it. Nullable: an automated anomaly response has no human actor, and recording a fake one would be worse than a NULL. |

**Indexes:** `ix_ai_shutdown_switches_workspace` on `(workspace_id)`, and `ix_ai_shutdown_switches_platform` on `(workflow_type) WHERE workspace_id IS NULL` — the platform switch is read on every AI call, so it gets its own index rather than a scan. Both partial on `deleted_at IS NULL`; at most a handful of live rows exist at any time.

## The Three Scopes

| `workspace_id` | `workflow_type` | Effect |
|---|---|---|
| `NULL` | `NULL` | **The whole platform.** |
| `NULL` | set | One workflow type, every workspace. |
| set | `NULL` | One workspace, every workflow. |
| set | set | One workspace, one workflow. |

All four are matched by a single query, ordered `created_at DESC LIMIT 1`, so the most recent applicable switch is the one that answers.

## The Platform Row Belongs to No Tenant

This is the table's one genuine departure from [[RLS Policy Pattern]], and it is the security property rather than an exception to it.

`workspace_id IS NOT NULL` appears in all three policies. On SELECT it is technically redundant — `NULL IN (SELECT ...)` evaluates to NULL, not true, so the platform row is already excluded — but it is stated anyway, because **relying on NULL comparison semantics for a security boundary is the kind of correctness that survives until someone rewrites the predicate in a way that looks equivalent.**

> [!danger] Both halves of the isolation matter
> - A tenant that could **read** the platform row would learn that a platform-wide incident is in progress — a fact about other customers.
> - A tenant that could **write** one would **disable AI for every customer on the platform**.
>
> Verified live: the platform switch is invisible to a tenant, and an attempt to insert one with `workspace_id = NULL` raises. It is created and read only on the privileged path (`AISpendRepository.set_platform_shutdown` / `active_shutdown`).

## The Refusal Does Not Disclose Its Scope

`AIShutdownError.public_message` is `"AI features are temporarily disabled"` regardless of which scope matched, and the internal reason string never reaches a client. A tenant told that a *platform-wide* shutdown is in effect has been told about an incident affecting other customers — the same reasoning that makes 401 and 403 bodies identical across causes in [[API Conventions]].

Guarded by `test_a_platform_shutdown_does_not_disclose_that_it_is_platform_wide`.

## Isolation

| Command | Rule |
|---|---|
| SELECT | Live membership **and** `workspace_id IS NOT NULL` |
| INSERT | `owner` or `admin` **and** `workspace_id IS NOT NULL` |
| UPDATE | `owner` or `admin` **and** `workspace_id IS NOT NULL` |
| DELETE | No policy, no grant |

`ENABLE` **and** `FORCE`, like every tenant table. Lifting a switch is an UPDATE setting `deleted_at`, governed by the UPDATE policy — so a workspace admin can lift their **own** workspace's switch but not another's, and no tenant can lift the platform's.

---

## Navigation

- **Previous:** [[Table - ai_budgets]]
- **Next:** [[Schema Overview]]
- **Parent:** [[Schema Overview]]
- **Related Notes:** [[AI Cost Governance]] · [[Table - ai_budgets]] · [[Table - ai_spend_records]] · [[RLS Policy Pattern]] · [[Security Architecture]]
