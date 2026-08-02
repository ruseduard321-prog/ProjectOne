---
title: STEP-17 AI Router and Provider Abstraction
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-02
tags: [engineering, workflow, build-step, ai,backend]
step_id: STEP-17
step_status: Not Started
detail_level: full
---

# STEP-17 — AI Router and Provider Abstraction

**Status:** Not Started
**Detail level:** full — expanded by [[STEP-16 Sign Up and Sign In UI]], per [[Execution Protocol]].

## Goal

The provider-agnostic AI Router: BYOK, provider selection, health monitoring, retries and fallback.

## Scope

Routing and abstraction only. Cost governance is STEP-18 and is a hard gate — no AI call reaches a real provider in production until it passes.

## Prerequisites

- [[STEP-16 Sign Up and Sign In UI]] — `Done`, owner-approved 2026-08-03
- [[STEP-12a Trusted Proxy and Per-User Rate Limiting]] — inserted 2026-08-03, runs first
- [[STEP-16a Developer Session Inspector]] — inserted 2026-08-03

## Required Documentation

- [[AI Architecture]]
- [[AI Providers]]
- [[CLAUDE|CLAUDE.md]] §15

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-16 Sign Up and Sign In UI]]:

- **The established backend layering is router → service → repository**, with dependency injection through `app/core/dependencies.py`. The AI Router is a *service* with *repositories* per provider; it is not a router in the HTTP sense, and the naming collision is worth avoiding in module names ([[CLAUDE|CLAUDE.md]] §12).
- **Errors are typed and translated centrally.** `app/core/security.py` defines the exception classes, `app/core/errors.py` owns the HTTP mapping in one table. A provider failure gets a new exception type and one entry in that table — never a `try/except` in a route ([[API Conventions]]).
- **Every error body is `{"detail", "request_id"}`.** A provider outage message reaching a user goes through that envelope like everything else.
- **Logging redacts structurally.** A filter on the log handler strips bearer tokens, `Authorization` values, passwords and API keys. **A BYOK provider key is exactly the kind of value that filter exists for** — confirm the redaction patterns cover provider key formats before the first key is logged anywhere, rather than after.
- **No secret is committed.** Provider keys follow [[Environment and Secrets]]; a BYOK key belongs to a workspace and is tenant data, so it is subject to RLS like everything else.
- **`packages/` is still empty.** If the provider abstraction is genuinely framework-agnostic it may belong there, but adding the first shared package is a structural decision — raise it rather than deciding it mid-step ([[CLAUDE|CLAUDE.md]] §8).

## Tasks

1. **Define the provider interface** — one abstraction every provider implements, covering the calls this release actually needs (chat completion at minimum, per [[STEP-23 AI Chat End to End]]). Model it on the capabilities in [[AI Providers]]; do not build for capabilities no scheduled step consumes.
2. **Implement at least two providers** against that interface. Two is the minimum that proves the abstraction is real — a single implementation always fits its own interface.
3. **Build the selection flow** from [[AI Providers]]: user preference → capability → availability → cost → selection. Selection must be *observable* — the decision and its reason are logged, because an unexplained provider choice is a black box ([[CLAUDE|CLAUDE.md]] §15).
4. **Implement retries with a hard ceiling and provider fallback.** Both are [[CLAUDE|CLAUDE.md]] §15a requirements, not enhancements: unbounded retry logic is forbidden anywhere AI spend is involved, and a critical workflow must survive one provider's outage.
5. **Add provider health tracking** so repeated failures take a provider out of rotation rather than being retried indefinitely.
6. **Store BYOK keys as tenant data** — workspace-scoped, RLS-protected in the same migration that creates the table ([[CLAUDE|CLAUDE.md]] §16), encrypted at rest, never returned to a client in full and never logged.
7. **Surface uncertainty honestly.** A failed or degraded call reports what happened; it never returns confident-sounding output over a silent fallback ([[CLAUDE|CLAUDE.md]] §15).

**Explicitly out of scope:** budget ceilings, circuit breakers, spend tracking and anomaly detection — all [[STEP-18 AI Cost Governance Controls]], which is a hard gate before any provider call reaches production. Also out of scope: the BYOK settings UI ([[STEP-19 Settings and BYOK UI]]) and chat itself ([[STEP-23 AI Chat End to End]]).

## Validation

- **Both providers satisfy the interface**, proven by the same test suite running against each rather than by two bespoke suites.
- **Fallback is observed, not assumed** — force the primary provider to fail and confirm the call completes through the secondary, with the switch logged.
- **The retry ceiling is enforced** — a permanently failing provider stops at the limit and does not retry indefinitely. Assert the exact call count.
- **Selection is reproducible and explained** — given the same inputs the same provider is chosen, and the reason is in the log.
- **A BYOK key never appears in a log or an API response**, verified by grepping captured output rather than by review.
- **The keys table has RLS in the migration that creates it**, and a cross-tenant read is proven blocked — following [[RLS Policy Pattern]], with the policies-removed check that STEP-09 established.
- **No provider key is committed**; `.env.example` gains placeholders only.
- Lint, type-check, tests and build pass for `apps/api` in CI.

## Definition of Done

A provider-agnostic AI Router exists with at least two working providers behind one interface; selection follows [[AI Providers]]' documented flow and logs its reasoning; retries are bounded by a hard ceiling and fallback is demonstrated against a forced failure; provider health is tracked; BYOK keys are stored as RLS-protected tenant data, encrypted, and proven absent from logs and responses; and no AI call path reaches production before [[STEP-18 AI Cost Governance Controls]] lands.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — AI/agent architecture, database schema, security controls, multi-tenancy). It carries an **owner approval gate**: [[STEP-18 AI Cost Governance Controls]] does not begin until the owner confirms this step.

> [!warning] Cost governance is a gate, not a follow-up
> [[CLAUDE|CLAUDE.md]] §15a is binding on every AI feature, and this step deliberately builds the machinery that *makes calls* before the machinery that *bounds them*. That ordering is only safe because nothing user-facing calls it yet. If any scheduled work would put a real provider call in front of a user before STEP-18 is `Done`, that is a plan problem to raise — not a risk to absorb.

---

## Navigation

- **Previous:** [[STEP-12a Trusted Proxy and Per-User Rate Limiting]]
- **Next:** [[STEP-18 AI Cost Governance Controls]]
- **Parent:** [[Build Plan]]
