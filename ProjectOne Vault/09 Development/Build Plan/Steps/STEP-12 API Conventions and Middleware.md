---
title: STEP-12 API Conventions and Middleware
category: Development/Build Step
status: draft
version: "1.2"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, backend,api]
step_id: STEP-12
step_status: Done
detail_level: full
---

# STEP-12 — API Conventions and Middleware

**Status:** Done
**Detail level:** full — expanded by [[STEP-11 Authorization and RBAC]], per [[Execution Protocol]].

## Goal

The cross-cutting API layer every endpoint inherits: versioning, standardized responses and errors, rate limiting, request validation, audit logging.

## Scope

Conventions and middleware only — the endpoints that use them are STEP-13. Built once, here, rather than re-decided per endpoint.

## Prerequisites

- [[STEP-11 Authorization and RBAC]] — `Done`
- [[STEP-11a Membership Removal Policy]] — `Done`

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

Added by [[STEP-11a Membership Removal Policy]]:

- **A third status code is now in play: 409.** `LastOwnerError` is deliberately not an `AuthorizationError`, and its handler already sits alongside the 403 one in `app/main.py`. The error envelope must carry 401, 403, 409 and 422 without collapsing any pair.
- **One error message is deliberately specific, and must stay that way.** The last-owner 409 names transferring ownership as the remedy. The generic-body rule protects *authentication and authorization* answers, where specificity is an oracle; here it leaks nothing an owner does not already know, and withholding it would leave them stuck.

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

## Outcome

**Every endpoint now shares one contract.** The decisions and their reasoning are [[API Conventions]]; only what a reader of this step needs is recorded here.

**The versioning decision was `/api/v1` as a URL prefix**, with header negotiation rejected: a version that is invisible in a log, a `curl` command and an edge routing rule fails in the one direction that matters — silently, when a client forgets it. `/health` stays unversioned because it is infrastructure rather than a product contract. The six existing endpoints were **migrated, not duplicated**, and `test_the_unversioned_path_no_longer_answers` is what proves it: had both paths answered, the prefix would have been decoration.

**The envelope kept FastAPI's `detail` key** rather than inventing one, and added `request_id` as a *sibling* rather than nesting it. That placement is load-bearing — the identical-401-body and identical-403-body properties are compared on `detail`, and an id that varies per request cannot live inside the compared value without weakening the tests that guard them. Both properties were re-proven against the new envelope.

**Error translation left the routers.** `AuthError` was the last mapping living in one (`app/routers/auth.py::_reject`); it now sits in `app/core/errors.py` alongside the 403, 409, 422, 404 and 500 handlers, registered from a single table. Sign-up's `CredentialsRejectedError` → 400 stayed in the router deliberately: the same exception from sign-in correctly means 401, so it is an endpoint decision rather than a type-to-status mapping.

**Credential redaction was built as a log filter rather than a convention**, and that choice is the substance of task 4. "Do not log the `Authorization` header" holds until someone debugging an auth problem logs the request headers — at which point the token is in the log file and nothing turns red. Enforcing it in the pipeline turns that change into a redacted line instead of a leaked credential. It is tested both directly and through a real request.

**Rate limiting is in-process and per-worker**, stated as a limitation rather than hidden. Exact global limits need shared state, which is new infrastructure and therefore an ADR ([[CLAUDE|CLAUDE.md]] §10, §28) — out of scope for a conventions step, and an approximate limit still stops the attacks it exists for.

**[[API Endpoint Template]] already existed** (task 6) and was updated to match these conventions rather than rewritten.

### Defects found during validation

Both were found by running the tests, not by reading:

- **A test fixture silently disabled authentication.** Overriding `get_tenant_connection` replaces the entire dependency subtree beneath it — including `get_current_user` — so an unauthenticated request reached the handler and returned 200. Four rejection tests were passing against an app that was not checking anything. The fixture was split in two (`client` and `authenticated_client`), with the trap documented on both, since the same override appears in earlier test modules and the failure mode is invisible.
- **Errors that never reach an exception handler bypassed the envelope.** Starlette answers an unmatched route from inside its router, and the rate limiter returns its 429 directly from middleware; neither passes through the handler chain, so both lacked a `request_id`. Stamped by the context middleware on the way out — which is the only place that sees *every* response. Without it the rule would have held for most errors and failed on exactly the two a confused caller is most likely to report.

### Validation

Run against a real PostgreSQL — a throwaway database on the development Supabase instance, created and dropped for the run, with the genuine `auth.uid()`. **160 passed, 0 failed, 0 skipped** (up from 133), including the full STEP-09, STEP-10, STEP-11 and STEP-11a suites. `apps/web`: 7 passed. Lint, format and `mypy app` (strict) all clean.

Observed rather than assumed, per the Validation section above: the *n+1*th sign-in inside the window is genuinely refused with 429 and `Retry-After`, a log line carries the same correlation id the response header returned, and no log line from a real request contains a token or an `Authorization` value.

---

## Navigation

- **Previous:** [[STEP-11a Membership Removal Policy]]
- **Next:** [[STEP-13 Auth Users Workspaces Endpoints]]
- **Parent:** [[Build Plan]]
