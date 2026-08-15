---
title: Backup and Disaster Recovery
category: Project Bible/Delivery and Trust
status: draft
version: "0.2"
last_updated: 2026-08-15
tags: [project-bible, deployment, documentation]
aliases: ["48 Backup Disaster Recovery", "Backup & Disaster Recovery"]
source_pdf: "[[12 Assets/PDF/ProjectOne_48_Backup_Disaster_Recovery_v0.1.pdf|ProjectOne_48_Backup_Disaster_Recovery_v0.1.pdf]]"
---

# ProjectOne — Backup & Disaster Recovery (Draft v0.1)

## Purpose

Ensure business continuity through reliable backups and disaster recovery planning.

## Backup Strategy

Encrypted daily, weekly and monthly backups with periodic restore testing.

## Recovery Objectives

**Restore capability is proven — executed, verified, and re-run on every pull request. The objectives themselves are provisional and await the owner.** [[STEP-25a Foundation Remediation]] (FA-03) closed the gap this section previously described — that RPO and RTO *should be defined* while no values existed and no restore had ever been performed.

### What is now proven

`apps/api/scripts/backup_restore_drill.py` executes a real drill against a **disposable** PostgreSQL 17 database, and runs as a step of the `api` CI job on every pull request:

1. migrations applied to head,
2. representative data seeded across **two workspaces**, so the restore is verifiable as tenant-correct rather than merely non-empty,
3. `pg_dump` backup taken,
4. restored into a **separate, empty database** — restoring over the source would pass even on an empty dump,
5. schema **and** per-workspace data verified against the source: tables, constraints, RLS enabled *and* forced, policy count, the Alembic revision pointer, and row content per tenant.

The drill refuses to run against `supabase.co`, RDS or Azure hosts before connecting. **The shared Supabase development database has never been a target of it.**

### Provisional figures — not an SLA

> [!warning] These are drill measurements, not commitments
> Timings are recorded by each CI run against a **seeded test database**, not against production data volumes. They describe what the mechanism does today; they are **not** an RPO/RTO commitment, and must not be quoted as one.
>
> **Setting the actual targets is an owner decision** and is deliberately left open. A recovery objective is a business commitment about acceptable data loss and acceptable downtime — it is not derivable from how fast a test database happens to restore.

| Objective | Status | Note |
|---|---|---|
| **RPO** (acceptable data loss) | **Not set — owner decision required** | Depends on backup frequency, which the hosting arrangement determines |
| **RTO** (acceptable downtime) | **Not set — owner decision required** | The drill measures restore duration at test scale only |
| Restore *capability* | **Proven 2026-08-15** | Executed in CI; schema, per-tenant data, RLS flags and the migration pointer all verified against the source |

### Still outstanding

- **Production-scale timings.** The drill measures a seeded database. Real figures need production-representative volumes.
- **Backup scheduling and retention.** Supabase's own backup arrangement, its frequency, and how long backups are kept — the encrypted-backup ageing referenced in [[CLAUDE|CLAUDE.md]] §16 as a bounded, disclosed exception to erasure.
- **The disaster-recovery runbook** below: who does what, in what order, and how it is communicated.

## Disaster Recovery

Document recovery procedures, responsibilities and communication plans.

## Success Criteria

Critical services can be restored within defined recovery objectives.

---

## Navigation

- **Previous:** [[Compliance and Governance]]
- **Next:** —
- **Parent:** [[Project Bible MOC]]
- **Related Notes:** [[Infrastructure]] · [[Security Architecture]] · [[STEP-25a Foundation Remediation]]
