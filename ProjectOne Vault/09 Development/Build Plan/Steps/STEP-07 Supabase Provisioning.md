---
title: STEP-07 Supabase Provisioning
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, database]
step_id: STEP-07
step_status: Not Started
---

# STEP-07 — Supabase Provisioning

**Status:** Not Started

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

---

## Navigation

- **Previous:** [[STEP-06 Continuous Integration]]
- **Next:** [[STEP-08 Users and Workspaces Schema]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Database Architecture]] · [[Chapter 07 - Database Standards]]
