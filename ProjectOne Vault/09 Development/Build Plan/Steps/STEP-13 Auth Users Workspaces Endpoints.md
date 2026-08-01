---
title: STEP-13 Auth, Users and Workspaces Endpoints
category: Development/Build Step
status: draft
version: "1.2"
last_updated: 2026-08-02
tags: [engineering, workflow, build-step, backend,api]
step_id: STEP-13
step_status: Done
detail_level: full
---

# STEP-13 — Auth, Users and Workspaces Endpoints

**Status:** Done
**Detail level:** full — expanded by [[STEP-12 API Conventions and Middleware]], per [[Execution Protocol]].

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

- **Some of these endpoints already exist and must be extended, not rebuilt.** `POST /auth/{sign-up,sign-in,sign-out,refresh}` and `GET /auth/me` are implemented ([[Authentication Implementation]]); `GET /workspaces` exists as a deliberately minimal read-only route. ~~This step brings them onto the STEP-12 conventions and~~ STEP-12 already brought them onto the conventions and onto the `/api/v1` prefix; this step documents them with [[API Endpoint Template]] — it does not write them from scratch.
- **The precedent for the audited path is already set.** `UserRepository.ensure_profile` performs exactly this shape of operation: an insert RLS forbids from a client, run over the privileged connection, confined to one narrow purpose and documented as to why. Workspace creation should follow that pattern rather than inventing a second one — and should be **audited**, which profile provisioning currently is not, because a tenant boundary being created is a more consequential event than a profile row appearing.
- **Two connections exist and the distinction is load-bearing.** `TenantConnectionDep` is RLS-subject and is the default for everything; the privileged connection is for the bootstrap operation only. A new endpoint reaching for the privileged connection because it is convenient silently loses tenant isolation.
- **Grants are narrow.** `authenticated` holds `SELECT`, `INSERT`, `UPDATE` only. An endpoint needing DELETE is a design error — removal is a soft delete.

Added by [[STEP-11 Authorization and RBAC]]:

Added by [[STEP-11a Membership Removal Policy]]:

- **Removal, departure and ownership transfer are built — this step only exposes them.** `MembershipService` implements the owner's five rules and the database enforces them independently ([[Authorization Model]]). The work here is HTTP routes over `remove_member`, `leave_workspace` and `transfer_ownership`, not re-deciding the rules.
- **`LastOwnerError` maps to 409, not 403**, and the handler already exists — in `app/core/errors.py` as of STEP-12, no longer in `app/main.py`. A route that catches it and returns 403 would tell an owner they lack a permission they hold.
- **Every query on `workspace_members` must filter `deleted_at IS NULL` explicitly.** The SELECT policy no longer does it — that is what made removal possible. A member listing that omits the filter shows removed members.
- **Inviting a member is still unsolved.** The INSERT policy requires the caller to already be a member of the target workspace, so adding someone needs the same audited service path as workspace creation.

- **Authorization is already built; endpoints declare it rather than implement it.** `requires(<permission>)` gates a route, `AuthorizationService` decides, and a single handler maps refusals to 403 ([[Authorization Model]]). A new endpoint writes a permission into its signature — it does not add an `if` to a handler, and it does not invent a second role check.
- **Every route taking a `workspace_id` must declare it as a path parameter.** `requires(...)` reads it from the URL by name, so a route that accepts a workspace id in the body cannot be authorized by it — deliberately, since a body-supplied id is the caller choosing their own permission check.
- **`GET /workspaces/{id}/permissions` already exists** and is what a client uses to render an interface matching what the server will allow. It is a convenience, never the enforcement.
- **Export and erasure endpoints exist structurally** (`GET /workspaces/{id}/export`, `DELETE /workspaces/{id}/data`). Any store this step adds registers in `REGISTERED_STORES` as part of its Definition of Done ([[CLAUDE|CLAUDE.md]] §16), or it is silently excluded from every export and erasure.

Added by [[STEP-12 API Conventions and Middleware]]:

- **Every route mounts under `/api/v1`, and no router hardcodes that string.** Routers declare their own prefix (`/workspaces`) and `app/main.py` mounts them under `API_PREFIX`. A new router that writes the version into its own prefix breaks v2 mounting before v2 exists.
- **Do not translate errors in a route.** Raise the typed exception; `app/core/errors.py` maps it. A `try/except` returning an `HTTPException` in a handler is the pattern STEP-12 removed, and re-adding it recreates the drift between two answers that a single handler exists to prevent.
- **The error envelope is `{"detail", "request_id"}`** and is produced centrally. An endpoint returning a bespoke error shape breaks the contract every client is written against.
- **Both identical-body properties are guarded by tests.** Any new endpoint taking a `workspace_id` must return the *same* 403 body whether the caller's role was insufficient or they were not a member — the existing `requires(...)` path does this automatically, and a hand-rolled check will not.
- **A new endpoint gets a rate limit only if it needs one**, and adding one is a line in `_RATE_LIMITS` in `app/main.py`, keyed by full path. Authenticated routes are unlimited by default ([[API Conventions]]).
- **[[API Endpoint Template]] was updated to match these conventions.** It now instructs the writer to document only what is endpoint-specific rather than restating the shared contract.
- **Audit logging is still not built**, and [[API Architecture]] requires it. Request logging records that a request happened, not who changed what. This step creates the first genuinely auditable mutations — workspace creation, membership changes, ownership transfer — so it is where the gap stops being theoretical. Decide explicitly whether audit logging lands here or in a step of its own; do not let it pass silently a second time.

## Tasks

1. **Build the audited workspace-creation path** (`POST /api/v1/workspaces`). The two-row bootstrap RLS forbids from a client — see the warning above. Follow `UserRepository.ensure_profile`'s shape: privileged connection, one narrow purpose, documented reasoning. Unlike profile provisioning, this one is **audited**, because a tenant boundary being created is a consequential event.
2. **Expose the membership operations** `MembershipService` already implements: remove a member, leave a workspace, transfer ownership. Routes only — the rules are built and enforced in the database ([[Authorization Model]]). `LastOwnerError` must surface as 409 without the route catching it.
3. **Build member invitation**, the one membership operation with no path at all: the INSERT policy requires the caller to already be a member of the target workspace. It needs the same audited service path as task 1. If it cannot be built without a decision the owner must make (invitation by email versus by existing user id, and whether an invited user is created before accepting), **stop and ask** rather than choosing ([[CLAUDE|CLAUDE.md]] §33–34).
4. **List a workspace's members** (`GET /api/v1/workspaces/{id}/members`). Every query must filter `deleted_at IS NULL` explicitly — the SELECT policy no longer does, and omitting it lists removed members.
5. **Decide and act on audit logging** — see the inherited note above. Either build it for the mutations in this step, or record the decision to defer it with the reason and the step that owns it.
6. **Document every endpoint** with [[API Endpoint Template]], including the ones STEP-10 and STEP-11 already built. An endpoint the frontend consumes from STEP-16 without a written contract is a contract that lives only in the code.
7. **Register any new data store** in `REGISTERED_STORES`, or it is silently excluded from every export and erasure ([[CLAUDE|CLAUDE.md]] §16).

## Validation

- Workspace creation works end to end and produces both rows; a client cannot achieve the same result by direct INSERT over the tenant connection.
- Each membership operation is exercised through HTTP, including the refusals: the last owner gets 409, a member removing someone else gets 403, and both 403 bodies are identical to the existing ones.
- Member listing omits soft-deleted members — asserted, since the policy no longer enforces it.
- Every new endpoint returns the standard envelope, and its errors carry a `request_id`.
- The STEP-09 through STEP-12 suites all still pass, run against a real PostgreSQL. New endpoints must not have widened access.
- Lint, format, type-check and the full suite pass in CI.

## Definition of Done

Every authentication, user and workspace operation the platform needs is reachable over HTTP, documented with [[API Endpoint Template]], built on the STEP-12 conventions rather than around them; workspace creation and invitation go through an audited service path rather than raw client INSERTs; and no endpoint introduces a second, weaker copy of a rule the database already enforces.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — public API contract, authorization, multi-tenancy): flag for owner review.

## Outcome

**Every workspace and membership operation is now reachable over HTTP**, and the first consequential mutations are audited. The endpoint contract is [[API Endpoints]]; the audit table is [[Table - audit_log]]. Neither is restated here.

### The owner's two decisions

Both were put to the project owner on 2026-08-01 before any code was written, per task 3's instruction to stop and ask:

- **Adding a member is by existing `user_id`, not by email.** An email-keyed endpoint reveals whether an address has a ProjectOne account unless every response is identical either way, and a full invitation flow is a larger scope than this step. Consequence stated rather than discovered: someone with no account cannot yet be added, and a real invitation flow is unscheduled.
- **Audit logging lands here, not in a later step.** This step creates the first auditable mutations, so deferring would ship them unaudited.

### A defect in the plan, found by probing rather than reading

The inherited notes said inviting a member was "still unsolved" and needed the privileged path, because the INSERT policy requires the caller to already be a member of the target workspace. **That conflated two different cases**, and the difference matters:

- **Adding a member is not blocked.** The policy tests the *caller's* membership, which an existing member has. Probed against a live database before designing anything: the insert succeeds over the ordinary tenant connection. Routing it through the privileged path would have discarded RLS for an operation that never needed it.
- **The bootstrap genuinely is blocked.** A creator's own first membership row has no prior membership to test against. Also probed: the `workspaces` row inserts fine, the membership row is refused. That is the only operation using the privileged connection, and `test_a_client_cannot_bootstrap_a_workspace_by_direct_insert` asserts the refusal permanently, so the day it stops being true the suite says so.

[[Authorization Model]] carried the incorrect claim and has been corrected.

### The audit log breaks two conventions on purpose

No `deleted_at`, no `version`, no `touch_row` trigger, and one SELECT-only policy. Those departures from [[Table Conventions]] are the security property: an audit record its own subject can edit or remove is not an audit record. Immutability rests on three independent mechanisms — absent policies, absent grants (`TRUNCATE` especially, which RLS does not govern), and writes confined to the privileged path so a client cannot forge entries.

It is **exportable but not erasable**, a documented [[CLAUDE|CLAUDE.md]] §16 legal exception rather than a gap in the erasure path. A workspace erasure reports `"audit_log": 0`, which discloses the exception instead of hiding it — an omitted store would be indistinguishable from a forgotten one.

### Defects found during validation

- **A partial unique index does not prevent a duplicate live membership.** `uq_workspace_members_active` only constrains rows where `deleted_at IS NULL`, so re-adding a previously-removed member with a plain INSERT leaves two rows for one person — one dead, one live — passing the constraint while corrupting every count and listing. Adding is therefore an explicit revive-then-insert in one transaction. `ON CONFLICT` cannot do it: an inference clause must match the index's predicate, and re-adding conflicts with nothing while the old row is still soft-deleted.
- **Test teardown could not delete workspaces.** `audit_log.workspace_id` is `RESTRICT`, deliberately — a trail must not be cascaded away with the thing it records — so the fixture has to clear audit rows first. Surfaced as 32 teardown errors that also caused two unrelated tests to fail on leftover state; both passed in isolation, which is what identified the real cause.
- **A cluster-wide role grant blocked the harness.** The STEP-12 run left `projectone_api` holding `USAGE` on `public` in the `postgres` database, so the migration's `DROP ROLE` failed. Residue on the shared development instance, not a code defect; revoked.

### Validation

Run against a real PostgreSQL — a throwaway database on the development Supabase instance, created and dropped for the run, with the genuine `auth.uid()`. **191 passed, 0 failed, 0 skipped** (up from 160), including the full STEP-09 through STEP-12 suites. `apps/web`: 7 passed. Lint, format and `mypy app` (strict) all clean. Migration `a3c07d5e91f4` was downgraded and re-upgraded to verify the rollback path.

Observed rather than assumed: workspace creation produces both rows and the creator can immediately see the result; a direct client bootstrap is refused by the database; an added member genuinely gains access and a removed one loses it immediately; the last owner gets 409 and the transfer-then-leave path the message recommends actually works; and a client acting as `authenticated` cannot insert, update, delete or truncate the audit log.

---

## Navigation

- **Previous:** [[STEP-12 API Conventions and Middleware]]
- **Next:** [[STEP-14 Design System Tokens]]
- **Parent:** [[Build Plan]]
