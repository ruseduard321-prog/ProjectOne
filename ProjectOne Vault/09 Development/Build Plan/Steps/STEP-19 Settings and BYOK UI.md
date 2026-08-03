---
title: STEP-19 Settings and BYOK UI
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-03
tags: [engineering, workflow, build-step, frontend,security,ai]
step_id: STEP-19
step_status: Not Started
detail_level: full
---

# STEP-19 — Settings and BYOK UI

**Status:** Not Started
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

## Navigation

- **Previous:** [[STEP-18 AI Cost Governance Controls]]
- **Next:** [[STEP-20 Projects Schema and Lifecycle]]
- **Parent:** [[Build Plan]]
