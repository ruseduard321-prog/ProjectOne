---
name: security-reviewer
description: Reviews changes touching authentication, authorization, secrets, tenant data boundaries, RLS policies, or external input handling — including modifications to security machinery that already exists. Triggers on auth/authz changes to new or already-shipped endpoints, env/secrets files, tenant-scoped policies and queries, new API endpoints, new dependencies AND dependency version upgrades, rate limiting, middleware, CORS/security headers, proxy and client-trust-boundary parsing, session/RLS role mechanics, log redaction and audit coverage, and error handling that could disclose sensitive detail. Also triggers on explicit requests like "security review" or "check for vulnerabilities". Critical — may block the change.
classification: critical
---

# Security Reviewer

Source of truth: `ProjectOne Vault/06 AI/Skills/Security Reviewer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

**New security surface**

- Diff adds/modifies/removes authentication or authorization logic.
- Diff adds a new external-facing API endpoint, or changes request validation on an existing one.
- Diff adds a new third-party dependency.
- Diff adds/modifies a table, policy, or query on tenant-scoped data.
- Diff touches `.env*`, `infrastructure/`, or a file whose **name** matches `secret|credential|token|key`.
- Diff assigns a hardcoded string literal to a name matching `secret|credential|token|api_key|password`, or adds a connection string.

**Modifications to existing security machinery**

- **Authorization on shipped endpoints** — `app/core/permissions.py`, `app/core/dependencies.py`, `app/services/authorization_service.py`; any route guard, role check, or permission-matrix entry.
- **Rate limiting** — `RateLimitMiddleware`/`RateLimitRule` in `app/core/middleware.py`, `app/core/user_rate_limit.py`; any limit, window, scope, or exemption change.
- **Middleware** — any change to `app/core/middleware.py` or the request/response pipeline.
- **CORS / security headers** — origin allowlists, `Access-Control-*`, CSP, HSTS, cookie attributes (`SameSite`/`Secure`/`httpOnly`), frame/content-type protections. None configured today; the first one fires this skill.
- **Proxy / trust boundary** — `app/core/client_address.py`, `trusted_proxies`, forwarded-header parsing; `apps/web/src/proxy.ts`, `apps/web/src/lib/session-cookies.ts`.
- **Session / RLS context** — `app/repositories/session.py`, `SET ROLE`, `REQUEST_DATABASE_URL`, `projectone_api`/`authenticated` role split.
- **Dependency upgrades** — version changes in `apps/api/pyproject.toml`, `apps/web/package.json`, `apps/web/package-lock.json`, not only additions.
- **Logging** — `app/core/logging.py` redaction patterns, log-record contents, `app/services/audit_service.py`, `app/services/security_event_service.py`.
- **Error disclosure** — `app/core/errors.py`, `app/core/security.py`; error text, status-code selection, exception detail in responses.

**Explicit request** — user asks for a security review or a vulnerability check.

**Not a trigger:** bare substring `key` in diff content (dict/sort/cache/idempotency keys, `key=` kwargs). Name-shaped and assignment-shaped matches above replace it; check 1 still greps content in full once running.

## Check Sequence

Run in order; stop and report immediately on the first Critical finding rather than continuing silently past it:

1. **Secrets scan** — grep the diff and any new files for credentials, API keys, tokens, connection strings in source, logs, or client-exposed code.
2. **Input validation** — every external input (API request, form, upload, webhook) is validated against a schema before business logic.
3. **AuthN/AuthZ** — every request authenticated, every action authorized; no "internal/trusted caller" exception.
4. **Multi-tenancy isolation** — every tenant-scoped table/query carries a workspace identifier and RLS policy; no raw/elevated bypass, including admin tooling.
5. **OWASP-relevant patterns** — injection (SQL/command/XSS), broken access control, insecure deserialization relevant to the diff.
6. **Data retention/deletion** — new persisted user data is registered with the deletion cascade path.
7. **Logging hygiene** — sensitive actions are audited without secrets in log output.

## Output Format

**PASS** — one line per check confirming it was evaluated and cleared, or "not applicable to this diff."

**BLOCK** — for each failed check: the check name, the exact file/line, the specific CLAUDE.md section violated (cite §number), and the minimum change required to clear it. Never block without citing a concrete rule.

## Escalation

Stop and ask rather than deciding when:
- A cross-tenant access pattern looks intentional but has no ADR.
- The correct RLS policy shape for a new table isn't clear from existing schema conventions.
- A third-party provider's data-deletion terms are unknown and relevant.

## Handoff

- RLS *mechanics*/migration sequencing → `database-engineer` skill (this skill owns policy *correctness*, not migration safety).
- Non-security quality findings → `code-reviewer` skill (Advisory, does not gate this skill's verdict).
