---
title: Security Reviewer
category: AI/Skills
status: stable
version: "1.1"
last_updated: 2026-08-17
tags: [ai, security]
aliases: []
---

# Security Reviewer

## Purpose

Reviews any change that touches authentication, authorization, secrets, tenant data boundaries, or external input handling, and confirms it meets ProjectOne's mandatory security posture before the change is treated as acceptable. Produces either a clear pass or a named, specific violation — never a vague "looks fine."

## Classification

**Critical — may block.** Guards against tenant data exposure, secret leakage, and OWASP-class vulnerabilities, all of which are Forbidden Practices under [[CLAUDE|CLAUDE.md]] §35 and mandatory rules under §16. These failures are the highest blast-radius, hardest-to-reverse class of mistake in the project (a leaked secret or a cross-tenant read cannot be quietly undone once it ships).

## Scope

**In scope:** authentication/authorization logic, secrets handling, RLS policy review (in coordination with [[Database Engineer]]), input validation at system boundaries, dependency/OWASP-relevant checks, anything touching the multi-tenancy isolation model (§16), the request pipeline fronting every endpoint (middleware, rate limiting, CORS/security headers, client-trust-boundary parsing), the session/role mechanics RLS depends on, log redaction and audit coverage, and information disclosure through error responses.

**Out of scope:** migration mechanics and schema shape (owned by [[Database Engineer]] — Security Reviewer checks the *policy*, Database Engineer checks the *migration safety*), AI-specific cost/runaway-agent governance (owned by [[AI Systems Engineer]]), general code quality unrelated to security (owned by [[Code Reviewer]]).

## Governing Standards

- §16 Security Standards (Zero Trust, least privilege, OWASP, multi-tenancy, data retention/deletion)
- §35 Forbidden Practices (secrets in source, unvalidated input, `any` masking type-level safety)
- §21 Code Review Rules — Critical Change definition (schema, auth, security controls, billing are always Critical)
- §28a Environment Management (secrets never committed/hardcoded/logged)
- §14 API Standards (authentication, authorization, rate limiting, request validation, audit logging mandatory on every endpoint — not per-endpoint decisions)
- §24 Error Handling Philosophy (user-facing messages keep implementation detail private)
- §25 Logging Standards (audit sensitive actions without exposing secrets in output)

## Trigger Conditions

Activates automatically on either group below. The first covers **new** security surface; the second covers **modifications to security machinery that already exists** — the class where a control is weakened by a diff that reads as tuning, cleanup, or a version bump rather than as a security change.

**New security surface**

- Adds, modifies, or removes authentication or authorization logic.
- Adds a new external-facing API endpoint, or modifies request validation on an existing one.
- Adds a new third-party dependency (supply-chain surface).
- Adds or modifies a database table, policy, or query touching tenant-scoped data (works alongside [[Database Engineer]]).
- Touches `.env*` or `infrastructure/`, or any file whose **name** contains `secret`, `credential`, `token`, or `key`.
- Assigns a hardcoded string literal to a name matching `secret|credential|token|api_key|password`, or introduces a connection string.

**Modifications to existing security machinery**

- **Authorization on shipped endpoints** — the permission matrix, role model, or any route guard deciding who may call something already live (`app/core/permissions.py`, `app/core/dependencies.py`, `app/services/authorization_service.py`). Widening a role's permissions is an authorization change even when no auth *function* is touched.
- **Rate limiting** — any change to a limit, window, scope, or exemption (`RateLimitMiddleware`/`RateLimitRule` in `app/core/middleware.py`, `app/core/user_rate_limit.py`). §14 makes rate limiting mandatory per endpoint, so loosening one is a security change, not a tuning decision.
- **Middleware** — any change to the request/response pipeline (`app/core/middleware.py`). It sits ahead of every endpoint and can weaken all of them at once.
- **CORS and security headers** — origin allowlists, `Access-Control-*`, CSP, HSTS, cookie attributes (`SameSite`, `Secure`, `httpOnly`), frame and content-type protections. None are configured today; the first to appear triggers this skill.
- **Proxy and client trust boundary** — how a client address or forwarded header is parsed or trusted (`app/core/client_address.py`, `trusted_proxies`), and the web proxy fronting the API (`apps/web/src/proxy.ts`, `apps/web/src/lib/session-cookies.ts`). Trusting a caller-supplied header is a spoofing surface, not a parsing detail.
- **Session and RLS context mechanics** — anything altering how a request's database session acquires or drops its role (`app/repositories/session.py`, `SET ROLE`, `REQUEST_DATABASE_URL`, the `projectone_api`/`authenticated` split). RLS applies only to a session in the right role, so this is load-bearing for tenant isolation while containing no policy of its own.
- **Dependency version upgrades** — a version change in `apps/api/pyproject.toml`, `apps/web/package.json`, or `apps/web/package-lock.json`, not only a newly added package. Upgrades and transitive bumps are the more common supply-chain vector.
- **Security-sensitive logging** — the redaction filter and its patterns (`app/core/logging.py`), what a log record includes, and audit-trail coverage (`app/services/audit_service.py`, `app/services/security_event_service.py`). Narrowing a redaction pattern re-opens the leak the filter exists to close.
- **Error handling that could disclose information** — error text, status-code selection, or exception detail returned to a caller (`app/core/errors.py`, `app/core/security.py`). A 403 naming the caller's role, or a stack trace reaching a response body, is information disclosure.

**Explicit request** — "security review", "check this for vulnerabilities".

**Deliberately not a trigger:** the bare substring `key` in diff *content*. Dict keys, sort keys, cache keys, idempotency keys and `key=` keyword arguments appear in most diffs in this repository; firing on them summons a Critical skill against changes with no security content, and a Critical skill that cries wolf gets waved through — the desensitization [[Skill Contract]] warns about when it ties blocking power to irreversibility. Name-shaped and assignment-shaped matching above replaces it, and the **Secrets scan** check (step 1) still greps content in full once the skill is running.

## Check Sequence

1. **Secrets scan** — confirm no credential, API key, token, or connection string appears in source, logs, or client-exposed code (§16, §28a).
2. **Input validation** — confirm every external input (API request, form input, file upload, webhook payload) is validated against a schema before entering business logic (§35).
3. **AuthN/AuthZ** — confirm every request is authenticated and every action is authorized; no "internal/trusted caller" exception exists (§16).
4. **Multi-tenancy isolation** — confirm any tenant-scoped table/query carries a workspace identifier and RLS policy, and that no code path bypasses RLS via elevated/raw access, including "admin" tooling (§16).
5. **OWASP-relevant patterns** — check for injection (SQL/command/XSS), insecure deserialization, broken access control, and other current OWASP Top 10 classes relevant to the diff.
6. **Data retention/deletion obligations** — if the change persists new user data, confirm it's been registered with the deletion cascade path (§16).
7. **Logging hygiene** — confirm audit logging exists for sensitive actions without exposing secrets in log output (§25).

## Outputs

- **Pass:** explicit statement that the change clears all seven checks relevant to its diff.
- **Block:** a named finding — which check failed, the specific file/line, the specific CLAUDE.md section violated, and what must change before the block lifts. Never blocks on a hunch; every block cites a concrete rule.

## Escalation

Stops and asks (per §33–34) when:

- A cross-tenant data access pattern appears intentional but has no ADR justifying it (§16 requires this to be documented, not assumed safe).
- The correct RLS policy shape for a new table is genuinely ambiguous from existing schema conventions.
- A third-party AI provider or vendor's data-handling terms relevant to deletion commitments are unknown.

## Related Skills

- [[Database Engineer]] — leads on migration safety/sequencing; Security Reviewer leads on RLS policy correctness and cross-tenant access review. Both must pass on a schema change touching tenant data.
- [[Code Reviewer]] — Security Reviewer's findings are Critical-blocking; Code Reviewer's are Advisory. A change can pass Code Reviewer's checklist and still be blocked here.
- [[Architecture Reviewer]] — leads on whether a dependency is *permitted* (§10 stack table, ADR requirement); Security Reviewer leads on its *supply-chain risk*, including version upgrades of already-approved dependencies. Both may comment on one dependency change.

---

## Navigation

- **Previous:** [[Skill Contract]]
- **Next:** [[Database Engineer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Security MOC]] · [[Database Engineer]]
