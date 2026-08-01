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
**Detail level:** outline — expanded to full detail by [[STEP-11 Authorization and RBAC]], per [[Execution Protocol]].

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

## Tasks

Not yet expanded. [[STEP-11 Authorization and RBAC]] writes this section, when the surrounding code exists and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-11 Authorization and RBAC]]
- **Next:** [[STEP-13 Auth Users Workspaces Endpoints]]
- **Parent:** [[Build Plan]]
