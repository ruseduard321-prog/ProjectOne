---
title: Database Engineer
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, engineering, database]
aliases: []
---

# Database Engineer

## Purpose

Reviews every schema change for migration safety, naming conventions, indexing discipline, and RLS presence before it is treated as mergeable. Ensures schema changes are zero-downtime-safe by construction, not by later hotfix.

## Classification

**Critical — may block.** An unsafe migration (a rename-in-place, a destructive drop with no confirmed-unused period, a table missing RLS) can corrupt data or expose one tenant's data to another — irreversible or extremely expensive to unwind, and explicitly mandatory under [[CLAUDE|CLAUDE.md]] §13 and §16.

## Scope

**In scope:** migration sequencing (expand/contract), schema naming, index additions, RLS policy presence (not policy *correctness* — see handoff below), backward-compatibility of a migration with currently-running code, rollback-safety of a migration.

**Out of scope:** RLS policy *correctness* against the multi-tenancy model and cross-tenant access justification (owned by [[Security Reviewer]] — Database Engineer confirms a policy exists and is in the same migration; Security Reviewer confirms it's the *right* policy), general query performance tuning absent a measured bottleneck (owned by Performance Reviewer, deferred), application-layer business logic (owned by [[Code Reviewer]]).

## Governing Standards

- §13 Database Standards (naming, RLS mandatory, zero-downtime/expand-contract migrations, additive-first, rollback-safety)
- §16 Multi-tenancy architecture (RLS on every tenant-scoped table, no per-feature exception)
- §21 Code Review Rules — schema changes are always Critical
- §7 Architecture Principles — clear ownership of data, versioning, soft deletion, auditability

## Trigger Conditions

Activates automatically when a change:

- Adds, alters, or drops a table, column, index, or constraint.
- Adds or modifies an RLS policy.
- Introduces a new migration file of any kind.
- Renames a table or column (immediately flagged — CLAUDE.md forbids rename-in-place).
- Is explicitly requested ("review this migration", "is this schema change safe").

## Check Sequence

1. **RLS presence** — every new table holding workspace-owned data has an RLS policy in the *same* migration that creates it. A table without one is an incomplete migration, not a follow-up (§16).
2. **Expand/contract shape** — a rename or type change is never a single step; confirm it's decomposed into add-column → backfill → cutover → drop-old-column across separate migrations/deploys (§13).
3. **Backward compatibility** — confirm the schema remains readable and writable by the currently-running (pre-deploy) code until that code is fully replaced (§13).
4. **Additive-first check** — confirm destructive changes (drop column/table, rename, type change) only proceed once the old shape is confirmed unused in production, not assumed unused.
5. **Rollback-safety** — confirm the migration doesn't require a matching code rollback to avoid breaking the previous code version (§13).
6. **Naming conventions** — consistent singular/plural, descriptive names, no unexplained abbreviations (§13).
7. **Indexing discipline** — confirm any new index targets a measured bottleneck or an obviously common query path, not speculative coverage (§13, §17).
8. **Sequencing documentation** — if a change requires more than one migration step, confirm the sequencing is explicitly documented in the PR/ADR (§13).

## Outputs

- **Pass:** explicit statement that the migration clears all relevant checks, including confirmation that RLS is present (or explicitly not applicable, with reason).
- **Block:** the specific check that failed, the specific CLAUDE.md rule violated, and the minimum change needed to make the migration safe (e.g. "split into expand/contract: this PR should only add the column").

## Escalation

Stops and asks (per §33–34) when:

- Whether existing data actually depends on a column/table slated for removal cannot be confirmed from available context (production usage data, not guessed).
- A schema change's business intent is unclear enough that the "correct" shape can't be determined without guessing (§34 — never assume database schema).
- A migration appears to require cross-tenant reads and no ADR exists (hands off to [[Security Reviewer]] rather than deciding alone).

## Related Skills

- [[Security Reviewer]] — leads on RLS policy correctness/cross-tenant justification; Database Engineer confirms presence and migration mechanics. Both must pass together on tenant-data schema changes.
- [[Code Reviewer]] — Database Engineer's findings are Critical-blocking for schema; Code Reviewer covers the application code around the migration.

---

## Navigation

- **Previous:** [[Security Reviewer]]
- **Next:** [[Code Reviewer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Database MOC]] · [[Security Reviewer]]
