---
title: Build Plan
category: Development
status: stable
version: "2.1"
last_updated: 2026-08-01
tags: [engineering, documentation, workflow]
aliases: ["Implementation Plan", "Build Roadmap", "Step Index"]
---

# ProjectOne Build Plan

The ordered execution index taking ProjectOne from an empty repository to first public release. **26 sequential steps**, each sized for a single Claude Code session.

This note is an **index, not a plan** — it holds only ID, title and status. Step detail lives in one note per step under `Steps/`, so a session reads this index plus exactly one step file, and beyond that only what [[Execution Protocol#Context Discipline]] permits.

**To execute:** say *"Implement the next step."* Claude follows [[Execution Protocol]] — no other instruction needed.

## Status Legend

| Status | Meaning |
|---|---|
| `Not Started` | Untouched. |
| `In Progress` | Claimed by the current session. Set before implementing, never left behind at session end. |
| `Done` | Every [[Execution Protocol#Step Completion]] condition met — Definition of Done satisfied, validation passed, docs updated, status synchronized, no unresolved Critical issues. |
| `Blocked` | Cannot proceed without a named unblocker, or failed validation. Rolled back where safe, reported as-is where rollback is unsafe. **Never committed** without explicit user approval ([[Execution Protocol#Blocked Steps Are Never Committed]]), so a blocked step leaves a dirty working tree by design. **Holds the queue** — the next step does not start ([[Execution Protocol#Validation Failure and Rollback]]). |

Status appears in two places — the step note and the row below — and they must always agree.

**Detail levels:** steps are written at full detail only when they become imminent. Steps still marked `outline` in the Detail column hold goal and scope only — they are expanded into full executable detail by the step immediately preceding them, per [[Execution Protocol]]. This is deliberate: detailed plans for work three months out are fiction, and [[CLAUDE|CLAUDE.md]] §29/§35 forbid speculative over-design.

## Steps

| ID | Title | Status | Detail |
|---|---|---|---|
| STEP-01 | [[STEP-01 Repository Bootstrap]] | Done | full |
| STEP-02 | [[STEP-02 Stack Confirmation ADR]] | Done | full |
| STEP-03 | [[STEP-03 Web App Skeleton]] | Done | full |
| STEP-04 | [[STEP-04 API App Skeleton]] | Done | full |
| STEP-05 | [[STEP-05 Environment and Secrets]] | Done | full |
| STEP-06 | [[STEP-06 Continuous Integration]] | Done | full |
| STEP-07 | [[STEP-07 Supabase Provisioning]] | Done | full |
| STEP-08 | [[STEP-08 Users and Workspaces Schema]] | Done | full |
| STEP-09 | [[STEP-09 Row Level Security Policies]] | Done | full |
| STEP-10 | [[STEP-10 Authentication Backend]] | Done | full |
| STEP-11 | [[STEP-11 Authorization and RBAC]] | Done | full |
| STEP-11a | [[STEP-11a Membership Removal Policy]] | Done | full |
| STEP-12 | [[STEP-12 API Conventions and Middleware]] | Done | full |
| STEP-13 | [[STEP-13 Auth Users Workspaces Endpoints]] | Done | full |
| STEP-14 | [[STEP-14 Design System Tokens]] | Not Started | full |
| STEP-15 | [[STEP-15 App Shell and Routing]] | Not Started | outline |
| STEP-16 | [[STEP-16 Sign Up and Sign In UI]] | Not Started | outline |
| STEP-17 | [[STEP-17 AI Router and Provider Abstraction]] | Not Started | outline |
| STEP-18 | [[STEP-18 AI Cost Governance Controls]] | Not Started | outline |
| STEP-19 | [[STEP-19 Settings and BYOK UI]] | Not Started | outline |
| STEP-20 | [[STEP-20 Projects Schema and Lifecycle]] | Not Started | outline |
| STEP-21 | [[STEP-21 Projects UI]] | Not Started | outline |
| STEP-22 | [[STEP-22 Minimum Workflow Engine]] | Not Started | outline |
| STEP-23 | [[STEP-23 AI Chat End to End]] | Not Started | outline |
| STEP-24 | [[STEP-24 Dashboard]] | Not Started | outline |
| STEP-25 | [[STEP-25 Launch Readiness Criteria]] | Not Started | outline |
| STEP-26 | [[STEP-26 First Public Release]] | Not Started | outline |

## Scope Boundary

These 26 steps deliver the **first public release** — the Foundation loop (sign up → workspace → project → AI chat → dashboard) hardened, billed for, and shipped. Everything the [[Roadmap]] places in Phase 2 (Video Generation, Analytics, advanced agents, publishing) and Phase 3 (teams, enterprise, marketplace) is **out of scope for this plan** and gets its own step sequence once STEP-26 is Done.

One consequence is worth stating plainly rather than discovering at STEP-25: **[[Billing]] is not in these 26 steps.** A public release that charges money needs it; a free/invite-only public beta does not. STEP-25 resolves which of those this release is, and inserts billing steps if required — see that step's note.

## Source Documents

This plan is derived from, and must stay consistent with, the vault. If this plan and a source document disagree, **the source document wins** — update the plan, not the source. Individual steps name their own required reading; the full corpus is:

- [[Roadmap]] · [[Release Strategy]] · [[Deployment Strategy]] · [[Testing Strategy]] — delivery
- [[Product Bible]] and `03 Project Bible/01 Features/` — feature specifications
- [[AI Architecture]] · [[Agent Architecture]] · [[Memory System]] · [[AI Providers]] · [[Workflow Engine]] — AI systems
- [[Backend Architecture]] · [[Database Architecture]] · [[API Architecture]] · [[Frontend Architecture]] · [[Infrastructure]] — tech architecture
- [[Security Architecture]] · [[Authentication and Authorization]] · [[Privacy and Data Protection]] · [[Compliance and Governance]] — security & trust
- [[Design System]] — the UI standard every screen follows
- Engineering Handbook Chapters 1–11 — binding build standards
- [[CLAUDE|CLAUDE.md]] — operating rules governing every step

## Current State

As of 2026-07-31, the project root is a git repository on branch `main` with the canonical skeleton (`apps/`, `packages/`, `infrastructure/`, `docs/`, `scripts/`, `.github/`) in place.

**Both applications now exist as skeletons.** `apps/web` is a Next.js 16.2.12 / React 19 / TypeScript-strict / Tailwind v4 skeleton with `/` and `/health` routes, building clean and serving zero client JavaScript (STEP-03). `apps/api` is a FastAPI 0.121.2 / Python 3.14.6 skeleton with the five layer directories in place and a `/health` endpoint served through a router→service path, clean under Ruff and mypy `strict` (STEP-04). Neither talks to the other yet, and neither has a database, auth or features. `packages/` and `infrastructure/` remain empty placeholders.

**Both apps now validate their configuration at startup and refuse to run without it** (STEP-05). `.env.example` templates are committed for both; real `.env` files are ignored. No secret exists in the repository yet — the first arrives with STEP-07. Conventions are documented in [[Environment and Secrets]], **approved by the project owner on 2026-07-31** as a Critical change; that owner approval gate is cleared and STEP-06 onward may proceed.

**A GitHub remote now exists** at `github.com/ruseduard321-prog/ProjectOne` (private), and all six commits are pushed. CI is committed and triggered: every push and pull request runs lint, type-check, tests and build for both apps. `apps/web` gained a Vitest runner and its first 7 tests.

**CI is live and green** — the project owner confirmed both jobs succeeded on 2026-07-31, closing STEP-06 (see [[STEP-06 Continuous Integration#Outcome]]). Note that confirming a CI run is an owner action for now: the build environment cannot observe workflow results on a private repository.

**A database exists** (STEP-07). A development Supabase project (PostgreSQL 17.6) is connected through the STEP-05 config system, Alembic applies and rolls back migrations via `scripts/migrate.{sh,ps1}`, and `/health` is now a **readiness** check reporting real database connectivity — 503 when it is unreachable. No application tables yet; the first schema is STEP-08.

**STEP-07 was approved by the project owner on 2026-08-01**, clearing its owner approval gate (Critical — database/infrastructure).

**The first application tables exist** (STEP-08): `users`, `workspaces` and `workspace_members`, created by migration `8a6f39b07c12`. They carry the standard column set every later table inherits — `id uuid`, `created_at`, `updated_at`, `deleted_at`, `version` — with `updated_at` and `version` maintained by a database trigger. Constraints enforce integrity at the database layer and were each verified by observing a rejection. Documented in [[Schema Overview]] and [[Table Conventions]].

**STEP-08 was approved by the project owner on 2026-08-01**, clearing its owner approval gate (Critical — database schema).

**Workspace isolation is now enforced at the database layer** (STEP-09). Migration `860a798d204b` enables *and forces* RLS on all three tables, adds eight per-command policies scoped `TO authenticated`, and installs `app_current_user_workspaces()` — a locked-down `SECURITY DEFINER` helper that exists because a policy on `workspace_members` cannot query `workspace_members` without recursing. Identity reaches the policies through `auth.uid()`, which returns NULL without a JWT claim, so every policy denies by default. The pattern every future tenant table copies is [[RLS Policy Pattern]].

17 isolation tests prove cross-tenant read, update and delete are all blocked, and **15 of them fail when the policies are removed** — verified, because an isolation test that passes with RLS off is testing nothing. CI gained a throwaway PostgreSQL service container to run them, plus a flag making a missing test database a hard failure rather than a silent skip.

**STEP-09 was approved by the project owner on 2026-08-01**, clearing its owner approval gate (Critical — security controls, multi-tenancy/RLS), with CI confirmed green.

**RLS now protects the application, not just the database** (STEP-10). The API authenticates requests against Supabase Auth, verifies `ES256` access tokens against the project's JWKS public key, and serves every request over a second connection as `projectone_api` — a role created by migration `d7b95c1f4e08` that does **not** carry `rolbypassrls`. Identity reaches the policies through `SET LOCAL ROLE authenticated` plus a transaction-scoped `request.jwt.claim.sub`, so `auth.uid()` resolves and the claim cannot outlive the request on a pooled connection.

Migration `c4f21a86b3de` narrowed table grants to `SELECT`/`INSERT`/`UPDATE` for `authenticated` and nothing for `anon`, and corrected the schema's default privileges so future tables inherit the same rather than Supabase's permissive `GRANT ALL`. `POST /auth/{sign-up,sign-in,sign-out,refresh}`, `GET /auth/me` and a minimal `GET /workspaces` exist; the suite grew from 25 tests to 58. Documented in [[Authentication Implementation]].

Two defects were found and fixed during validation, both reproduced against a live database before being resolved: a **pooled-connection claim leak** (a session-scoped claim survived its transaction and the next session read the previous user's workspace), and **Supabase's default privileges re-granting full DML on every future table**, which would have left the next tenant table open to `anon`. See [[STEP-10 Authentication Backend#Outcome]].

The inherited STEP-07 REST 401 turned out to be a request-shape problem, not a broken key — the `sb_secret_...` key must be sent in both the `apikey` header and `Authorization: Bearer`.

**MFA and OAuth were deliberately deferred** out of STEP-10, and remain unscheduled — see that step's Outcome for the reasoning.

**STEP-10 was approved by the project owner on 2026-08-01**, with CI confirmed green, clearing its owner approval gate (Critical — authentication, security controls, multi-tenancy).

**Roles are now enforced, in both layers** (STEP-11). Migration `9f4d2c7a1b83` makes the two UPDATE policies role-aware — a plain `member` could previously rename the workspace and rewrite anyone's role row exactly like its owner — and installs `app_current_user_workspaces_as(text[])`, the role-filtered sibling of STEP-09's helper. Above the database, `requires(<permission>)` gates a route declaratively, `AuthorizationService` makes the decision from a per-request membership lookup, and one exception handler maps refusals to **403** rather than conflating them with 401. The role model, the two-layer split and the invalidation window are [[Authorization Model]]; the structural basis for data export and erasure ships with it. The suite grew from 58 tests to 96.

Three defects were found during validation, each reproduced against a live database: **`migrations/env.py` discarded the test harness's database URL** (so a test run migrated whatever `DATABASE_URL` pointed at — invisible in CI, a live-database hazard on a developer machine), a **branched migration history**, and an **own-row `WITH CHECK` that rejected the very operation it was written for**. All three are fixed.

**STEP-11 was approved by the project owner on 2026-08-01**, with CI confirmed green, clearing its owner approval gate (Critical — authorization, security controls, multi-tenancy).

**Membership removal now works, governed by explicit rules** (STEP-11a — a step inserted by owner decision on 2026-08-01, since the fix was a Critical multi-tenancy change rather than an API convention). STEP-11 had found that soft-deleting a `workspace_members` row was impossible for *every* role including `owner`. Migration `b8e1d94c50a7` resolves it and encodes the owner's five rules: the last owner may never leave or be removed, removal is strictly ranked owner > admin > member, a member may only leave themselves, and an owner may transfer ownership before leaving.

Two mechanisms carry it. The `deleted_at` filter **moved out of the SELECT policy into the queries** — a policy answers "whose rows may this caller touch", which is a tenant question `deleted_at` has nothing to do with — and the last-owner rule became a **deferrable constraint trigger**, because it counts remaining owners and no RLS predicate can do that without recursing. Tenant isolation is provably unchanged: `app_current_user_workspaces()` still filters the caller's own membership, so a removed member still loses access immediately, and a test proves the widening stopped at the workspace boundary. The suite grew from 96 tests to 133.

**STEP-11a was approved by the project owner on 2026-08-01**, with CI confirmed green, clearing its owner approval gate (Critical — authorization, security controls, multi-tenancy/RLS).

**Every endpoint now shares one API contract** (STEP-12). Routes moved onto a `/api/v1` URL prefix — migrated, not duplicated, so the unversioned paths return 404 — with `/health` deliberately left unversioned as infrastructure. One error envelope (`{"detail", "request_id"}`) covers 401, 403, 409, 422, 404 and 500, and translation moved out of the routers entirely into a handler table in `app/core/errors.py`, finishing what STEP-11 started. Every request carries a correlation id, echoed in the `X-Request-ID` header and in every error body, and the auth endpoints are rate limited. The decisions and their reasoning are [[API Conventions]]; the suite grew from 133 tests to 160.

The rule that no credential reaches a log became **structural rather than conventional**: a redacting filter on the log handler strips bearer tokens, `Authorization` values, passwords and API keys from every record, including ones emitted by `httpx` and `uvicorn`. The reasoning is that "do not log the header" holds until someone debugging logs the headers, and that failure is silent and permanent.

Two defects were found by running the tests: **a fixture that silently disabled authentication** (overriding `get_tenant_connection` replaces `get_current_user` beneath it, so four rejection tests were passing against an app checking nothing), and **errors bypassing the envelope** when they never reached a handler — Starlette's 404 and the limiter's own 429. Both are fixed; see [[STEP-12 API Conventions and Middleware#Outcome]].

Two things [[API Architecture]] requires are explicitly **not** built yet and are recorded rather than forgotten: **audit logging** (request logging is not audit logging) and **idempotency keys** (nothing yet creates a resource from a client-supplied request). Both are named in STEP-13's inherited notes.

**STEP-12 was approved by the project owner on 2026-08-01**, with CI confirmed green, clearing its owner approval gate (Critical — public API contract, security controls). The in-process rate limiting and the deferral of audit logging to STEP-13 were approved alongside it.

**Every workspace and membership operation is now reachable over HTTP, and the consequential ones are audited** (STEP-13). Creation, member listing and addition, removal, departure, ownership transfer and the audit trail join the endpoints STEP-10 and STEP-11 built; the full contract is [[API Endpoints]]. Migration `a3c07d5e91f4` adds `audit_log` ([[Table - audit_log]]) — append-only, RLS-scoped to the workspace, with immutability resting on absent policies, absent grants (`TRUNCATE` especially, which RLS does not govern) and writes confined to the privileged path so a client cannot forge entries. It is exportable but **not** erasable, a documented [[CLAUDE|CLAUDE.md]] §16 retention exception that a workspace erasure discloses as `"audit_log": 0` rather than hiding. The suite grew from 160 tests to 191.

**The project owner made two decisions on 2026-08-01**, both asked before any code was written: members are added by existing `user_id` rather than by email (an email-keyed endpoint is an account-enumeration oracle unless every response is identical, and a full invitation flow is a larger scope), and audit logging lands in this step rather than a later one. **Inviting someone with no ProjectOne account remains unbuilt and unscheduled.**

**A defect in the plan itself was found by probing the database before designing.** The inherited notes recorded member invitation as "unsolved, needs the privileged path". That conflated two cases: the INSERT policy tests the *caller's* membership, so an existing member adding someone else is permitted over the ordinary tenant connection — verified against a live database. Only the bootstrap (a creator's own first membership row) is genuinely refused, and it is the sole operation using the privileged connection. Routing invitation through that path would have discarded RLS for an operation that never needed it. [[Authorization Model]] carried the incorrect claim and is corrected.

Three defects were found during validation: **a partial unique index does not prevent a duplicate live membership** (re-adding a removed member with a plain INSERT leaves one dead and one live row, passing the constraint while corrupting every count), **audit rows blocked test teardown** because `audit_log.workspace_id` is deliberately `RESTRICT`, and **a cluster-wide role grant left by the STEP-12 run** blocked the harness. All three are fixed; see [[STEP-13 Auth Users Workspaces Endpoints#Outcome]].

Two gaps are recorded rather than forgotten: **audit retention is unbounded** (no purge schedule — needs a decision by [[STEP-25 Launch Readiness Criteria]]), and **authentication events are not audited** — sign-in, sign-out and failed attempts are arguably the most security-relevant events of all. **Idempotency keys** remain unbuilt, and `POST /workspaces` is now the first endpoint that could use them.

**STEP-13 carries an owner approval gate** (Critical — public API contract, authorization, multi-tenancy, database schema). It is `Done` and committed, but STEP-14 does not begin until the owner confirms it — including confirming the CI run, which this environment cannot observe on a private repository.

> [!warning] STEP-14 needs owner input before implementation, not only approval to start
> [[Design System]] is still `status: draft` at v0.1 and states **principles, not values** — "a modern sans-serif typeface", "one primary accent color", "consistent grid" — with no typeface, no hex codes and no base spacing unit. A token layer *is* the concrete values, so [[STEP-14 Design System Tokens]] cannot be implemented from the document as written, and inventing a brand palette would propagate into every screen built afterwards. Its task 1 is resolving those choices with the project owner and recording them in [[Design System]]. Flagged here so it is known before the session starts rather than discovered inside it.

The vault, Claude OS and AI operating capabilities are built and validated ([[Environment Setup]], [[AI Index]]).

Every Project Bible note is still `status: draft` at v0.1 — the *specification* is transcribed, not accepted. Treat drafts as the best current source of truth and flag genuine ambiguity per [[CLAUDE|CLAUDE.md]] §33 rather than resolving it silently mid-step.

[[ADR-001 Technology Stack]] is the first and only ADR, written by STEP-02 and `Accepted` by the project owner on 2026-07-31. Its owner approval gate is cleared, so the stack is settled and STEP-03 onward may proceed ([[CLAUDE|CLAUDE.md]] §7).

---

## Navigation

- **Previous:** —
- **Next:** [[Execution Protocol]]
- **Parent:** [[Development MOC]]
- **Related Notes:** [[Execution Protocol]] · [[Roadmap]] · [[Task Workflow]] · [[CLAUDE|CLAUDE.md]]
