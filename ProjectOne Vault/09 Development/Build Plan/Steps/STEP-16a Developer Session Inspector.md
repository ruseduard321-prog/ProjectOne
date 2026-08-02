---
title: STEP-16a Developer Session Inspector
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-03
tags: [engineering, workflow, build-step, frontend, security, development]
step_id: STEP-16a
step_status: Not Started
detail_level: full
---

# STEP-16a — Developer Session Inspector

**Status:** Not Started
**Detail level:** full — inserted after [[STEP-16 Sign Up and Sign In UI]] by owner request on 2026-08-03.

## Why This Step Exists

[[STEP-16 Sign Up and Sign In UI]] moved the entire session into httpOnly cookies written server-side. That is the correct security posture, and it has a deliberate consequence: **the running session is now invisible to the developer building against it.** The browser cannot read the cookies, DevTools shows opaque values, and every API call happens server-side where no network tab observes it.

Three of STEP-16's defects — the spent refresh token that stranded users, the `redirect()` that could not send a status, the `"use server"` export failure — were each found by running the flow and reasoning backwards from a symptom. A page that states the session's actual condition would have shortened all three.

The project owner requested this on 2026-08-03 as a development aid. It is its own step rather than part of [[STEP-17 AI Router and Provider Abstraction]] because it is unrelated frontend work, and folding it in would violate scope discipline ([[CLAUDE|CLAUDE.md]] §29/§35).

## Goal

A read-only page at `/dev/session` that reports the running authentication system's actual state — and that **cannot exist in a production build**.

## The Central Risk

This feature's entire risk is its exclusion, not its content. A diagnostics page that reports session metadata, proxy headers and backend connectivity is a reconnaissance surface if it ever answers in production. The requirement is therefore inverted from a normal feature: **the step's hardest validation is proving the route is absent, not proving it renders.**

Two independent mechanisms are required, because one mechanism is one mistake away from failing:

1. **Build-time exclusion** — the route is not compiled into a production build at all. A route that does not exist cannot leak, regardless of runtime configuration.
2. **Runtime refusal** — the handler itself returns 404 when `NODE_ENV === "production"`, so a misconfigured build that somehow includes the route still refuses.

A 404 rather than a 403: a 403 confirms the route exists.

## Scope

One page, read-only, in `apps/web`. **No new API endpoints**, and no mutation of session state — the page observes, it never refreshes, revokes or repairs.

`apps/api` changes are limited to what the page reads and only if an existing endpoint does not already provide it — see Task 3, which deliberately prefers reusing `/health` over adding a diagnostics endpoint.

## Prerequisites

- [[STEP-16 Sign Up and Sign In UI]] — `Done`, owner-approved 2026-08-03
- [[STEP-12a Trusted Proxy and Per-User Rate Limiting]] — runs first by owner decision on 2026-08-03, so Task 5's rate limit identity panel reports the per-user scheme rather than the regression it replaced

## Required Documentation

- [[Web Session Handling]] — the cookie contract this page reports on
- [[Design System]] — the page is developer-facing but still ProjectOne UI
- [[CLAUDE|CLAUDE.md]] §16 (secrets), §24 (error states), §28a (environment management)

## Inherited from STEP-16

- **Tokens are httpOnly cookies read server-side** via `src/lib/session.ts` and `src/lib/session-cookies.ts`. This page is a Server Component; it reads the same way every other server surface does.
- **`src/proxy.ts` returns a real 307** before rendering begins. Whatever route-matching that file performs must be checked against `/dev/session` — an inspection page that the auth gate redirects away from is useless.
- **`/session/expired` owns cookie deletion.** This page must never delete a cookie, even one it discovers is dead. That failure mode is exactly what STEP-16 documented.
- **The API error envelope is `{"detail", "request_id"}`.** Backend probes surface through `ApiError` like everything else.

## Tasks

1. **Create the route** at `apps/web/src/app/dev/session/page.tsx` as a Server Component, outside the `(app)` route group — it is not an application screen and should not inherit the shell's nav.

2. **Report the session state**, all of it derived server-side:
   - Authentication status (signed in / signed out / session expired)
   - Current user: `id`, `email`, `display_name` from `GET /auth/me`
   - Access token **expiry** — decoded from the JWT's `exp` claim, rendered as an absolute time and a countdown
   - Refresh token expiry if the token's shape exposes it; **state "not exposed" if it does not**, rather than inferring a value
   - Session id — the JWT `sid` claim if present, otherwise state its absence
   - Which session cookies are present, **by name and presence only**

3. **Report connectivity** by calling the existing `GET /health`, which STEP-07 already made a real readiness check reporting database connectivity. Render API reachability and the Supabase/database status it returns. **Do not add a diagnostics endpoint** to `apps/api` if `/health` already answers this — a new endpoint is new production surface added for a development page.

4. **Report the proxy headers the API actually received**, and the client address it resolved from them. This is the diagnostic that makes the page worth building: [[STEP-12a Trusted Proxy and Per-User Rate Limiting]] makes address resolution depend on configuration that is easy to get wrong and silent when wrong, and this panel is where a misconfigured allowlist becomes visible. It requires an API-side echo, which is **new surface and therefore gated**: if implemented, it carries the same dual exclusion as the page — the endpoint must not exist in a production build. If that cannot be done cleanly, **render the headers Next.js itself received and state plainly that the API-side view is unavailable**, rather than presenting the proxy's own view as the API's.

5. **Report the rate limit identity** — which key the API would count this request against (`user:<id>` or `ip:<addr>`). [[STEP-12a Trusted Proxy and Per-User Rate Limiting]] runs first, so this reports the real per-user scheme; it must show the actual resolved key, not a client-side reconstruction of what the key *should* be, since a reconstruction that drifts from the API's own logic is worse than no panel at all.

6. **Enforce the dual exclusion** described above: build-time absence plus runtime 404.

7. **Redact structurally, not by discipline.** No token value, no cookie value, no API key, no password, no `Authorization` header value, no Supabase connection string. Prefer computing a boolean or an expiry from a secret over displaying any part of it. Where a value's presence matters, render presence — never a prefix, and never a truncation, since a truncated token is still token material.

## Explicitly Out of Scope

- Any mutation: refresh, revoke, sign-out, cookie repair
- Impersonation, user switching, or acting as another workspace
- A general developer tools section — this is one page
- Any production-visible surface whatsoever

## Validation

- **The route returns 404 in a production build**, verified by building with `NODE_ENV=production`, serving it, and requesting the path — observed, not inferred from configuration.
- **The route is absent from the production build output**, verified by inspecting the build manifest/output for the path rather than by trusting the runtime check.
- **The route renders in development** for a signed-in user, showing a correct user id and a token expiry that matches the JWT's actual `exp`.
- **No secret appears anywhere in the rendered output**, verified by fetching the rendered HTML and grepping it for the live access token, refresh token and cookie values — grepped, not reviewed by eye ([[CLAUDE|CLAUDE.md]] §16).
- **The page renders correctly signed out**, and while holding an expired session, without throwing and without deleting any cookie.
- **The page never mutates session state** — confirm the cookies are byte-identical before and after a visit.
- Lint, type-check, tests and build pass for `apps/web` in CI.

## Definition of Done

A `/dev/session` page reports authentication status, user identity, token expiries, session id, cookie presence, proxy headers, rate limit identity and API/database health; it is proven absent from a production build *and* proven to 404 at runtime in production mode; no secret material appears in its output, proven by grep; and it mutates nothing.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — security controls: it surfaces authentication state). It carries an **owner approval gate**.

> [!warning] The exclusion is the feature
> If the dual exclusion cannot be proven by observation, this step is `Blocked` — not shipped with a note to verify later. A diagnostics page that might answer in production is a worse outcome than no diagnostics page at all.

---

## Navigation

- **Previous:** [[STEP-12a Trusted Proxy and Per-User Rate Limiting]]
- **Next:** [[STEP-17 AI Router and Provider Abstraction]]
- **Parent:** [[Build Plan]]
