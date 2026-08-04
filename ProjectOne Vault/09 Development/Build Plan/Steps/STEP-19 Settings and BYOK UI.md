---
title: STEP-19 Settings and BYOK UI
category: Development/Build Step
status: draft
version: "2.1"
last_updated: 2026-08-04
tags: [engineering, workflow, build-step, frontend,security,ai]
step_id: STEP-19
step_status: Done
detail_level: full
---

# STEP-19 — Settings and BYOK UI

**Status:** Done
**Detail level:** full — expanded by [[STEP-18 AI Cost Governance Controls]], per [[Execution Protocol]].

## Goal

The first settings screens, and **the first HTTP routes that reach the AI layer at all**. Profile, Workspace, AI Providers (BYOK), and AI Spend — each backed by endpoints that follow [[API Conventions]] and a UI that follows [[Design System]].

## Scope

Billing, Notifications and Integrations sections are deferred to the steps that build those domains. Security settings reduce to what exists: sign-out is already built, and MFA remains deferred out of STEP-10.

> [!important] This step opens the door STEP-17 and STEP-18 built
> STEP-17 built the router with **no HTTP routes**; STEP-18 built the ceilings, also with none. This is where a real user first reaches a real provider. Every route added here is on the critical path for both tenant isolation and spend, so the review bar is the higher one.

## Prerequisites

- [[STEP-18 AI Cost Governance Controls]] — `Done`

## Required Documentation

- [[Settings]] — the product specification
- [[Design System]] — binding on every screen
- [[API Conventions]] — the envelope, the versioned prefix, rate limiting
- [[AI Cost Governance]] — what a budget screen may and may not expose
- [[AI Router Implementation]] — the BYOK model and where plaintext exists

**Reference only, not required reading:** [[Design Backlog and UI Vision]]. It is informational, binds nothing, and **must not** change what this step builds — screens are built against [[Design System]]. If implementing this step surfaces a concrete UI improvement traceable to that vision, record it in [[Design Backlog and UI Vision#UI Polish Backlog]] and carry on; acting on it during Foundation is out of scope ([[CLAUDE|CLAUDE.md]] §29, §35).

## Inherited from STEP-18

Recorded during expansion, while the context was loaded. These are the load-bearing facts, not a substitute for reading the notes.

- **`CredentialSummary` has no field capable of carrying a key.** A settings screen renders `provider` and `last_four` and structurally cannot leak more. Do not add a field to it "for the UI".
- **`ProviderCredentialService.key_for` is the only method producing plaintext.** No route may call it. A route that returns a stored key — even to the tenant that owns it — is a route that puts a credential in a browser, a proxy log and a user's clipboard history.
- **Writes require `owner`/`admin`; reads require membership.** Enforced by RLS on `provider_credentials` and `ai_budgets` alike, so the route's `requires(...)` dependency and the policy must agree — if they disagree, the policy is correct ([[RLS Policy Pattern]]).
- **Governance errors already have an HTTP mapping.** 402 for a budget or execution limit, 503 + `Retry-After` for a shutdown or tripped breaker, registered in `app/core/errors.py`. Routes raise; they do not map.
- **A budget PATCH must not accept `spent_usd`.** [[Table - ai_budgets]] records this as a known limitation: the UPDATE policy is per-row, so an owner can currently rewrite their own running total. The request schema is the control — accept `limit_usd` and `period_interval` and nothing else.
- **`AIRouter` is reachable only through `AIService`**, asserted by `test_no_route_can_reach_the_router_without_the_ai_service`. A new dependency that takes the router directly breaks that test, which is the point.
- **`AISpendRepository.read_records_for_workspace` takes a connection** rather than opening one, so a spend-history route cannot accidentally run privileged.

## Tasks

1. **Schemas** (`app/schemas/settings.py`, `app/schemas/ai.py`) — request and response models. `ProviderCredentialResponse` mirrors `CredentialSummary` exactly; `BudgetUpdateRequest` accepts `limit_usd` and `period_interval` only.
2. **Provider credential routes** — `GET /api/v1/workspaces/{id}/ai/providers` (summaries), `PUT .../providers/{provider}` (store, `owner`/`admin`), `DELETE .../providers/{provider}` (revoke, soft delete). Audited: storing or revoking a key that authorizes spend is a consequential action ([[Table - audit_log]]).
3. **Budget and spend routes** — `GET .../ai/budgets`, `PUT .../ai/budgets` (`owner`/`admin`), `GET .../ai/spend` (history over the tenant connection). Rate limited, per [[STEP-12a Trusted Proxy and Per-User Rate Limiting]]'s per-user scheme.
4. **Profile and workspace routes** — reuse what STEP-13 built where it exists; add only what the screens genuinely need.
5. **Settings shell** — `/settings` gains sections, following STEP-15's route group. Server Components by default; a Client Component only where a form genuinely needs one.
6. **BYOK entry UI** — a masked input, `last_four` display for an existing key, and an explicit "replace" affordance. **Never renders a stored key**, because none is retrievable.
7. **Budget UI** — current ceiling, spend against it, period, and an honest state when the breaker is open or a shutdown is active.
8. **Loading, empty and error states** for every screen ([[Design System]] §10, [[CLAUDE|CLAUDE.md]] §11) — polished skeletons, informative empties, actionable errors.

## Validation

- **A stored key is never returned by any route**, proven by grep against real responses rather than by reading the serializer — the STEP-16a standard.
- **A `member` cannot store, replace or revoke a provider key**, asserted through the HTTP layer, not only at the policy.
- **A `member` cannot change a budget**, and **can** read one — the asymmetry is deliberate and both halves need asserting.
- **`spent_usd` cannot be modified through the budget route**, proven by sending it and observing it ignored or rejected.
- **A cross-tenant request for another workspace's providers, budgets or spend returns 403 or an empty result**, never another tenant's data.
- **A tripped ceiling surfaces as 402 through a real route**, and a shutdown as 503 with `Retry-After`.
- **Negative control:** remove the `requires(...)` dependency from a write route and confirm the role tests fail.
- Lint, type-check, tests and build pass for both apps in CI.

## Definition of Done

Settings screens exist for Profile, Workspace, AI Providers and AI Spend, each with loading, empty and error states, each following the Design System. Their endpoints follow [[API Conventions]], enforce roles in both layers, and are audited where consequential. No route returns key material. A user can configure a provider key, see their spend against a ceiling, and understand a refusal when one occurs.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — public API contract, security controls, multi-tenancy, and the first user-facing AI path) and carries an **owner approval gate**.

---

## Outcome

**A user can now configure a provider key, set a spending ceiling, see what they have spent, and understand a refusal — and no route in the codebase can return a stored key.** Nine endpoints, four settings sections, two migrations, and two defects found by running the work rather than reviewing it.

### What was built

- **`app/routers/ai_settings.py`** — `GET/PUT/DELETE .../ai/providers`, `GET/PUT .../ai/budgets`, `GET .../ai/spend`. Members read; owners and admins write. Full contract in [[API Endpoints#AI settings — providers, budgets and spend]].
- **`PATCH /api/v1/auth/me`** — the one genuine profile gap. `email` is deliberately not editable: it is authoritative upstream and reconciled on every authenticated request, so a write here would silently revert.
- **Four settings sections** — Profile, Workspace, AI Providers, AI Spend — each with loading skeleton, empty state and a route-scoped error boundary that keeps the shell rather than replacing the page.
- **Migration `c9d3b71e08af`** — the column-level grant closing STEP-18's `spent_usd` exposure, plus three audit actions.
- **Migration `d1f70a4c62be`** — the revocation fix (see below).

### `spent_usd` is closed, by the mechanism RLS cannot provide

STEP-18 recorded honestly that an owner could zero their own running total, because a PostgreSQL policy is per-row and cannot restrict *columns*. A **column-level grant** can, and it is evaluated before any policy runs:

```sql
REVOKE UPDATE ON public.ai_budgets FROM authenticated;
GRANT UPDATE (limit_usd, period_interval) ON public.ai_budgets TO authenticated;
```

Three independent gates now stand on that value: `extra="forbid"` makes sending it a **422** rather than a silent discard, the handler never passes it on, and the grant refuses the write regardless of what any future route accepts. The third exists precisely because it is the one that holds when a route forgets.

Verified live, including a **negative control** that re-granted the column, reproduced the breach, and revoked it again — so the refusal is demonstrably the grant rather than something incidental. The `touch_row` trigger still increments `version`, because it runs as the table owner rather than as the caller.

### Two defects, both found by running it

**1. Revoking a provider key was impossible — for every role, including `owner`.**

`provider_credentials_select_same_workspace` filtered `deleted_at IS NULL`, and revocation is an `UPDATE` that *sets* `deleted_at`. PostgreSQL applies the SELECT policy to the resulting row, so the write was refused by the policy governing **reading**, with an error naming row-level security that points the reader at the UPDATE policy where nothing is wrong.

Established by narrowing against a live database rather than by inference:

| Statement | Result |
|---|---|
| `UPDATE ... SET last_four = '9999'` | **1 row** — the UPDATE policy passes |
| `UPDATE ... SET deleted_at = now()` | **refused** |
| the same, with `deleted_at` dropped from the SELECT policy | **1 row** |

**This is [[STEP-11a Membership Removal Policy]]'s defect, exactly, on a second table.** It recurred because [[RLS Policy Pattern]] recorded that fix as "a deliberate exception, and the only one" while still instructing every new table to filter `deleted_at` in each `USING` clause — so `provider_credentials` and the STEP-18 tables copied the broken shape from the instruction rather than the correction. That note now states the general rule and flags the four tables still carrying the latent version.

Worse than a broken button: **`ProviderCredentialStore.erase` had been silently failing since STEP-17**, so a workspace erasure left provider keys behind — a [[CLAUDE|CLAUDE.md]] §16 obligation broken with no test covering it, because nothing had ever revoked a key.

**2. Raising a ceiling silently reset the billing period.**

`upsert_budget` collapsed an unstated `period_interval` to a 30-day default and *wrote* it, so a budget configured with a 7-day period became a 30-day one the next time anyone changed the limit. `None` now means "leave it" on update (`COALESCE(%s, period_interval)`, one statement so the read and write share a row lock) and takes the default only on insert.

The failure was invisible from the response, which is what makes it worth a named regression test: the endpoint reported `period_days: 30` and was telling the truth about what had just been written.

### Validation

The pytest harness **cannot reach the development database**: `conftest.request_database_url` rebuilds the DSN with a bare `projectone_api` username, and the Supabase session pooler requires the `<role>.<project-ref>` suffix. Creating a scratch database on the same instance did not help — same pooler, same requirement. That harness is built for the direct-connection PostgreSQL CI provides, so **the 25 database-backed tests in `test_ai_settings_endpoints.py` will first execute in CI.**

Rather than mark that unverified, the same assertions were driven **in-process against the live development database** through a real `TestClient` using the application's own working DSNs:

- **37 HTTP-layer checks passed** — no key in any response body (including a 20-character prefix scan across list, export and audit), the role asymmetry in both directions, cross-tenant refusals, revocation, rotation, the `spent_usd` 422, the bounded spend limit, and a tripped breaker surfacing with its reason.
- **The negative control neutered the API's authorization gate** and confirmed the member is no longer refused 403 — while **RLS still refused the write independently**, which is the two-layer property asserted rather than assumed.
- **11 further checks** on the grant and the audit constraint, including the re-grant/revoke negative control.
- **6 checks** confirming the two inverted STEP-18 assertions and the period fix.
- Every probe removed its rows and **confirmed the database back to its prior contents by query**.

Offline: `apps/api` 325 passed, `apps/web` 97 passed (up from 74). Ruff, ruff-format, mypy `strict`, ESLint, `tsc --noEmit` and `next build` all clean. `/settings` builds as a dynamic route; `/dev/session` remains absent from the production build.

**A STEP-18 test asserted the old exposure** (`affected == 1`) and would have failed in CI. It is inverted rather than deleted, and its docstring records what changed and why.

### Decisions made

- **Workspace selection is "the caller's first workspace", resolved server-side.** The web application had no workspace concept at all before this step, and a switcher — persisted selection, a picker, workspace-carrying URLs — is a real feature belonging with [[STEP-20 Projects Schema and Lifecycle]] onward. The limitation is **disclosed on screen** ("You belong to N other workspaces — switching is not available yet") rather than left to be discovered. `GET /workspaces` orders by name, so "first" is stable across requests.
- **A stored key is never rendered, because none is retrievable.** The UI shows `••••••••1234` and an explicit **Replace** affordance rather than an always-present input — replacing a working credential is a deliberate act, and an open field invites a half-pasted value over a key that was working.
- **Sections with no backend are not rendered at all.** Billing, Notifications, Integrations, Connected Accounts and Storage are in [[Settings]] but have no step. A settings section that appears to save and does not is worse than one that is honestly absent.
- **Amounts cross every boundary as decimal strings**, never parsed to `number`. A cost displayed as `0.001234` matches the ledger it came from.

### Known gaps

- **No workspace switcher** — see above.
- **The four tables carrying the latent `deleted_at` policy defect** (`ai_budgets`, `ai_shutdown_switches`, `users`, `workspaces`) are recorded in [[RLS Policy Pattern]], not fixed. Each becomes live the moment a route soft-deletes that table.
- **A tripped spend breaker cannot be reset from the settings screen**, deliberately — it trips because something spent more than expected, which does not resolve by the tenant clearing it.
- **`test_ai_settings_endpoints.py` has not run locally.** CI is where it first executes.

---

## Navigation

- **Previous:** [[STEP-18 AI Cost Governance Controls]]
- **Next:** [[STEP-20 Projects Schema and Lifecycle]]
- **Parent:** [[Build Plan]]
