---
title: STEP-08 Users and Workspaces Schema
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, database]
step_id: STEP-08
step_status: Not Started
---

# STEP-08 — Users and Workspaces Schema

**Status:** Not Started

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

---

## Navigation

- **Previous:** [[STEP-07 Supabase Provisioning]]
- **Next:** [[STEP-09 Row Level Security Policies]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Database Architecture]] · [[Database Table Template]]
