---
title: "Table - ai_budgets"
category: Database Table
status: stable
version: "1.0"
last_updated: 2026-08-03
tags: [database, schema, ai, cost, multi-tenancy]
table_name: "ai_budgets"
---

# Table — ai_budgets

Created by migration `b2e6f0a71c94` ([[STEP-18 AI Cost Governance Controls]]).

## Purpose

The **spend ceiling itself**, and the running total it is compared against. This is the table that makes a budget a limit rather than an invoice: `spent_usd` is compared and incremented in a single statement before any provider is contacted, so PostgreSQL's row lock settles concurrency instead of application logic that would have to be right on every path.

It also carries the **spend circuit breaker**, which is a different mechanism from the availability breaker in `ProviderHealthTracker` — see [[AI Cost Governance]].

## Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Primary key. |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Standard column. |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | Maintained by `touch_row()`. |
| `deleted_at` | `timestamptz` | — | Soft deletion. |
| `version` | `integer` | NOT NULL, default `1` | Maintained by `touch_row()`. |
| `workspace_id` | `uuid` | NOT NULL, FK → `workspaces.id` `ON DELETE RESTRICT` | The tenant this ceiling governs. |
| `workflow_type` | `text` | — | **NULL means workspace-wide**; a value scopes the ceiling to one workflow type. |
| `limit_usd` | `numeric(12,6)` | NOT NULL, `> 0` | The ceiling. |
| `spent_usd` | `numeric(12,6)` | NOT NULL, default `0`, `>= 0` | The running total. The column that makes the ceiling race-free. |
| `period_started_at` | `timestamptz` | NOT NULL, default `now()` | When the running total was last reset. |
| `period_interval` | `interval` | NOT NULL, default `'30 days'` | How long a period lasts. |
| `breaker_tripped_at` | `timestamptz` | — | When the spend breaker opened. NULL means closed. |
| `breaker_reason` | `text` | — | Why. A kill switch with no stated reason is one nobody can safely reopen. |

## Why `limit_usd > 0` Rather Than `>= 0`

A zero ceiling and "no ceiling configured" must not be the same configuration. **No row** already expresses "unmetered"; a zero-limit row would express "refuse every call", which is what [[Table - ai_shutdown_switches]] is for and says far more clearly.

## Two Unique Indexes, Not One

```sql
uq_ai_budgets_workspace_workflow_live  (workspace_id, workflow_type)
    WHERE deleted_at IS NULL AND workflow_type IS NOT NULL

uq_ai_budgets_workspace_default_live   (workspace_id)
    WHERE deleted_at IS NULL AND workflow_type IS NULL
```

**PostgreSQL treats NULLs as distinct in a unique index**, so a single index on `(workspace_id, workflow_type)` would permit unlimited rows with a NULL `workflow_type` — precisely the workspace-wide budget that must be unique. `NULLS NOT DISTINCT` would solve it on PostgreSQL 15+, but two explicit partial indexes say what is meant without depending on that version behaviour.

Both partial on `deleted_at IS NULL`, so a removed budget does not block configuring a new one.

## The Two Scopes Apply as a Conjunction

A call must pass **both** the workspace-wide ceiling and the one scoped to its workflow type. Neither can be used to escape the other. Modelling both in one table rather than two keeps the enforcement check a single query, and the reservation locks both rows `ORDER BY id` so concurrent calls queue rather than deadlock.

**All-or-nothing:** a reservation refused by one ceiling rolls back what it already took from the other. Without that, a workspace repeatedly refused by a tight workflow cap would still bleed its workspace cap dry on calls that never happened.

## Periods, Not Lifetimes

`period_started_at + period_interval <= now()` resets `spent_usd` to zero. Without it, a ceiling is a lifetime cap every workspace eventually hits and never recovers from.

The reset advances `period_started_at` to `now()` rather than by exactly one interval. For a workspace dormant for several periods, advancing by one interval would leave the row still expired and reset it again on the next call; this starts a fresh period from the moment of first use.

Done in SQL with `now()` rather than in Python, so the comparison and the write are one statement — two concurrent callers cannot both decide a period expired and both reset it, which would advance the period twice and grant a workspace two allowances.

> [!warning] A period reset deliberately does not clear a tripped breaker
> A tripped spend breaker is an incident someone should look at. Having it silently clear itself when a billing period rolls over would let a runaway resume on a schedule ([[CLAUDE|CLAUDE.md]] §15a — a tripped breaker stops, it does not degrade into a delay). Guarded by `test_a_period_reset_does_not_clear_a_tripped_breaker`.

## Isolation

| Command | Rule |
|---|---|
| SELECT | Live membership — **any member**, so a refused user can see why |
| INSERT | `owner` or `admin` |
| UPDATE | `owner` or `admin`, with `WITH CHECK` |
| DELETE | No policy, no grant |

The asymmetry mirrors [[Table - provider_credentials]]: reads are membership-scoped because a tripped ceiling has to be explainable to whoever was refused, while changing a spend limit is a billing-adjacent decision belonging to the roles that already control them.

Verified live: a tenant cannot see another workspace's budget, and an attempt to raise one affects **0 rows** — a `USING` mismatch affects zero rows silently rather than raising, so the test asserts the count rather than expecting an error ([[RLS Policy Pattern]]).

> [!warning] Known limitation: an owner can zero their own `spent_usd`
> The UPDATE policy exists so a settings route can change `limit_usd` and `period_interval`, and PostgreSQL policies are per-row, not per-column — so the same policy reaches the running total. An owner could therefore grant themselves fresh allowance.
>
> The mitigation is that **[[Table - ai_spend_records]] is the immutable record** and is what a billing reconciliation reads; this counter is enforcement state, not the account of what was spent. Closing it properly means a column-level grant, which is a schema change belonging to the step that adds the settings route ([[STEP-19 Settings and BYOK UI]]). Recorded rather than glossed, and asserted honestly by `test_a_tenant_cannot_clear_its_own_running_total`, which documents the current exposure instead of claiming a protection that does not exist.

---

## Navigation

- **Previous:** [[Table - ai_spend_records]]
- **Next:** [[Table - ai_shutdown_switches]]
- **Parent:** [[Schema Overview]]
- **Related Notes:** [[AI Cost Governance]] · [[Table - ai_spend_records]] · [[Table - ai_shutdown_switches]] · [[RLS Policy Pattern]] · [[Table Conventions]]
