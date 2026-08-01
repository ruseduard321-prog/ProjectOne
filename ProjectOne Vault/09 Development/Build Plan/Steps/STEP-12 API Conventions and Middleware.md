---
title: STEP-12 API Conventions and Middleware
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, backend,api]
step_id: STEP-12
step_status: Not Started
detail_level: outline
---

# STEP-12 — API Conventions and Middleware

**Status:** Not Started
**Detail level:** full — expanded by [[STEP-11 Authorization and RBAC]], per [[Execution Protocol]].

## Goal

The cross-cutting API layer every endpoint inherits: versioning, standardized responses and errors, rate limiting, request validation, audit logging.

## Scope

Conventions and middleware only — the endpoints that use them are STEP-13. Built once, here, rather than re-decided per endpoint.

## Prerequisites

- [[STEP-11 Authorization and RBAC]] — `Done`

## Required Documentation

- [[API Architecture]]
- [[Chapter 06 - FastAPI Architecture]]
- [[Authentication Implementation]] — the error translation and response shapes already in place
- [[CLAUDE|CLAUDE.md]] §14

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-10 Authentication Backend]]:

- **Endpoints already exist, so conventions are being applied retroactively.** `/auth/*` and `/workspaces` shipped before this step ([[Authentication Implementation]]). Where a convention here differs from what they do, this step changes them — a convention with pre-existing exceptions is not a convention.
- **Error handling is partly established and should be generalized, not replaced.** `app/core/security.py` defines a typed `AuthError` hierarchy with a `public_message` separate from the log detail, and `app/routers/auth.py` maps it to status codes in one function. That pattern is the candidate for a project-wide error contract; the mapping currently lives in a router and belongs in middleware.
- **One security property must survive any refactor:** every authentication failure returns 401 with an *identical* body, whichever cause. A standardized error envelope that leaks the reason — expired vs. bad signature vs. absent — reintroduces the oracle [[CLAUDE|CLAUDE.md]] §24 exists to prevent. Guarded by `test_rejections_do_not_reveal_why`.
- **Rate limiting on the auth endpoints was deferred to this step.** Supabase applies its own limits upstream in the meantime, which is not the same as the API having any.
- **Request logging must never log the `Authorization` header or a token.** Nothing logs today, so this step is where that rule becomes real ([[CLAUDE|CLAUDE.md]] §16, §25).

Added by [[STEP-11 Authorization and RBAC]]:

- **A second error hierarchy now exists and must be generalized alongside the first.** `AuthorizationError`/`WorkspaceAccessError` are deliberately *not* `AuthError` subclasses ([[Authorization Model]]), because the two map to different status codes. Any project-wide error contract must preserve that split rather than collapsing them into one envelope.
- **The 403 mapping already lives where this step wants mappings to live** — an `add_exception_handler` in `app/main.py`, not a router. That is the precedent to generalize, and the `AuthError`→401 mapping still sitting in `app/routers/auth.py` is the thing to bring in line with it.
- **Two response-body properties must survive any refactor**, both currently guarded by tests: every *authentication* failure returns an identical 401 body whichever cause, and every *authorization* refusal returns an identical 403 body whether the caller lacked the role or was not a member at all. The second is what stops a workspace id becoming an existence oracle.
- **Endpoint count has grown.** `/auth/*`, `GET /workspaces`, `GET /workspaces/{id}/permissions`, `PATCH /workspaces/{id}`, `GET /workspaces/{id}/export`, `DELETE /workspaces/{id}/data`. Conventions apply retroactively to all of them.

## Tasks

1. **Decide the API versioning scheme and apply it.** Every route today is unversioned (`/auth/sign-in`, `/workspaces`). Choose the shape (URL prefix `/v1` versus header negotiation), state why, and move the existing routes onto it — a convention with pre-existing exceptions is not a convention ([[CLAUDE|CLAUDE.md]] §14).
2. **Define the standard response and error envelope**, and generalize the two existing hierarchies onto it. `AuthError` → 401, `AuthorizationError` → 403, validation → 422, and one shape for all of them. Preserve the identical-body properties named above; a standardized envelope that leaks a reason reintroduces the oracle [[CLAUDE|CLAUDE.md]] §24 exists to prevent.
3. **Move error translation out of routers into exception handlers.** `app/routers/auth.py::_reject` is the last mapping living in a router; `app/main.py` already holds the 403 handler as the pattern to follow.
4. **Add request logging with a correlation id**, carried through the request and included in every log line and error response, so a user-reported failure is findable ([[CLAUDE|CLAUDE.md]] §25). **Never log the `Authorization` header, a bearer token, a refresh token, or a password** — and add a test asserting that, because this is the rule most easily broken by a later convenience change.
5. **Add rate limiting to the authentication endpoints.** Deferred from STEP-10; Supabase's upstream limits are not the API having any. Sign-in and sign-up at minimum.
6. **Write [[API Endpoint Template]]** if it does not yet exist, since STEP-13 documents every endpoint with it.
7. **Bring the existing endpoints onto every convention above**, not just new ones.

## Validation

- Every existing endpoint answers on its versioned path, and the suite still passes — proving the migration was applied rather than the routes duplicated.
- Authentication failures return one identical 401 body; authorization refusals return one identical 403 body. Both directions tested, and `test_rejections_do_not_reveal_why` still passes.
- A rate-limited endpoint actually refuses the *n+1*th request within the window, observed rather than assumed.
- A log line from a request carries the correlation id, and a test asserts no log line contains a token or the `Authorization` header value.
- The STEP-09, STEP-10 and STEP-11 suites all still pass. Conventions must not have widened access.
- Lint, format, type-check and the full suite pass in CI.

## Definition of Done

Every endpoint shares one versioning scheme, one response envelope, one error contract and one logging path; error translation lives in handlers rather than routers; the auth endpoints are rate limited; and no log or response body leaks a credential or the reason a request was rejected.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — public API contract, security controls): flag for owner review.

---

## Navigation

- **Previous:** [[STEP-11 Authorization and RBAC]]
- **Next:** [[STEP-13 Auth Users Workspaces Endpoints]]
- **Parent:** [[Build Plan]]
