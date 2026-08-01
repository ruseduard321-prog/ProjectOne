---
title: STEP-11 Authorization and RBAC
category: Development/Build Step
status: stable
version: "1.2"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, security,backend]
step_id: STEP-11
step_status: Done
detail_level: full
---

# STEP-11 — Authorization and RBAC

**Status:** Done
**Detail level:** full — expanded by [[STEP-10 Authentication Backend]], per [[Execution Protocol]].

## Goal

Role-based access control layered above the RLS policies, so every action is validated against explicit permissions before execution.

## Scope

Includes the structural start of data ownership/export/delete mechanics per [[Privacy and Data Protection]] — retrofitting deletion is expensive ([[CLAUDE|CLAUDE.md]] §16). UI for it comes later.

## Prerequisites

- [[STEP-10 Authentication Backend]] — `Done`

## Required Documentation

- [[Authentication and Authorization]]
- [[Privacy and Data Protection]]
- [[RLS Policy Pattern]] — what the database already enforces, so RBAC does not duplicate it
- [[CLAUDE|CLAUDE.md]] §16

## Inherited from earlier steps

Recorded during synchronization, not expansion.

- **RLS enforces the workspace boundary; it does not distinguish roles.** [[STEP-09 Row Level Security Policies]] wrote policies that ask "is this requester a live member of the workspace", nothing finer. `workspace_members.role` exists and is constrained to `owner`/`admin`/`member`, but **no policy reads it** — an ordinary member can currently update the workspace row exactly like its owner.
- **This step owns closing that gap**, and must decide where: tightening the RLS policies to consult `role`, enforcing in the service layer above them, or both. Defence in depth argues for both ([[CLAUDE|CLAUDE.md]] §16); duplicating a rule in two places argues for care about which is authoritative.
- **Deletion is soft-only at the database layer.** No table has a DELETE policy, deliberately ([[RLS Policy Pattern#DELETE is granted to no one]]). The export/delete mechanics in this step's scope must work with `deleted_at`, not hard deletes.

Added by [[STEP-10 Authentication Backend]]:

- **The request path now exists and is what RBAC plugs into.** Every authenticated request runs as `projectone_api` → `SET LOCAL ROLE authenticated` with the caller's `sub` claim set, inside one transaction ([[Authentication Implementation]]). `CurrentUserDep` yields the verified identity; `TenantConnectionDep` yields an RLS-subject connection. A permission check belongs between those two, not inside a router.
- **`AuthenticatedUser` carries only `id` and `email` today.** It has no role, because nothing reads one. This step decides whether the role is resolved per request (a membership lookup) or carried on the token (a Supabase custom claim), and the two have very different invalidation behaviour — a token-carried role stays stale until the token expires.
- **Grants are now narrow: `authenticated` holds `SELECT`, `INSERT`, `UPDATE` and nothing else** (`c4f21a86b3de`). RBAC tightens *within* that, never widens it. Anything requiring DELETE is a design error, not a grant to add back.
- **Typed errors exist.** `app/core/security.py` defines `AuthError` and subclasses, translated to status codes in one place. An authorization failure is a **403**, not a 401 — the caller authenticated fine and simply may not do this — and needs its own type rather than being folded into `InvalidTokenError`.

## Tasks

1. **Decide where roles are enforced, and record why.** Three options: tighten the RLS policies to consult `workspace_members.role`; enforce in a service layer above them; or both. Defence in depth argues for both ([[CLAUDE|CLAUDE.md]] §16); duplicating a rule in two places argues for naming which is authoritative. This is the load-bearing decision — write it down before writing code, and treat it as Critical.
2. **Decide how a request's role is resolved** — per-request membership lookup or a token claim — and state the invalidation consequence. A role demoted mid-session must not stay effective until the token expires.
3. **Define what each role permits.** `owner`, `admin`, `member` are a vocabulary with no meaning today. Produce an explicit matrix of role × action; an undocumented permission model is one that drifts.
4. **Implement the permission check** as a reusable dependency alongside `CurrentUserDep`, so requiring a permission is declarative at the route rather than an `if` inside a handler ([[CLAUDE|CLAUDE.md]] §12: no business logic in routers).
5. **If policies are tightened**, ship the migration following [[RLS Policy Pattern]], and add isolation tests that fail when the new predicate is removed.
6. **Begin data ownership/export/delete mechanics** per [[Privacy and Data Protection]] — structural only, no UI. Work with `deleted_at`; hard deletes are denied by both the missing policy and the revoked grant.
7. **Return 403, not 401, for authorization failures**, with a new `AuthError` subclass and the router mapping.

## Validation

- A `member` cannot perform an `owner`-only action **through the API**, and an `owner` can. Test both directions — a check that denies everything passes a one-sided test.
- If policies were tightened: the new tests fail when the role predicate is removed ([[RLS Policy Pattern#Testing]]).
- A role changed mid-session takes effect within the documented window, and that window is stated rather than discovered.
- Authorization failures return 403 and authentication failures still return 401 — the two are not conflated.
- The STEP-09 and STEP-10 isolation tests still pass. RBAC narrows access; it must not have widened anything.
- Lint, format, type-check and the full suite pass in CI.

## Definition of Done

Every action is validated against an explicit, documented permission before execution; the role model is written down rather than implied; role enforcement is tested in both directions; and the structural basis for data export/deletion exists.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — authorization, security controls, multi-tenancy): flag for owner review.

## Outcome

**Roles are now enforced in both layers, with the database authoritative.** The full model — matrix, enforcement split, invalidation window, 401/403 rule — is [[Authorization Model]]; it is not restated here.

Migration `9f4d2c7a1b83` replaces the two role-blind UPDATE policies and installs `app_current_user_workspaces_as(text[])`, the role-filtered sibling of STEP-09's helper. Above them, `requires(<permission>)` is a declarative route dependency, `AuthorizationService` makes the decision, and a single exception handler maps it to 403. The suite grew from 58 tests to 96.

### Three defects found during validation, all reproduced against a live database

1. **`migrations/env.py` discarded the test harness's database URL.** It overwrote `sqlalchemy.url` from `DATABASE_URL` unconditionally, so conftest's override — the thing that exists so *"a test run can never migrate the development database by accident"* — did nothing. Every migration a test run applied went to whatever `DATABASE_URL` pointed at. Invisible in CI, where the two happen to be the same throwaway container; on a developer machine it means a test run migrating the development project. Fixed: an explicitly supplied URL now wins.

2. **This step's migration branched the history.** `down_revision` was set to `c4f21a86b3de` when the real head was `d7b95c1f4e08`, producing `MultipleHeads` on every migration attempt. Corrected.

3. **The own-row WITH CHECK rejected the operation it was written for.** The clause re-tested membership, and `app_current_user_workspaces()` filters `deleted_at IS NULL`, so a row being soft-deleted no longer satisfied it. Removed — the `USING` clause and `user_id = auth.uid()` already establish everything it added.

### The finding that outlived the step

> **Soft-deleting a `workspace_members` row is impossible for every role, including `owner`.**

Not an authorization limit. STEP-09's `workspace_members_select_same_workspace` filters `deleted_at IS NULL`, so the row being soft-deleted becomes invisible to the very statement writing it and PostgreSQL rejects the `UPDATE`. Verified in all three directions — a member erasing their own row, a member erasing another's, an owner erasing a member's — and confirmed by observing the same update succeed once that filter was lifted.

**Consequences, none of them worked around:**

- *Leaving a workspace* and *removing a member* have no working database path yet.
- `WorkspaceMembersStore.erase` returns `0` rather than raising or running over the privileged connection. Bypassing RLS for the erasure path would make it the one component exempt from the isolation it enforces ([[CLAUDE|CLAUDE.md]] §16).
- `test_self_removal_is_blocked_by_the_step_09_select_policy` pins it as known behaviour. It is *expected to fail* when this is fixed, and that failure is the signal to delete it.

Fixing it means changing a STEP-09 SELECT policy — a Critical multi-tenancy decision of its own ([[CLAUDE|CLAUDE.md]] §21/§29), not something an RBAC step folds in silently. **It needs an owner decision and a step of its own; [[STEP-13 Auth Users Workspaces Endpoints]] cannot deliver member removal without it.**

### Validation

Run against a real PostgreSQL — a throwaway database on the development Supabase instance, created and dropped for the run, with the genuine `auth.uid()` rather than the CI shim. The development database was verified untouched afterwards (still `d7b95c1f4e08`, 8 policies). **96 passed, 0 failed**; lint, format and `mypy app` all clean.

### Deliberately not done

- **Membership management endpoints** — [[STEP-13 Auth Users Workspaces Endpoints]] owns them, and is blocked on the finding above for the removal half.
- **Hard deletion and the 30-day purge.** Erasure is soft-delete only; a scheduled purge on an audited service path is a later concern, stated rather than implied.
- **Cross-workspace or platform-level roles.** Default-forbidden, and an ADR if ever needed.

---

## Navigation

- **Previous:** [[STEP-10 Authentication Backend]]
- **Next:** [[STEP-12 API Conventions and Middleware]]
- **Parent:** [[Build Plan]]
