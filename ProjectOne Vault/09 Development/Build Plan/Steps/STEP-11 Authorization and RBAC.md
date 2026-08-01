---
title: STEP-11 Authorization and RBAC
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, security,backend]
step_id: STEP-11
step_status: Not Started
detail_level: full
---

# STEP-11 — Authorization and RBAC

**Status:** Not Started
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

---

## Navigation

- **Previous:** [[STEP-10 Authentication Backend]]
- **Next:** [[STEP-12 API Conventions and Middleware]]
- **Parent:** [[Build Plan]]
