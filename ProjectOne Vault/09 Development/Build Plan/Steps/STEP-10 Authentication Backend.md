---
title: STEP-10 Authentication Backend
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, security,backend]
step_id: STEP-10
step_status: Done
detail_level: full
---

# STEP-10 — Authentication Backend

**Status:** Done

> [!warning] Owner review required before STEP-11
> This is a **Critical change** ([[CLAUDE|CLAUDE.md]] §21 — authentication, security controls, multi-tenancy). Its Definition of Done is satisfied and it is committed, but [[Execution Protocol#Owner Approval Gates]] holds the queue: **[[STEP-11 Authorization and RBAC]] does not begin until the project owner confirms this step.** Silence is never approval.
>
> What to review: the choice of `projectone_api` over Supabase's `authenticator`; the two-connection split and the rule that nothing on the request path uses `DATABASE_URL`; transaction-scoped identity as the defence against pooled-connection claim leaks; the narrowed grants *and* the corrected default privileges; the application-side upsert linking `auth.users` to `public.users`; and the deliberate deferral of MFA and OAuth.
>
> Also confirm the CI run, as with STEP-06 and STEP-09: this environment cannot observe workflow results on a private repository.
**Detail level:** full — expanded by [[STEP-09 Row Level Security Policies]], per [[Execution Protocol]].

## Goal

Sign-up, sign-in, sign-out, session and token handling in `apps/api`, with identity reaching the RLS policies from STEP-09.

## Scope

Backend only — no UI. MFA and OAuth providers are in scope per [[Authentication and Authorization]]; decide during expansion whether they ship here or in a follow-on step.

## Prerequisites

- [[STEP-09 Row Level Security Policies]] — `Done`

## Required Documentation

- [[Authentication and Authorization]]
- [[Security Architecture]]
- [[Chapter 09 - Security Standards]]
- [[Table - users]] — specifically [[Table - users#Relationship to Supabase Auth]]

## Inherited from earlier steps

Recorded during synchronization, not expansion — these are constraints this step must resolve, not its task list.

> [!warning] Blocker to clear here: the Supabase REST API returns 401
> `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are configured and validated, but REST calls with the provided `sb_secret_...` key return 401 while direct PostgreSQL access works ([[STEP-07 Supabase Provisioning#Outcome]]). Nothing has used REST so far, so it has blocked nothing.
>
> **This step is the deadline.** Supabase Auth's admin API is HTTP, so the first real consumer of those two variables is almost certainly here. Resolve it before building on them — most likely the key must be enabled for the REST role in the dashboard, or a different key type is required.

Two schema facts from [[STEP-08 Users and Workspaces Schema]] that this step owns:

- **`public.users.id` holds the same value as `auth.users.id`, with no foreign key between them.** The link is a convention right now, enforced by nothing. This step decides how it is established on sign-up and how it is kept honest — a trigger on `auth.users`, an application-side upsert, or an explicit FK if the coupling to Supabase's schema is judged acceptable.
- **`public.users.email` is denormalized from `auth.users.email`.** This step owns keeping the copy in step with the authoritative value when a user changes their address.

> [!danger] The decision this step cannot avoid: which database role the API connects as
> Added by [[STEP-09 Row Level Security Policies]]. RLS now protects all three tables, but **`postgres` and `service_role` both carry `rolbypassrls` and ignore every policy**. `DATABASE_URL` currently connects as `postgres`.
>
> That is correct for Alembic and wrong for serving requests: an API that queries tenant tables over today's connection gets **no isolation at all**, silently, while every isolation test still passes. RLS is not "on" for the application until this is resolved.
>
> This step must establish a request-path connection that (a) uses a non-bypassing role, and (b) sets `request.jwt.claim.sub` per request so `auth.uid()` resolves — see [[RLS Policy Pattern#How Identity Reaches a Policy]]. Migrations keep using the privileged connection.

Also inherited from STEP-09:

- **Table grants are still Supabase's defaults** — `anon` and `authenticated` hold full DML on all three tables. Narrowing them was deferred to this step deliberately, because the right grants depend on which role the API uses.
- **A client cannot bootstrap a workspace.** The INSERT policies deliberately do not permit creating a workspace and its first membership row from outside, so that path needs an audited service ([[STEP-13 Auth Users Workspaces Endpoints]]). Sign-up creating a default workspace must account for this.

## Tasks

1. **Resolve the Supabase REST 401** before anything depends on it — see the warning above. Supabase Auth's admin API is HTTP, so this is the first step that genuinely needs those credentials to work.
2. **Decide and document the API's database role**, per the danger callout. This is the load-bearing decision of the step: record it in the vault with its reasoning, and treat it as Critical ([[CLAUDE|CLAUDE.md]] §21 — auth, security controls, multi-tenancy).
3. **Establish the request-scoped identity path**: set `request.jwt.claim.sub` from the verified JWT on each request so `auth.uid()` resolves inside the policies. Connection reuse makes this easy to get wrong — a claim leaking between pooled connections is a cross-tenant breach, so scope it to the transaction.
4. **Implement sign-up, sign-in, sign-out and session/token handling**, following router → service → repository ([[CLAUDE|CLAUDE.md]] §12). Token verification is business logic and belongs in a service, not in a router.
5. **Establish the `auth.users` ↔ `public.users` link** on sign-up, and keep `email` current when it changes upstream. Decide between a trigger, an application-side upsert, or an FK, and record why.
6. **Narrow the table grants** now that the API's role is known.
7. **Decide MFA and OAuth scope** — ship here or defer to a follow-on step, and say which in the Outcome.

## Validation

- A request carrying a valid token reads only its own workspace's rows **through the API**, not just through a psql session. This is the test that proves RLS is actually protecting the application.
- A request with no token, an expired token, or a tampered token is rejected — test all three.
- Two concurrent requests from different users over a reused connection do not see each other's data. This is the pooling leak in task 3, and it will not appear in a single-request test.
- The isolation tests from STEP-09 still pass.
- Sign-up creates exactly one `public.users` row whose `id` matches the `auth.users` identity.
- Lint, format, type-check and the full suite pass in CI.

## Definition of Done

A user can sign up, sign in and sign out through the API; requests carry a verified identity that reaches the RLS policies; the API connects as a role that does **not** bypass RLS; and the `auth.users` ↔ `public.users` link is established and documented.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — authentication, security controls, multi-tenancy): flag for owner review.

## Outcome

RLS now protects the **application**, not just the database. A request carrying a verified token reads only its own workspace's rows through the API, proven end to end against the live Supabase project.

| | Detail |
|---|---|
| Migrations | `c4f21a86b3de` (grants), `d7b95c1f4e08` (request role) — head |
| API role | `projectone_api` — `NOBYPASSRLS`, `NOSUPERUSER`, `NOINHERIT` |
| Token algorithm | `ES256`, verified via JWKS public key — no signing secret in the API |
| Endpoints | `POST /auth/{sign-up,sign-in,sign-out,refresh}`, `GET /auth/me`, `GET /workspaces` |
| Tests | 58 pass (was 25); 33 new across `test_token_service.py`, `test_request_session.py`, `test_auth_endpoints.py` |
| Documentation | [[Authentication Implementation]] (new) · [[RLS Policy Pattern]] · [[Schema Overview]] · [[Table - users]] · [[Environment Setup]] |

### The inherited blocker was a false alarm

STEP-07's REST 401 was a request-shape problem, not a broken key: the `sb_secret_...` format requires the key in **both** the `apikey` header and `Authorization: Bearer`. With both set, `/rest/v1/`, `/auth/v1/settings` and `/auth/v1/admin/users` all return 200. Nothing needed fixing in the dashboard.

### The role decision

**`projectone_api`**, created by `d7b95c1f4e08`. Supabase's `authenticator` was the obvious candidate and was rejected on two grounds: it is a reserved role that `postgres` cannot alter on managed Supabase (`ALTER ROLE authenticator WITH PASSWORD` fails — `postgres` is not a superuser there), and its definition belongs to the platform rather than to this project. Full reasoning in [[RLS Policy Pattern#The Two Connections]].

`NOINHERIT` is the attribute worth remembering: the role is granted `authenticated` but holds none of its privileges until it explicitly `SET ROLE`s, so a request path that skipped the role switch would read **nothing** rather than everything. The bug fails closed.

### Two defects found during validation

**1. The pooled-connection claim leak, reproduced before it was fixed.** A session-scoped `set_config(..., false)` left the JWT claim set after its transaction committed. A subsequent session with *no* claim then read the previous user's workspace — the exact cross-tenant breach task 3 warns about, observed on a live database. Resolved with `SET LOCAL ROLE` plus `set_config(..., true)`, both of which revert on commit *and* rollback (verified on both paths). `test_claim_does_not_leak_between_sessions` guards it; note that a single-request test cannot catch this, because the first request always looks correct.

**2. Revoking table grants was not enough — Supabase re-grants on every future table.** `ALTER DEFAULT PRIVILEGES ... GRANT ALL ON TABLES TO anon, authenticated` means each new table arrives with full DML including DELETE and TRUNCATE. Revoking only today's three tables would have left the next tenant table wide open to an unauthenticated role. This is the same class of defect STEP-09 found with `REVOKE ... FROM PUBLIC` failing on `anon` — Supabase grants **by name**. `c4f21a86b3de` corrects the default privileges too, and `test_future_tables_do_not_inherit_permissive_grants` creates a real table and inspects what it inherited.

### Decisions

- **`auth.users` ↔ `public.users` is linked by an application-side upsert**, not a trigger. A trigger would require creating an object on a Supabase-owned table in a Supabase-owned schema — the coupling the missing FK exists to avoid — and would live outside Alembic. Trade-off accepted and stated: an identity created in the dashboard has no profile row until it first authenticates, and `ON CONFLICT` makes that self-healing. See [[Table - users#Relationship to Supabase Auth]].
- **Email is reconciled on the same upsert**, guarded by `IS DISTINCT FROM` so an unchanged address writes nothing — otherwise every authenticated request would bump `version` and `updated_at` and make optimistic concurrency meaningless.
- **MFA and OAuth are deferred**, per task 7. The email/password path plus the RLS connection is already the Critical surface; adding two identity flows on top of an unreviewed foundation widens the blast radius of a mistake in it. The verification path is provider-agnostic — an OAuth-issued Supabase token verifies identically.
- **`GET /workspaces` is read-only and minimal.** It exists because the Validation section demands proof through the API rather than through psql. Workspace management is [[STEP-13 Auth Users Workspaces Endpoints]].
- **A STEP-09 test was updated, not weakened.** `test_delete_is_denied_on_every_table` asserted DELETE affects zero rows; with the grant revoked, PostgreSQL now raises instead. It accepts either gate and asserts what actually matters — the rows survive. Asserting the mechanism would make the test fail whenever the defence got stronger.

### Validation performed

12/12 end-to-end checks passed against the live development project, with throwaway identities cleaned up afterwards: isolation through the API for two users over a reused connection; rejection of absent, expired and tampered tokens; indistinguishable rejection bodies; `/auth/me`; upstream sign-out; and exactly one `public.users` row per auth identity. Migrations verified to roll back and re-apply cleanly. Lint, format and mypy `strict` clean; 58 tests pass.

### Known limitations

- **CI is unverified**, as with STEP-06 and STEP-09 — the build environment cannot observe workflow results on a private repository. Confirming the run is an owner action.
- **The e2e script created identities through the admin API**, not `/auth/sign-up`, because this project has email confirmation enabled with Supabase's rate-limited built-in SMTP. Sign-in — the path these checks exercise — went through the API. `/auth/sign-up`'s own behaviour is covered by `test_auth_endpoints.py`.
- **`projectone_api`'s password is set out of band** and must be re-set after any rollback past `d7b95c1f4e08`, which drops the role. Documented in [[Environment Setup]].

---

## Navigation

- **Previous:** [[STEP-09 Row Level Security Policies]]
- **Next:** [[STEP-11 Authorization and RBAC]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Authentication and Authorization]] · [[Security Architecture]] · [[RLS Policy Pattern]]
