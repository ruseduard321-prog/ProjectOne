---
title: STEP-12a Trusted Proxy and Per-User Rate Limiting
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-03
tags: [engineering, workflow, build-step, security, backend, api, infrastructure]
step_id: STEP-12a
step_status: Done
detail_level: full
---

# STEP-12a — Trusted Proxy and Per-User Rate Limiting

**Status:** Done

**ADR gate cleared:** [[ADR-002 Trusted Proxy and Client Address Resolution]] was marked `Accepted` by the project owner on 2026-08-03, unblocking Tasks 2–8 ([[CLAUDE|CLAUDE.md]] §7). All eight tasks are complete and validated — see [[#Outcome]].
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

- [[STEP-16 Sign Up and Sign In UI]] — `Done`, owner-approved 2026-08-03
- **An `Accepted` ADR on the trusted proxy boundary** — see Task 1. This is a hard gate: implementation may not begin while the ADR is `Draft` or `Review` ([[CLAUDE|CLAUDE.md]] §7).

> [!note] Execution order set by the owner on 2026-08-03
> This step runs **before** [[STEP-16a Developer Session Inspector]], reversing the order first proposed. The regression here is a live denial of service in a shipped control, while the inspector is a development aid — the security fix goes first. One consequence: STEP-16a's proxy-header panel will report the identity scheme this step establishes, rather than the broken one it would otherwise have documented.

## Required Documentation

- [[API Conventions]] — the contract this amends
- [[Security Architecture]] — trust boundary treatment
- [[Web Session Handling]] — what the proxy currently sends
- [[CLAUDE|CLAUDE.md]] §14 (API security), §16 (Zero Trust, untrusted input), §28a (environment configuration)

## Tasks

1. ~~**Write an ADR**~~ — **Done 2026-08-03.** [[ADR-002 Trusted Proxy and Client Address Resolution]], `Accepted` by the project owner the same day. It records which headers are honoured and under what condition, the right-to-left parsing rule, the allowlist configuration format, the closed failure mode, per-environment expectations, the two-mechanism split and its reasoning, and a **Future Evolution** section documenting the migration path to a distributed limiter — including the two backend-unavailable operating modes (**Availability First**, adopted for Foundation, and **Security First**), with the production decision deliberately left to a future ADR.

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

## Outcome

**Completed 2026-08-03.** The regression [[STEP-16 Sign Up and Sign In UI]] recorded is closed: a rate limiter that counted the whole platform as one caller now counts the right identity in both request classes.

### What was built

`app/core/client_address.py` holds the resolution rules as **pure logic** — addresses and headers in, an address out, no request object and no I/O. That shape is why the parsing rules could be tested exhaustively (27 cases) rather than through HTTP fixtures. `app/core/user_rate_limit.py` holds `limit_by_user`, the route-level dependency that keys on the verified `user_id`. Public limiting stayed in `RateLimitMiddleware`, re-keyed onto the resolved address.

`RateLimitExceededError` lives in `app/core/security.py` with one entry in the `app/core/errors.py` handler table, following the established convention rather than returning a `JSONResponse` from the dependency.

### The negative controls, which are the real evidence

Two regressions were introduced deliberately and the suites re-run, because a security test that passes for an unrelated reason proves nothing:

- **Trust gate removed** (every peer treated as trusted): exactly the 4 spoofing tests failed, including the central `test_a_forged_header_from_an_untrusted_peer_is_ignored`. Restored, all 27 pass.
- **Per-user key replaced with a shared bucket**: exactly the 2 independent-bucket tests failed, including `test_the_limit_key_cannot_be_influenced_by_the_request`. Restored, all 11 pass.

### Decisions made during implementation

- **A circular import was assumed and turned out not to exist.** The first draft of `user_rate_limit.py` used a placeholder-dependency indirection to avoid importing `CurrentUserDep`. Checking the actual import graph showed `token_service` imports only `config` and `security`, so a direct import is fine — the workaround was removed. Worth recording because the workaround was *more* code defending against a problem that was never there.
- **The allowlist is validated at startup, not on first use.** A malformed entry exits the process with a message naming the variable. Discovering it on a request would mean running for some time with a narrower allowlist than intended, silently degraded to the defect this step closes.
- **An empty allowlist warns at boot** rather than failing. Running with nothing in front of the API is legitimate; running *behind* a proxy with an empty allowlist is the defect itself, and it is otherwise invisible ([[CLAUDE|CLAUDE.md]] §26).
- **The `rate_limit_exceeded` log line gained an identity *class*, never the identifier.** A client IP or user id in a log line is personal data, and this line is emitted on exactly the traffic most likely to be automated probing ([[Privacy and Data Protection]]).
- **No address is forwarded on authenticated calls.** Those are limited by `user_id`, so collecting an address would serve nothing ([[CLAUDE|CLAUDE.md]] §16 data minimization).
- **`apps/web` *sets* the forwarding header rather than appending.** It is the first trusted hop, so anything a browser sent under that name is discarded — appending would splice an attacker-chosen entry into a chain the API is about to trust.

### A test-environment constraint worth knowing

`TestClient` reports its peer as the literal string `testclient`, which no CIDR can match — so through the real app, forwarded headers are always correctly ignored. That covers the *untrusted* case (the security-relevant one) but cannot exercise the trusted path. Tests needing a trusted peer build a minimal app with the same middleware and pass an address the allowlist matches. Stated here so a later session does not mistake the two fixtures for duplication.

### Validation

| Check | Result |
|---|---|
| `apps/api` tests | **113 passed**, 117 skipped (database tests, no live DB in this environment) — up from 74 |
| `apps/api` ruff check | Clean |
| `apps/api` ruff format | Clean |
| `apps/api` mypy strict | Clean, 37 source files |
| `apps/web` tests | **45 passed** — up from 34 |
| `apps/web` eslint | Clean |
| `apps/web` tsc | Clean |
| `apps/web` build | Succeeds, 12 static pages |

### Not built, deliberately

- **A shared rate-limit store.** Needs its own ADR; see [[ADR-002 Trusted Proxy and Client Address Resolution]] §Future Evolution. The limiter remains in-process and per-worker, and per-user keys make that approximation *more* visible: N workers permit N× each user's allowance.
- **Rules for password reset and email confirmation.** Those endpoints do not exist. Creating them to have something to limit would be inventing scope.
- **Per-workspace AI spend quotas.** [[STEP-18 AI Cost Governance Controls]] owns those ([[CLAUDE|CLAUDE.md]] §15a). `limit_by_user` is a mechanism they can build on, not a substitute — a request limit and a spend ceiling answer different questions.

### A correction made before marking this Done

The first draft of this Outcome recorded that `limit_by_user` was applied to **no** production route — mechanism, tests and error contract all present, nothing calling it. Writing that down is what exposed it as a defect rather than a boundary: the Definition of Done says *"authenticated requests are limited per verified `user_id`"*, and a limiter wired to nothing does not satisfy that however well it is tested.

Two routes genuinely warranted one on their existing merits, and both now carry it:

- **`POST /workspaces`** (10/min) — any authenticated caller may create workspaces without limit, and each bootstraps two rows through the privileged service path.
- **`GET /{workspace_id}/export`** (5/min) — the most expensive read the API serves, and the shape a stolen token would reach for.

`test_a_real_route_carries_its_per_user_limit` asserts the wiring through the route table, and was verified to fail when a limit is removed. Without it the mechanism could have passed every other test in the suite while limiting nothing — the failure mode that nearly shipped here.

---

## Navigation

- **Previous:** [[STEP-16 Sign Up and Sign In UI]]
- **Next:** [[STEP-16a Developer Session Inspector]]
- **Parent:** [[Build Plan]]
