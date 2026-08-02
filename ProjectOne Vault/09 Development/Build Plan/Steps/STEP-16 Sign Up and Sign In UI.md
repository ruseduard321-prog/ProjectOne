---
title: STEP-16 Sign Up and Sign In UI
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-02
tags: [engineering, workflow, build-step, frontend,security]
step_id: STEP-16
step_status: Not Started
detail_level: full
---

# STEP-16 — Sign Up and Sign In UI

**Status:** Not Started
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

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — authentication, security controls, and a session/token storage decision). It carries an **owner approval gate**: [[STEP-17 AI Router and Provider Abstraction]] does not begin until the owner confirms this step, including the token storage approach.

---

## Navigation

- **Previous:** [[STEP-15 App Shell and Routing]]
- **Next:** [[STEP-17 AI Router and Provider Abstraction]]
- **Parent:** [[Build Plan]]
