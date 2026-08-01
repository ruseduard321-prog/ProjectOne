---
title: STEP-09 Row Level Security Policies
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-01
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
- [[Schema Overview]] — the tables that now exist
- [[Table - workspace_members]] — the table policies will consult

## What STEP-08 actually built

Three tables, not two ([[STEP-08 Users and Workspaces Schema#Outcome]]):

| Table | Tenant-scoped | Note for policy design |
|---|---|---|
| `users` | **No** — a user is not owned by a workspace | Reachable by any workspace co-member; the policy is about *which* users are visible, not workspace filtering |
| `workspaces` | **Is the boundary** | Visible when the requester has a live membership row |
| `workspace_members` | Yes | **The table every other policy consults** |

Two consequences worth knowing before writing a line of SQL:

- **`workspace_members` protecting itself is the subtle case.** A policy on that table that queries that table recurses. The usual resolution is a `SECURITY DEFINER` helper function that reads memberships outside RLS, which must then be written carefully enough that it cannot itself become the bypass this step exists to prevent.
- **Membership is soft-deleted, so every policy must filter `deleted_at IS NULL`.** A removed member whose row still exists must not retain access. The partial indexes (`uq_workspace_members_active`, `ix_workspace_members_user_id`) already carry that predicate, so policies matching it stay index-served.

Identity does not yet reach the database — [[STEP-10 Authentication Backend]] establishes how a request's user becomes visible to a policy (`auth.uid()` or an equivalent). Confirm which mechanism applies before writing policies that depend on it; if it is not settled, that is a `Blocked` step, not a guess ([[CLAUDE|CLAUDE.md]] §34).

## Tasks

1. Enable RLS on every tenant-scoped table from STEP-08 — see the table above for which are tenant-scoped and which is not.
2. Write policies filtering on workspace membership — a user reaches only their own workspace's rows. Every policy filters out soft-deleted membership rows.
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
