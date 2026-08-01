---
title: STEP-13 Auth, Users and Workspaces Endpoints
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, backend,api]
step_id: STEP-13
step_status: Not Started
detail_level: outline
---

# STEP-13 — Auth, Users and Workspaces Endpoints

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-12 API Conventions and Middleware]], per [[Execution Protocol]].

## Goal

The first real REST endpoints — authentication, user and workspace operations — built on the STEP-12 conventions.

## Scope

Each endpoint documented with [[API Endpoint Template]]. This is the contract the frontend consumes from STEP-16 onward.

## Prerequisites

- [[STEP-12 API Conventions and Middleware]] — `Done`

## Required Documentation

- [[API Architecture]]
- [[API Endpoint Template]]
- [[RLS Policy Pattern]] — what the database permits a client to do directly
- [[CLAUDE|CLAUDE.md]] §12/§14

## Inherited from earlier steps

Recorded during synchronization, not expansion.

> [!warning] Workspace creation cannot be a plain INSERT
> [[STEP-09 Row Level Security Policies]] made this structural. Creating a workspace requires two rows — the `workspaces` row and the creator's first `workspace_members` row — and the membership INSERT policy requires the caller to *already* be a member of that workspace. The creator is not, because the workspace did not exist a statement ago.
>
> This is deliberate, not an oversight: it forces workspace creation through an audited service path rather than letting a client assemble a tenant boundary row by row. **This step owns building that path.** Expect it to need a privileged, explicitly audited operation rather than the ordinary request-scoped connection — and see [[RLS Policy Pattern#What RLS Cannot Enforce]] before reaching for the service key, because using it casually would defeat every policy at once.

Added by [[STEP-10 Authentication Backend]]:

- **Some of these endpoints already exist and must be extended, not rebuilt.** `POST /auth/{sign-up,sign-in,sign-out,refresh}` and `GET /auth/me` are implemented ([[Authentication Implementation]]); `GET /workspaces` exists as a deliberately minimal read-only route. This step brings them onto the STEP-12 conventions and documents them with [[API Endpoint Template]] — it does not write them from scratch.
- **The precedent for the audited path is already set.** `UserRepository.ensure_profile` performs exactly this shape of operation: an insert RLS forbids from a client, run over the privileged connection, confined to one narrow purpose and documented as to why. Workspace creation should follow that pattern rather than inventing a second one — and should be **audited**, which profile provisioning currently is not, because a tenant boundary being created is a more consequential event than a profile row appearing.
- **Two connections exist and the distinction is load-bearing.** `TenantConnectionDep` is RLS-subject and is the default for everything; the privileged connection is for the bootstrap operation only. A new endpoint reaching for the privileged connection because it is convenient silently loses tenant isolation.
- **Grants are narrow.** `authenticated` holds `SELECT`, `INSERT`, `UPDATE` only. An endpoint needing DELETE is a design error — removal is a soft delete.

Added by [[STEP-11 Authorization and RBAC]]:

Added by [[STEP-11a Membership Removal Policy]]:

- **Removal, departure and ownership transfer are built — this step only exposes them.** `MembershipService` implements the owner's five rules and the database enforces them independently ([[Authorization Model]]). The work here is HTTP routes over `remove_member`, `leave_workspace` and `transfer_ownership`, not re-deciding the rules.
- **`LastOwnerError` maps to 409, not 403**, and the handler already exists in `app/main.py`. A route that catches it and returns 403 would tell an owner they lack a permission they hold.
- **Every query on `workspace_members` must filter `deleted_at IS NULL` explicitly.** The SELECT policy no longer does it — that is what made removal possible. A member listing that omits the filter shows removed members.
- **Inviting a member is still unsolved.** The INSERT policy requires the caller to already be a member of the target workspace, so adding someone needs the same audited service path as workspace creation.

- **Authorization is already built; endpoints declare it rather than implement it.** `requires(<permission>)` gates a route, `AuthorizationService` decides, and a single handler maps refusals to 403 ([[Authorization Model]]). A new endpoint writes a permission into its signature — it does not add an `if` to a handler, and it does not invent a second role check.
- **Every route taking a `workspace_id` must declare it as a path parameter.** `requires(...)` reads it from the URL by name, so a route that accepts a workspace id in the body cannot be authorized by it — deliberately, since a body-supplied id is the caller choosing their own permission check.
- **`GET /workspaces/{id}/permissions` already exists** and is what a client uses to render an interface matching what the server will allow. It is a convenience, never the enforcement.
- **Export and erasure endpoints exist structurally** (`GET /workspaces/{id}/export`, `DELETE /workspaces/{id}/data`). Any store this step adds registers in `REGISTERED_STORES` as part of its Definition of Done ([[CLAUDE|CLAUDE.md]] §16), or it is silently excluded from every export and erasure.

## Tasks

Not yet expanded. [[STEP-12 API Conventions and Middleware]] writes this section, when the surrounding code exists and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-12 API Conventions and Middleware]]
- **Next:** [[STEP-14 Design System Tokens]]
- **Parent:** [[Build Plan]]
