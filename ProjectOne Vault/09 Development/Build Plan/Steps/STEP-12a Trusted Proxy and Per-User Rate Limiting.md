---
title: STEP-12a Trusted Proxy and Per-User Rate Limiting
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-03
tags: [engineering, workflow, build-step, security, backend, api, infrastructure]
step_id: STEP-12a
step_status: Not Started
detail_level: full
---

# STEP-12a — Trusted Proxy and Per-User Rate Limiting

**Status:** Not Started
**Detail level:** full — inserted after [[STEP-16 Sign Up and Sign In UI]] by owner decision on 2026-08-03.

## Why This Step Exists

[[STEP-16 Sign Up and Sign In UI]] recorded a regression in an existing control rather than resolving it:

> With every call proxied through Next.js, the API's rate limiter keys on the web server's address, so it no longer limits per user and one user can lock out others — observed directly.

This is not a cosmetic degradation. `RateLimitMiddleware._client_key()` returns `request.client.host`, which is now **always the Next.js server**. Every user therefore shares one bucket on every limited path. The sign-in limit of 10/minute is now a platform-wide limit of 10 sign-ins per minute across all users — a denial of service that any single user triggers accidentally, and any attacker triggers deliberately.

It is numbered `12a` because it amends the middleware contract [[STEP-12 API Conventions and Middleware]] established, not because it runs before STEP-17. **It executes after [[STEP-16a Developer Session Inspector]].**

## The Constraint That Shapes Everything

The existing implementation already documented the correct instinct, and this step must not discard it. From `middleware.py`:

> The peer address, never a header. `X-Forwarded-For` is caller-supplied and trivially spoofed, so counting against it would let an attacker reset their own allowance by changing one header — a rate limiter that the attacker controls.

That reasoning is right and stays right. **The fix is not to start trusting the header. It is to define precisely when the header is trustworthy** — which is only when it arrives from a peer that is itself trusted to have written it.

## Goal

Rate limiting that counts against the correct identity: the authenticated user where one exists, the real client IP where one does not — with the forwarded-header trust boundary explicit, configured, and documented.

## The Design

### 1. Two identity classes, one resolver

A single `RateLimitIdentity` resolver answers one question — *what does this request count against?* — with a namespaced key so the two classes can never collide:

| Request | Key | Reasoning |
|---|---|---|
| Authenticated | `user:<user_id>` | Independent bucket per user, per [[CLAUDE\|CLAUDE.md]] §14 |
| Unauthenticated | `ip:<trusted_client_ip>` | The only identity available before a credential exists |

Namespacing is not decoration: without it a user whose id happened to match an IP string would share a bucket with that address.

### 2. `user_id` comes from the validated auth context — never from the request

This is the load-bearing rule. The `user_id` used for limiting **must be the one produced by the same JWT verification the rest of the request relies on** (`app/core/security.py`, ES256 verified against JWKS). It is never read from a header, a body field, or an unverified claim.

That creates an **ordering problem the step must solve explicitly.** `RateLimitMiddleware` currently runs as middleware, which is *before* FastAPI's dependency resolution — so at the moment the limiter runs today, no verified identity exists. Three shapes are available and the step must choose deliberately:

- **(a) Verify the token inside the limiter.** Rejected on sight: it duplicates verification, doubles JWKS work, and creates two places where auth logic can drift apart.
- **(b) Move limiting out of middleware into a dependency** that runs after authentication. Limiting becomes declarative per-route, like `requires(<permission>)` already is ([[Authorization Model]]). Costs: unauthenticated paths still need a middleware-level limiter, so there are two mechanisms.
- **(c) Split by class.** Public paths stay in middleware keyed on trusted IP; authenticated paths are limited by a dependency keyed on `user_id`.

**(c) is the recommended shape**, and it is what (b) collapses into once its own caveat is taken seriously. It matches how the two classes genuinely differ: a public limit must refuse *before* any work happens, while an authenticated limit inherently cannot run until identity is established. The step implements (c) unless implementation finds a concrete reason it fails, in which case that reason is reported rather than worked around.

### 3. The trust boundary

`X-Forwarded-For` is accepted **only** when the immediate peer address (`request.client.host`) is in a configured allowlist of trusted proxies. Otherwise the header is ignored entirely and the peer address is used.

The parsing rule matters and is a common source of real vulnerabilities:

- `X-Forwarded-For` is a comma-separated list, appended to by each hop: `client, proxy1, proxy2`.
- **Never take the leftmost entry unconditionally** — it is fully attacker-controlled, since a client may send the header itself and honest proxies append rather than replace.
- **Walk the list right-to-left, discarding entries that are themselves trusted proxies. The first untrusted address found is the client.** If every entry is trusted, fall back to the peer address.
- The number of trusted hops is configuration, not a guess.

**Failure mode is closed, not open.** If the header is malformed, or trusted-proxy configuration is absent in an environment that requires it, the limiter falls back to the peer address and logs it. It never fails open by skipping the limit.

### 4. Deployment reality

The allowlist must express what real deployments need: Cloudflare's published ranges, an Nginx/Caddy sidecar on loopback, and the Next.js server itself. CIDR ranges are therefore required, not bare addresses.

Where a platform provides a **single-hop, non-appendable** header — Cloudflare's `CF-Connecting-IP` is the standard example — preferring it is legitimate, **but only under the same trust gate**: it is trustworthy solely because Cloudflare overwrites it, which holds only if the request genuinely came from Cloudflare. Treat it as an optional configured override, never as a default.

### 5. The proxy's obligation

`apps/web` currently forwards no client address (`src/lib/api.ts` sends `Accept`, `Content-Type` and `Authorization` only). For public endpoints to be limited by real client IP, the Next.js proxy must forward it — reading the client address from its own incoming request and setting the forwarded header on the outgoing call. Next.js is then itself a trusted proxy, and must be in the allowlist for the API to honour what it sends.

## Scope

`apps/api` middleware and dependencies, `apps/web` proxy forwarding, configuration in both, tests, and documentation. **The storage backend does not change** — see below.

## Explicitly Out of Scope

- **Redis or any shared rate-limit store.** The current limiter is in-process and per-worker, which STEP-12 documented as a deliberate, stated approximation. Moving to shared state is a new infrastructure dependency requiring its own ADR ([[CLAUDE|CLAUDE.md]] §10, §28). **This step fixes *what is counted*, not *where counts live*** — those are independent problems, and conflating them turns a security fix into an infrastructure project. The per-worker approximation must be re-stated in the documentation this step produces, because per-user keys make it *more* visible: N workers means N times the per-user allowance.
- **AI cost governance quotas.** [[CLAUDE|CLAUDE.md]] §15a budget ceilings are [[STEP-18 AI Cost Governance Controls]]. A per-user request limit and a per-workspace spend ceiling answer different questions.
- **Per-workspace limits.** The owner's requirement is per-user. Workspace-scoped limiting is a plausible future need and is not built speculatively (§29/§35).

## Prerequisites

- [[STEP-16a Developer Session Inspector]] — `Done`
- **An `Accepted` ADR on the trusted proxy boundary** — see Task 1. This is a hard gate: implementation may not begin while the ADR is `Draft` or `Review` ([[CLAUDE|CLAUDE.md]] §7).

## Required Documentation

- [[API Conventions]] — the contract this amends
- [[Security Architecture]] — trust boundary treatment
- [[Web Session Handling]] — what the proxy currently sends
- [[CLAUDE|CLAUDE.md]] §14 (API security), §16 (Zero Trust, untrusted input), §28a (environment configuration)

## Tasks

1. **Write an ADR** — *Trusted Proxy and Client Address Resolution*. It records: which headers are honoured and under what condition, the right-to-left parsing rule, the allowlist configuration format, the closed failure mode, per-environment expectations (local, staging, Cloudflare production), and the explicitly accepted residual risk. **Implementation stops here until the owner marks it `Accepted`.**

2. **Implement client address resolution** as a single tested unit, separate from the middleware that consumes it. It is pure logic — peer address plus headers plus configuration in, client address out — and it must be unit-testable without an HTTP request.

3. **Add configuration** for the trusted proxy allowlist (CIDR-aware) and the optional platform header override, through the existing STEP-05 settings system, with `.env.example` entries for both apps. No environment-conditional branching in code ([[CLAUDE|CLAUDE.md]] §28a) — behaviour changes by configuration value.

4. **Implement per-user limiting** for authenticated routes, keyed on the verified `user_id`, per the shape chosen in Design §2.

5. **Re-key public limiting** onto the resolved client address. The three existing rules (`sign-in`, `sign-up`, `refresh`) keep their current numbers — this step changes the key, not the policy — and **password reset and email confirmation gain rules when those endpoints exist**. They do not exist today; do not create endpoints to limit them.

6. **Forward the client address from `apps/web`**, and add the Next.js server to the API's trusted allowlist in every environment's configuration.

7. **Preserve the STEP-12 refusal contract** — the 429 keeps its envelope, its `Retry-After`, and its correlation id. The `rate_limit_exceeded` log line gains the identity **class** (`user` / `ip`); it must not log a raw client IP alongside a user id without checking that against [[Privacy and Data Protection]].

8. **Document the trust boundary** in [[API Conventions]], and record the deployment requirement in [[Infrastructure]]: **any reverse proxy placed in front of the API must be added to the allowlist, and must strip or overwrite inbound `X-Forwarded-For` from the internet rather than appending to it.**

## Validation

Every check observed, not assumed.

- **A spoofed `X-Forwarded-For` from an untrusted peer is ignored** — send a forged header directly to the API, confirm the limit counts against the peer address and the forged value never becomes the key. This is the security test; it must fail if the allowlist check is removed, in the manner STEP-09 established for RLS.
- **A forwarded address from a trusted peer is honoured** — same request from an allowlisted address is keyed on the forwarded client.
- **Right-to-left parsing is correct** against a multi-hop chain, including a chain where a client pre-seeded the header with a forged leftmost entry.
- **Two authenticated users have independent buckets** — exhaust one user's allowance, confirm the second is unaffected. This is the regression STEP-16 recorded, and this assertion is what proves it fixed.
- **Two users behind one proxy have independent buckets on public endpoints** — different client IPs, same proxy, separate allowances.
- **`user_id` cannot be influenced by the request** — a request carrying a header or body field naming another user is keyed on the verified token's subject regardless.
- **Malformed and absent headers fail closed** — limiting still applies, falling back to the peer address.
- **The 429 envelope, `Retry-After` and correlation id are unchanged**, proven by the existing STEP-12 tests still passing untouched.
- **`/health` is still never limited** — the existing test still passes.
- Lint, type-check, tests and build pass for both apps in CI.

## Definition of Done

Authenticated requests are limited per verified `user_id` with independent buckets; public requests are limited by a client address resolved only from trusted proxies using right-to-left parsing with a closed failure mode; the allowlist is configuration with CIDR support and `.env.example` entries; `apps/web` forwards the client address and is itself allowlisted; spoofing is proven ineffective by a test that fails when the check is removed; the STEP-12 refusal contract is unchanged; and the trust boundary is documented in [[API Conventions]] with the deployment requirement recorded in [[Infrastructure]].

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — security controls, public API contract, infrastructure configuration). It carries an **owner approval gate**, in addition to the ADR gate in Prerequisites.

> [!warning] Two gates, not one
> The ADR gate is *before* implementation; the owner approval gate is *after* completion. The first exists because the trust boundary is an architectural decision ([[CLAUDE|CLAUDE.md]] §7); the second because a rate limiter is a security control. Neither substitutes for the other.

---

## Navigation

- **Previous:** [[STEP-16a Developer Session Inspector]]
- **Next:** [[STEP-17 AI Router and Provider Abstraction]]
- **Parent:** [[Build Plan]]
