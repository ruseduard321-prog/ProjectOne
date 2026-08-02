---
title: STEP-16a Developer Session Inspector
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-03
tags: [engineering, workflow, build-step, frontend, security, development]
step_id: STEP-16a
step_status: Done
detail_level: full
---

# STEP-16a — Developer Session Inspector

**Status:** Done
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

## Outcome

**Completed 2026-08-03.** `/dev/session` reports the running session's actual condition in development, and is **absent from a production build entirely** — not merely refused.

### The defect that shaped the implementation

The first implementation put `notFound()` at the top of the page component, which is the obvious way to write this. Testing it against a real production build returned **`HTTP 200` with the not-found body inside it**.

The cause is the root `loading.tsx` Suspense boundary: Next.js has already flushed a 200 by the time a page body runs, so `notFound()` can change what renders but not the status code. **This is the same failure STEP-16 documented for `redirect()`, one level up** — a render that has begun streaming can no longer choose its status. It would not have been found by review, only by requesting the route against a production build.

The fix moves enforcement to `src/proxy.ts`, which runs before rendering begins and can return a real 404. That mirrors what STEP-16 did for the redirect, and is now the second instance of the same lesson: **anything that must control an HTTP status belongs before the render, not inside it.**

### Two genuinely independent mechanisms

The step required build-time absence *and* runtime refusal. An intermediate state satisfied only the second — the route still appeared as `ƒ /dev/session` in the build output — which was recorded as a gap and then closed rather than accepted:

1. **Build-time.** Development-only routes are named `page.dev.tsx`, and `next.config.ts` adds `dev.tsx` to `pageExtensions` **only** when the build is not production. A production build does not recognise the file as a route at all: never compiled, absent from the route manifest, unreachable by any means. Verified by inspecting the build output and grepping the manifests.
2. **Runtime.** `src/proxy.ts` refuses the whole `/dev/*` namespace with a **404** (never 403 — a 403 confirms the route exists). Verified by serving a production build and observing `HTTP 404` with a zero-byte body, while `/sign-in` still answered 200.

They fail independently: one depends on `NODE_ENV` at build time, the other at run time. `notFoundInProduction()` remains in the page as a third, weaker line — it cannot set a status, but it stops the work happening if a page is somehow reached another way.

A test asserts the config's duplicated expression agrees with `devRoutesEnabled()` across all five environment combinations, because drift in the permissive direction would leave the page in a production bundle.

### The secret-leak check, done by grep

The page renders derived facts only. Proven by planting cookies carrying marked values (`SIGNATURE-SECRET-MUST-NOT-LEAK-XYZ`, `REFRESH-SECRET-QQQ`), fetching the rendered HTML, and grepping for each — **all clean**, including every individual JWT segment, since a partial leak is still a leak. The same fetch confirms the derived facts *are* present (`SESSION-ID-ABC`, `Present (httpOnly…`, the expiry countdown), so the scan is not passing against an error page.

`Set-Cookie` headers on a visit: **none**. The page never mutates session state, including never deleting a dead cookie it discovers — the STEP-16 trap that stranded users forever.

### Decisions made during implementation

- **No API endpoint was added.** `/health` already reports real database connectivity (STEP-07), so the step's preference for reuse held. New production surface for a development page is a bad trade, and the API-side header echo was left unbuilt for the same reason — the page renders Next.js's own view and says plainly that it is not the API's.
- **`/dev/*` is matched by the proxy but not session-gated.** The inspector must render signed out: "why am I signed out" is one of the questions it exists to answer, and a redirect to sign-in would hide exactly the state worth inspecting.
- **The JWT is decoded, never verified.** The API owns signature verification against JWKS; duplicating it here would create a second place for the two answers to drift apart. This is a view of what the browser holds, not an authentication decision — `GET /auth/me` is what actually proves the session works, and the page calls it.
- **`isDevOnlyPath` matches a prefix**, so a future inspector page inherits the exclusion rather than needing to remember it. Tested against `/developer-settings` and `/devices`, which must **not** match.
- **`export const dynamic` must be a static literal.** An imported constant failed the build outright — discovered, not assumed.

### Validation

| Check | Result |
|---|---|
| Production build: route absent | **Confirmed** — no `/dev/session` in build output or manifests |
| Production runtime: `/dev/session` | **HTTP 404**, zero-byte body |
| Production runtime: `/dev/anything` | **HTTP 404** — the whole namespace |
| Production runtime: `/sign-in` (control) | HTTP 200 |
| Development: `/dev/session` | HTTP 200, renders signed in, signed out and expired |
| Secret leak scan | **Clean** — grepped, not reviewed |
| Cookie mutation | **None** — no `Set-Cookie` on any visit |
| `apps/web` tests | **74 passed** — up from 45 |
| `apps/web` eslint / tsc / build | Clean |

Negative control: removing the proxy's production refusal failed exactly the 2 exclusion tests, and they passed again on restore.

### Known limitations

- **The API-side proxy header view is not built.** The page shows what *Next.js* received and states that the API's own view may differ. Adding the echo means new API surface carrying its own exclusion; it was judged not worth the risk for a development aid. If STEP-12a's allowlist is ever misconfigured, this page narrows the search but does not settle it.
- **`readProfile` is called with the access token but the session is not refreshed** if it has expired. Deliberate: the page observes, and a diagnostics page that silently repaired the thing being diagnosed would be lying about the state it reports.

---

## Navigation

- **Previous:** [[STEP-12a Trusted Proxy and Per-User Rate Limiting]]
- **Next:** [[STEP-17 AI Router and Provider Abstraction]]
- **Parent:** [[Build Plan]]
