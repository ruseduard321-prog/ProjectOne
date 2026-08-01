---
title: STEP-10 Authentication Backend
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, security,backend]
step_id: STEP-10
step_status: Not Started
detail_level: full
---

# STEP-10 — Authentication Backend

**Status:** Not Started
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

---

## Navigation

- **Previous:** [[STEP-09 Row Level Security Policies]]
- **Next:** [[STEP-11 Authorization and RBAC]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Authentication and Authorization]] · [[Security Architecture]] · [[RLS Policy Pattern]]
