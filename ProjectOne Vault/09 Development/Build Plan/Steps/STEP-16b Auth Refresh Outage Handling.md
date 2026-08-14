---
title: STEP-16b Auth Refresh Outage Handling
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-14
tags: [engineering, workflow, build-step, frontend, security, authentication]
step_id: STEP-16b
step_status: Done
detail_level: full
---

# STEP-16b — Auth Refresh Outage Handling

**Status:** Done
**Detail level:** full — inserted after [[STEP-24 Dashboard]] by owner decision on 2026-08-14, correcting the [[STEP-16 Sign Up and Sign In UI]] session contract.

## Why This Step Exists

[[STEP-24 Dashboard]]'s manual checklist reached its error-boundary item and stopped the API to trigger a data-fetch failure. The dashboard's boundary never rendered. The browser was redirected to `/sign-in` instead, and the session cookies were gone.

The outage never reached the dashboard's data fetches. It was caught four frames earlier, in the shared authentication gate:

```
apiRequest → resolveAccessToken → currentProfile → requireProfile → AppLayout
```

`resolveAccessToken` refreshes an expired access token. Its failure path caught **every** error identically and cleared the session:

```ts
} catch {
  await clearSession();
  return undefined;
}
```

That is correct for a refresh token the provider *rejected*, and wrong for one it never saw. `api.ts` already draws the distinction — `ApiError` carries a status because a request was judged, `ApiUnreachableError` carries none because no request completed — and its own comment says collapsing the two "would tell a user their password was wrong during an outage." The bare `catch` discarded exactly that distinction.

Two [[CLAUDE|CLAUDE.md]] §24 failures follow from one discarded error type:

- **A still-valid credential is destroyed.** The refresh token was never rejected; it was deleted because the service was unreachable. The user must re-authenticate after an outage they did not cause.
- **An availability failure is reported as an authentication failure.** `/sign-in` claims the session ended. It had not.

It is **its own step rather than part of STEP-24** because `auth.ts` is shared authentication code from STEP-16, byte-identical on `main` and on `step-24-dashboard`, and touched by no dashboard work. Folding a shared-auth fix into a dashboard step would violate scope discipline ([[CLAUDE|CLAUDE.md]] §29/§35) and hide an authentication change inside a frontend commit.

**Severity: High, treated as Critical** under [[CLAUDE|CLAUDE.md]] §21 — it changes authentication behaviour.

## Goal

An unreachable API surfaces as a recoverable availability error. It never destroys a valid session and never reports itself as a signed-out state. Genuine rejections keep behaving exactly as [[STEP-16 Sign Up and Sign In UI]] built them.

## Scope

1. Preserve a valid refresh credential when the API is temporarily unreachable.
2. Never translate an availability failure into an authentication rejection.
3. Clear the session **only** when the refresh credential is genuinely rejected.
4. Show a recoverable, friendly availability error carrying no internal detail.
5. Verify the **correct error-boundary level** by inspection, not assumption.
6. Confirm behaviour across `/dashboard`, `/projects`, `/chat` and `/settings`.
7. Confirm recovery once the API returns, without destroying a still-valid session.
8. Preserve all existing authentication and redirect behaviour for genuine 401 responses.

Out of scope: retry/backoff policy, offline support, and any change to [[STEP-24 Dashboard]]'s own surfaces.

## Which Boundary Catches This

**Verified, not assumed** — the owner's instruction was explicit that the dashboard's route boundary must not be presumed to catch a failure thrown by the shared layout.

A Next.js `error.tsx` catches errors thrown by its segment's **children**, not by its own layout. `(app)/layout.tsx` throws, so:

- `(app)/dashboard/error.tsx` — **cannot** catch it. It is nested inside the layout that failed. (It also does not exist on `main`; it is [[STEP-24 Dashboard]]'s work.)
- `(app)/error.tsx` — does not exist, and would not catch its own sibling layout either.
- **`app/error.tsx` (root) — catches it.** The nearest ancestor boundary above `(app)/layout.tsx`.

Confirmed by observation: with the API stopped, the served payload loads `src_app_error_tsx` and reports *"Switched to client rendering because the server rendering errored"*, and the rendered page is the root boundary's own markup.

The root boundary already satisfies requirement 4 as built in [[STEP-03 Web App Skeleton]]: a friendly message, a `reset()` retry, no `error.message`, no stack trace, and a `digest` correlation id. **No new boundary is added** — adding one would duplicate a working boundary to no benefit ([[CLAUDE|CLAUDE.md]] §29).

## Tasks

### 1. Reproduce the defect in an automated test first

Create `apps/web/src/lib/auth.test.ts`. `auth.ts` had **no test file at all**, which is how this shipped. The test must fail against the current code before any fix.

### 2. Distinguish the two failures

In `resolveAccessToken`, re-throw `ApiUnreachableError` and leave every other error on the existing clear-and-return path. The smallest change that makes an existing distinction load-bearing — no new abstraction, no new dependency, no API change.

### 3. Verify the boundary level by inspection

Enumerate the boundaries, identify the nearest ancestor of `(app)/layout.tsx`, and confirm by observation which one renders.

### 4. Confirm across every authenticated route

The gate is in the shared layout, so all four routes are affected identically.

### 5. Confirm recovery

The API returns; pages load again with the session intact and no re-authentication.

### 6. Documentation

Update [[Authentication Implementation]] to record the outage contract, and this note's Outcome.

## Validation

Observed, not assumed.

- [x] `auth.test.ts` fails against the unfixed code, on the assertions describing the defect. **3 failed / 8 passed before the fix.**
- [x] `auth.test.ts` passes after the fix, with the pre-existing behaviour still green. **11/11.**
- [x] The full `apps/web` suite passes. **174 tests, 16 files.**
- [x] Lint, type-check and build pass.
- [x] The governance docs sync check passes.
- [x] Every required CI check on the Pull Request is green.

### Required regression tests

| # | Assertion |
|---|---|
| 1 | Expired access cookie + valid refresh cookie + API unreachable |
| 2 | `ApiUnreachableError` propagates rather than being swallowed |
| 3 | The refresh cookie is **not** deleted |
| 4 | The user is **not** redirected to `/sign-in` |
| 5 | The availability state carries no stack trace, internal URL or raw exception |
| 6 | A genuinely rejected refresh still clears the session and redirects |
| 7 | Recovery works once the API is healthy |
| 8 | Authenticated routes remain protected |

### Manual Browser Test Checklist

| # | Check |
|---|---|
| 1 | With the API stopped, an authenticated route renders the root error boundary, not `/sign-in` |
| 2 | The message is friendly, with a working retry control |
| 3 | No stack trace, exception name or internal URL is visible |
| 4 | `/dashboard`, `/projects`, `/chat`, `/settings` all behave identically |
| 5 | After the API returns, pages load without re-authentication |
| 6 | A genuinely invalid refresh token still clears cookies and lands on `/sign-in` |

## Definition of Done

- [x] Every Validation box is checked.
- [x] The regression tests exist and cover all eight assertions.
- [x] [[Authentication Implementation]] records the outage contract.
- [x] Status is `Done` in this note **and** in the [[Build Plan]] index, and the two agree.
- [x] A Pull Request into `main` is open with every required CI check green.
- [x] **Owner approval is obtained** — this is a Critical change under [[CLAUDE|CLAUDE.md]] §21 (authentication).

### Completion state

This step carried an **owner approval gate**. It was satisfied: the project owner approved and squash-merged [PR #4](https://github.com/ruseduard321-prog/ProjectOne/pull/4) into `main` on 2026-08-14 as commit `e690640`, with every required CI check green.

[[STEP-24 Dashboard]] remains `In Progress` on its own branch and is **not** marked `Blocked`: [[Execution Protocol#Blocked Steps Are Never Committed]] requires a `Blocked` marking to stay uncommitted, so recording one would either breach that rule or strand the branch on a dirty tree. STEP-24 is paused on a named dependency — this step — which is what `In Progress` already means.

---

## Navigation

- **Previous:** [[STEP-24 Dashboard]]
- **Next:** [[STEP-25 Foundation Audit and Internal Readiness]]
- **Parent:** [[Build Plan]]
