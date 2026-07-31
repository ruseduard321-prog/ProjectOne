---
title: STEP-09 Row Level Security Policies
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, database, security]
step_id: STEP-09
step_status: Not Started
---

# STEP-09 — Row Level Security Policies

**Status:** Not Started

## Goal

Enforce workspace isolation at the database layer, and establish the RLS pattern every future tenant table must follow.

## Prerequisites

- [[STEP-08 Users and Workspaces Schema]] — `Done`

## Required Documentation

- [[CLAUDE|CLAUDE.md]] §16 — multi-tenancy, RLS, no admin bypass
- [[Authentication and Authorization]] — how identity reaches the policy
- [[Security Architecture]] — isolation model
- [[Chapter 09 - Security Standards]]

## Tasks

1. Enable RLS on every tenant-scoped table from STEP-08.
2. Write policies filtering on workspace membership — a user reaches only their own workspace's rows.
3. Verify no bypass path exists. Admin and internal tooling do **not** get elevated cross-tenant raw access ([[CLAUDE|CLAUDE.md]] §16); cross-tenant needs go through an audited service path that does not exist yet and is not built here.
4. Write automated tests proving isolation: a user from workspace A cannot read, update or delete workspace B's rows. These tests are permanent regression protection, not one-off checks.
5. Document the policy pattern in the vault so later tables copy a reviewed approach rather than improvising.
6. Record the standing rule: **every future tenant table ships RLS in the same migration that creates it.**

## Validation

- RLS is enabled on every tenant-scoped table — query the catalog to confirm, don't assume.
- Isolation tests pass, and each one **fails when the policy is deliberately disabled**. An isolation test that passes with RLS off is testing nothing.
- Cross-tenant read, write and delete are all blocked — test all three, not just read.
- Tests run in CI.

## Definition of Done

Workspace isolation is enforced at the database layer, proven by tests that demonstrably fail without the policies, running in CI. The RLS pattern is documented for reuse. Application code may now touch these tables.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — security controls, multi-tenancy/RLS): flag for owner review. This is the single highest-consequence step in the foundation — a flaw here is a cross-tenant data breach, and it will not be caught by any later step.

---

## Navigation

- **Previous:** [[STEP-08 Users and Workspaces Schema]]
- **Next:** [[STEP-10 Authentication Backend]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Authentication and Authorization]] · [[Security Architecture]]
