---
title: "Table - ai_spend_records"
category: Database Table
status: stable
version: "1.0"
last_updated: 2026-08-03
tags: [database, schema, ai, cost, multi-tenancy]
table_name: "ai_spend_records"
---

# Table — ai_spend_records

Created by migration `b2e6f0a71c94` ([[STEP-18 AI Cost Governance Controls]]).

## Purpose

The **append-only ledger of every AI call that cost money**. It answers *what did we spend, on what, and for whom* — the attribution source behind billing reconciliation, per-workspace usage reporting, and the anomaly baseline that trips the spend circuit breaker.

It is deliberately **not** what a budget ceiling reads. Answering "may this call proceed" with `SELECT sum(cost_usd) ...` would mean an aggregate over an unbounded table on every request, and — far worse — a check that races. The ceiling lives in [[Table - ai_budgets]], as a running total compared and incremented in one statement.

## Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Primary key. |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | When the spend occurred. |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | Standard column; never actually changes — see below. |
| `deleted_at` | `timestamptz` | — | Standard column, filtered by the SELECT policy. |
| `version` | `integer` | NOT NULL, default `1` | Standard column. |
| `workspace_id` | `uuid` | NOT NULL, FK → `workspaces.id` `ON DELETE RESTRICT` | The tenant that spent. |
| `provider` | `text` | NOT NULL | Which provider answered — **the one that actually served it**, which after a fallback is not the one selection first chose. |
| `model` | `text` | NOT NULL | The specific model. Cost varies far more by model than by vendor. |
| `workflow_type` | `text` | NOT NULL | What incurred the spend. The dimension per-workflow ceilings are keyed on. |
| `prompt_tokens` | `integer` | NOT NULL, `>= 0` | Reported by the provider, never estimated. |
| `completion_tokens` | `integer` | NOT NULL, `>= 0` | Reported by the provider, never estimated. |
| `cost_usd` | `numeric(12,6)` | NOT NULL, `>= 0` | Computed from real usage via `app/ai/pricing.py`. |
| `actor_id` | `uuid` | — | Who triggered it. Nullable: an automated run has no human actor. |

**Indexes** (both partial on `deleted_at IS NULL`, matching the policy predicate so filtered queries stay index-served):

- `ix_ai_spend_records_workspace_created` on `(workspace_id, created_at DESC)` — what anomaly detection reads, a range scan per workspace.
- `ix_ai_spend_records_workspace_workflow` on `(workspace_id, workflow_type)` — per-workflow attribution.

## `numeric`, Never `float`

Money in binary floating point accumulates error, and these values are summed into totals a ceiling is compared against. A ceiling compared against a drifting total is a ceiling that drifts. `Decimal` is used throughout the application layer for the same reason.

Twelve digits with six after the point holds a single call's fraction-of-a-cent cost and a large lifetime total alike.

## Why `provider` Has No CHECK Constraint

Unlike [[Table - provider_credentials]], whose `provider` column is constrained to a fixed list. The asymmetry is deliberate:

- That column decides whether a key can **ever be used**, so a typo must fail loudly at write time.
- This one records something that **already happened**. Refusing to record a completed call because a new provider was added without a migration would lose the spend rather than the typo — and the money is gone either way.

## Append-Only, Enforced by Absence

| Command | Policy | Grant |
|---|---|---|
| SELECT | membership-scoped | `SELECT` |
| INSERT | **none** | **none** |
| UPDATE | **none** | **none** |
| DELETE | **none** | **none** |

`authenticated` holds `SELECT` and nothing else. Writes happen only on the privileged path, via `AISpendRepository.record` — the audited-service-path shape [[CLAUDE|CLAUDE.md]] §16 requires for operations RLS deliberately forbids, the same as [[Table - audit_log]].

> [!danger] A client-writable ledger is worse than a missing one
> Beyond forging a charge, a workspace able to insert rows could **flood the ledger to poison its own anomaly baseline** — making a genuine runaway look like ordinary usage and keeping the spend breaker closed through exactly the incident it exists to catch.

It carries `deleted_at`, `updated_at` and `version` for [[Table Conventions]] consistency, but no `touch_row` trigger: there is no UPDATE for one to fire on.

## Retention: Exportable, Not Erasable

Registered with [[Authorization Model]]'s data-ownership registry as `AISpendRecordStore`. A workspace export includes the full ledger; a workspace erasure reports `"ai_spend_records": 0`.

**The second documented retention exception after the audit log**, and it rests on the same principle applied to a different obligation. A spend record is a **financial record**: it substantiates what a customer was charged and is the evidence behind any billing dispute, refund or chargeback. Letting the party who incurred the spend erase the record of it is the same defect as letting an actor erase their own audit trail.

It also carries no personal data beyond the workspace and an optional actor — token counts and dollar amounts, never prompt or completion content — which is what makes retaining it proportionate rather than an erasure loophole.

The exception is **visible** in the erasure response rather than silent, so a reader can question it ([[CLAUDE|CLAUDE.md]] §16 requires disclosure).

## Isolation

Standard [[RLS Policy Pattern]] SELECT policy, `ENABLE` **and** `FORCE`. Verified behaviourally against a live database over the request-path connection: another tenant's spend is invisible, forging a record raises, rewriting one raises, deleting one raises — with a negative control disabling RLS, observing the breach, and restoring it.

Spend history is commercially sensitive beyond the money itself: it reveals a competitor's usage volume, model choices and activity patterns.

---

## Navigation

- **Previous:** [[Table - provider_credentials]]
- **Next:** [[Table - ai_budgets]]
- **Parent:** [[Schema Overview]]
- **Related Notes:** [[AI Cost Governance]] · [[Table - ai_budgets]] · [[Table - ai_shutdown_switches]] · [[RLS Policy Pattern]] · [[Table Conventions]]
