---
title: STEP-16 Sign Up and Sign In UI
category: Development/Build Step
status: draft
version: "1.2"
last_updated: 2026-08-02
tags: [engineering, workflow, build-step, frontend,security]
step_id: STEP-16
step_status: Done
detail_level: full
---

# STEP-16 — Sign Up and Sign In UI

**Status:** Done
**Detail level:** full — expanded by [[STEP-15 App Shell and Routing]], per [[Execution Protocol]].

## Goal

Working sign-up and sign-in screens wired to the STEP-13 endpoints — the first end-to-end path through the whole stack.

## Scope

Completes the auth vertical slice: UI → API → RLS → database. Proves the layers actually connect before more is built on them.

## Prerequisites

- [[STEP-15 App Shell and Routing]] — `Done`

## Required Documentation

- [[Design System]]
- [[Authentication and Authorization]]
- [[Chapter 04 - React Standards]]

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-15 App Shell and Routing]]:

- **The shell exists and does not enforce authentication.** `app/(app)/layout.tsx` is a route group wrapping `/dashboard`, `/projects`, `/chat` and `/settings`. Gating those routes is **this step's** work — STEP-15 deliberately left it undone rather than guessing at a session contract that did not exist.
- **Auth screens sit outside the app shell.** Sign-up and sign-in must not render the shell's nav chrome, so they belong in their own route group (e.g. `(auth)`) rather than inside `(app)`.
- **The token layer is the only styling vocabulary.** Semantic tokens only, no `dark:` variants, no hardcoded values — the form controls this step introduces are the first real use of `--color-border-strong`, which exists precisely because an input whose edge is invisible is a control some users cannot find ([[Design System]] §6.2).
- **`--color-danger` is the token for validation errors**, and `--color-skeleton` (added in STEP-15) for loading placeholders.
- **Two client boundaries exist today** (`error.tsx`, `SidebarNav`). Forms need client interactivity, so this step adds more — keep each boundary as small as the interaction requires rather than marking a whole page.
- **`EmptyState` is available** at `components/shell/EmptyState.tsx` if a surface needs one.

### The API contract this step consumes

Settled and versioned in [[API Endpoints]] — read it rather than inferring shapes:

- `POST /api/v1/auth/sign-up` — **201**. Returns `email_confirmation_required` when the project issues no session. **400** on rejection with a **deliberately generic message**; the UI must not "improve" it, because a specific one turns this into an account-enumeration oracle. Rate limited 5/min.
- `POST /api/v1/auth/sign-in` — returns access + refresh tokens. Rate limited 10/min.
- `POST /api/v1/auth/sign-out` — Bearer. Revokes the session **upstream**; a client-side discard leaves the token valid until expiry.
- `POST /api/v1/auth/refresh` — exchanges a refresh token. Rate limited 30/min.
- `GET /api/v1/auth/me` — Bearer. Provisions the `public.users` row on first use.
- Every error arrives in the STEP-12 envelope: `{"detail", "request_id"}`.

## Tasks

1. **Build the sign-up and sign-in screens** in an `(auth)` route group, outside the app shell. Both are forms over the endpoints above, with every async state defined — loading, validation error, and server error ([[CLAUDE|CLAUDE.md]] §11).
2. **Decide and implement token storage**, and record the reasoning. This is the consequential decision of the step: `localStorage` is readable by any XSS, so an httpOnly cookie set by a Next.js route handler is the safer default. **If the chosen approach differs from what [[Authentication and Authorization]] specifies, stop and ask rather than diverging silently** ([[CLAUDE|CLAUDE.md]] §33–34).
3. **Gate the `(app)` route group on an authenticated session**, redirecting unauthenticated users to sign-in. Enforcement is server-side; a client-side redirect is a convenience, never the control ([[Chapter 05 - NextJS Architecture]] §5.10).
4. **Wire sign-out** to the endpoint so revocation happens upstream, then clear local session state and redirect.
5. **Surface the signed-in user in the shell header** using `GET /auth/me`, replacing nothing else in the STEP-15 chrome.
6. **Handle token refresh** so a user whose access token expires mid-session is not silently logged out.

**Explicitly out of scope:** password reset, email confirmation flows, OAuth/social sign-in, and workspace creation UI. Each is its own scope; none is required to prove the vertical slice.

## Validation

- **The full slice works end to end against a live backend**, observed: sign up → sign in → land in the shell → sign out. Not mocked — the point of this step is proving UI → API → RLS → database actually connects.
- **An unauthenticated request to a shell route redirects to sign-in**, verified by requesting it directly with no session rather than by clicking through the UI.
- **Sign-out revokes upstream** — verified by reusing the old access token against a Bearer endpoint and confirming it is rejected. A UI that merely forgets the token would pass a click-through test and fail this one.
- **The sign-up rejection message stays generic**, verified by attempting to register an existing address and confirming the response does not reveal that the account exists.
- **Rate limits surface as a usable message**, not a raw 429 or a silent failure.
- Every form defines loading, validation-error and server-error states; errors render from the `{"detail", "request_id"}` envelope with the `request_id` shown so a user report is traceable.
- **No token is written to `localStorage` or `sessionStorage`** if the cookie approach is chosen — grep for it rather than trusting review.
- **No credential is logged**, client or server. The backend already redacts structurally (STEP-12); this step must not undo that by logging a request body.
- Semantic tokens only; contrast verified for any new pairing, particularly form controls on `--color-border-strong`.
- Keyboard: every field reachable and labelled, errors associated with their inputs via `aria-describedby`, focus moved to the first error on failed submit.
- Lint, type-check, tests and build pass for `apps/web` in CI.

## Definition of Done

A user can sign up, sign in, reach the application shell, and sign out with the session revoked upstream; unauthenticated access to shell routes is refused server-side; token storage is implemented with its reasoning recorded; every form defines its loading and error states from the API's own error envelope; and the vertical slice is demonstrated against a live backend rather than a mock.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — authentication, security controls, and a session/token storage decision). It carries an **owner approval gate**, **cleared by the project owner on 2026-08-03** — the httpOnly cookie approach, server-side session handling, the Next.js proxy and the absence of `localStorage` were each confirmed. The same decision inserted [[STEP-16a Developer Session Inspector]] and [[STEP-12a Trusted Proxy and Per-User Rate Limiting]], so the step that follows this one is STEP-16a rather than [[STEP-17 AI Router and Provider Abstraction]].

## Outcome

**The vertical slice works end to end against a live backend**: sign up → sign in → application shell → sign out, with the user's identity in the header coming from `GET /auth/me`, which means UI → API → RLS → database all connect.

**Token storage: httpOnly cookies written server-side**, never `localStorage` or `sessionStorage`. [[Authentication and Authorization]] specifies no mechanism, so this extends that document rather than diverging from it — checked before implementing, as the task required. The full reasoning, the two-layer gate and the refresh behaviour are [[Web Session Handling]]. Verified in a real browser: signed in, `document.cookie` empty and both storages empty, yet a same-origin request still authenticated.

Because the browser cannot read the token, every API call is server-side — which also sidesteps the fact that the API registers **no CORS middleware** and would have refused a direct browser call anyway.

### Three defects were found by running it, not by reading

**A `"use server"` file may export only async functions.** `EMPTY_FORM_STATE` was a constant in the actions module and failed the build outright, because every export of such a file becomes a remotely-callable endpoint. Moved to `lib/form-state.ts`.

**A `redirect()` from the layout could not send a redirect status.** It runs inside STEP-15's `loading.tsx` Suspense boundary, so Next.js had already flushed a **200** and could only finish with a `<meta http-equiv="refresh">`. No shell markup or user data leaked — the gate held — but a 200 carrying a meta-refresh depends on the client honouring it. Resolved by adding `src/proxy.ts`, which runs before rendering and returns a real **307**, verified on all four shell routes.

**Clearing a dead cookie threw and stranded the user forever.** The most consequential of the three. A layout that discovers a spent refresh token cannot delete the cookie carrying it — Next.js permits cookie writes only in a Server Action or Route Handler — and the attempt *throws*, aborting the render and killing the redirect that was about to fire. Reproduced exactly: a stale cookie produced an endless "Loading…" skeleton with no escape. Fixed by making the session writes report failure instead of throwing, and adding `/session/expired`, a Route Handler that can write, which the gate routes rejected sessions through.

That third one is the lesson worth carrying: **the place that discovers a credential is dead is not always a place permitted to delete it**, and the failure mode is a user trapped rather than a user signed out.

### Sign-out revokes, but not everything, and now the note says so

The step required proving revocation happens upstream. Measured against the live project:

- **The refresh token is revoked immediately** — exchanging it after sign-out returns 401. The session is genuinely terminated.
- **An access token already issued keeps working for up to an hour.** `GET /auth/me` returned 200 for a token captured before sign-out, because access tokens are stateless JWTs verified locally against JWKS — honouring one requires no call to Supabase, so revocation cannot reach it.

This is an inherited property of the STEP-10 design rather than something this step introduced, but [[Authentication Implementation]] implied more than it delivered and is now corrected with the measurement. Closing the gap entirely means a revocation check on every request, which is the cost the stateless design exists to avoid.

### Anti-enumeration verified, and stronger than required

Registering an address that **already exists** returns the same `201 / email_confirmation_required` as a brand-new one. The response does not reveal that the account exists at all, and the failure message is identical whether the address is new, taken, or rate-limited.

### A regression in an existing control, recorded not resolved

**The API's rate limiter now sees one IP.** With every call proxied through Next.js, the limiter keys on the web server's address rather than the end user's — so it no longer limits per user, and one user hitting the limit can lock out others. Observed directly: exhausting the limit via curl also blocked the browser's sign-in. This needs a trusted forwarded-client-address scheme (an untrusted forwarded header is spoofable and would be worse than the current state). Out of this step's scope, named in [[Web Session Handling]], and flagged for the owner below.

### Also done

- Next.js 16 deprecates the `middleware` file convention in favour of `proxy`; the file follows it, and the build is warning-free.
- Web suite grew from **7 tests to 34**. API suite unchanged at 74 passing.
- Test accounts created against the live Supabase project were deleted afterwards.

### Validation results

| Check | Result |
|---|---|
| Full slice against a live backend | **Pass** — sign up → sign in → shell → sign out, observed in a browser |
| Unauthenticated shell route, requested directly | **Pass** — 307 to `/sign-in` on all four routes |
| Sign-out revokes upstream | **Pass** for the refresh token; access token survives to expiry (documented above) |
| Sign-up rejection stays generic | **Pass** — an existing address is indistinguishable from a new one |
| Rate limits surface usably | **Pass** — 429 renders as "Too many attempts. Wait a minute and try again." |
| No token in `localStorage`/`sessionStorage` | **Pass** — both empty while signed in; `document.cookie` holds neither token |
| Loading / validation-error / server-error states | **Pass** — errors render from the `{"detail", "request_id"}` envelope with the id shown |
| Keyboard and screen reader | **Pass** — labels bound, `aria-invalid` set, `aria-describedby` resolves, focus moves to the first error on failed submit |
| Lint, type-check, tests, build | **Pass** — 34 tests, clean build, no warnings |

### For the owner

Beyond confirming the token storage approach, two items need a decision rather than a review:

1. **The one-hour access-token window after sign-out** — accept as documented, or shorten the token lifetime.
2. **Per-user rate limiting is currently ineffective** behind the proxy, and should be fixed before real traffic.

---

## Navigation

- **Previous:** [[STEP-15 App Shell and Routing]]
- **Next:** [[STEP-16a Developer Session Inspector]]
- **Parent:** [[Build Plan]]
