---
title: STEP-09 Row Level Security Policies
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, database, security]
step_id: STEP-09
step_status: Done
---

# STEP-09 — Row Level Security Policies

**Status:** Done

> [!warning] Owner review required before STEP-10
> This is a **Critical change** ([[CLAUDE|CLAUDE.md]] §21 — security controls, multi-tenancy/RLS). Its Definition of Done is satisfied and it is committed, but [[Execution Protocol#Owner Approval Gates]] holds the queue: **[[STEP-10 Authentication Backend]] does not begin until the project owner confirms this step.** Silence is never approval.
>
> What to review: the `SECURITY DEFINER` helper and its lockdown; per-command policies rather than `FOR ALL`; `FORCE` alongside `ENABLE`; the deliberate absence of any DELETE policy; the co-membership rule on `users`; and the two items STEP-10 inherits — **the API must not connect as a role that bypasses RLS**, and table grants are still Supabase's permissive defaults.
>
> Also confirm the CI run, as with [[STEP-06 Continuous Integration]]: the service-container job could not be executed locally (no Docker available), so its first real run is the first push.

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

## Outcome

Workspace isolation is enforced at the database layer by migration `860a798d204b`, proven by 17 isolation tests that demonstrably fail without the policies, wired into CI against a throwaway PostgreSQL. The pattern is documented in [[RLS Policy Pattern]] for every later table to copy.

| | Detail |
|---|---|
| Migration | `860a798d204b` (head) |
| Tables protected | `users`, `workspaces`, `workspace_members` — all `ENABLE` **and** `FORCE` |
| Policies | 8, written per command (SELECT/INSERT/UPDATE), `TO authenticated` |
| Helper | `public.app_current_user_workspaces()` — `SECURITY DEFINER`, no parameters, `search_path` pinned |
| Tests | 17 in `apps/api/tests/test_rls_isolation.py`; 25 tests pass suite-wide |
| Documentation | [[RLS Policy Pattern]] (new) · [[Schema Overview]] · [[Table Conventions]] · the three table notes |

### The identity mechanism was settled, not guessed

The step note required confirming how identity reaches a policy before writing one. `auth.uid()` was verified to exist in the live database, reading `request.jwt.claim.sub` and returning NULL when no claim is set. Every policy inherits deny-by-default from that NULL. [[STEP-10 Authentication Backend]] owns *setting* the claim; this step only consumes it.

### Two defects found during validation

**1. Policy recursion, anticipated and confirmed.** A policy on `workspace_members` that subqueries `workspace_members` raises `infinite recursion detected in policy for relation`. Proven against a live database *before* the migration was written, and resolved with the `SECURITY DEFINER` helper. `test_membership_policy_does_not_recurse` guards it permanently.

**2. `REVOKE ... FROM PUBLIC` did not revoke `anon`'s access to the definer function.** Supabase ships `ALTER DEFAULT PRIVILEGES ... GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role` on `public`, so a new function is granted to those roles **by name** — and revoking from `PUBLIC` does not remove a named grant. Observed in the catalog: `anon` still held `EXECUTE` after the revoke. This is the exact bypass path Task 3 exists to catch, and it would have handed an unauthenticated role a function that reads membership with RLS switched off.

Fixed by revoking from `anon` and `service_role` explicitly. The migration had not been pushed, so it was corrected in place after a verified rollback ([[Table Conventions#Migration Discipline]]). `test_definer_function_is_not_executable_by_anon` guards it.

### Decisions and notes for later steps

- **`service_role` and `postgres` bypass RLS and no policy can stop them.** Both carry `rolbypassrls`. The control is architectural: the API must not use `SUPABASE_SECRET_KEY` or the `postgres` role for tenant queries. **[[STEP-10 Authentication Backend]] must establish which role the API connects as, and it must not be either of these.** Recorded in [[RLS Policy Pattern#What RLS Cannot Enforce]].
- **Table grants were left as Supabase's defaults.** `anon` and `authenticated` hold full DML on all three tables; RLS is what makes that safe. Tightening them belongs with STEP-10's role decision, not here — narrowing grants before knowing the API's role would be guessing.
- **The workspace-creation bootstrap deliberately does not pass the policies.** A creator's first membership row has no membership to test against, so it cannot be inserted by a client. Workspace creation is a two-statement operation for an audited service path ([[STEP-13 Auth Users Workspaces Endpoints]]).
- **No DELETE policy anywhere.** Removal is a soft delete via `deleted_at`. RLS denies DELETE by default with no policy present, so the absence is the control.
- **`users` policies are about co-membership, not workspace filtering** — it is not a tenant-scoped table.
- **CI gained a PostgreSQL service container**, and `PROJECTONE_REQUIRE_DATABASE_TESTS=1` makes a missing test database a hard failure there. Without it a broken container would downgrade the security suite to skips while CI still reported green.
- **The CI job itself is unverified.** No Docker or local PostgreSQL was available in this session, so the service-container path could not be executed — see Known limitation below.
- **No application code touches these tables yet.** This step is policy only.

### Known limitation

The isolation tests were validated against the **development Supabase project**, which has the genuine `auth.uid()`. They have *not* been executed against the stock `postgres:17` container CI uses, because neither Docker nor a local PostgreSQL was available in this session. The shim supplying `auth.uid()` on a bare server was verified to parse and to return the correct values (claim set → uuid, no claim → NULL), but the end-to-end CI job is unproven until the first push.

Confirming the CI run is an owner action, as it was for [[STEP-06 Continuous Integration]] — the build environment cannot observe workflow results on a private repository.

---

## Navigation

- **Previous:** [[STEP-08 Users and Workspaces Schema]]
- **Next:** [[STEP-10 Authentication Backend]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Authentication and Authorization]] · [[Security Architecture]]
