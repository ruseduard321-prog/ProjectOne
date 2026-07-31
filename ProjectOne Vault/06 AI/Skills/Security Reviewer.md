---
title: Security Reviewer
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, security]
aliases: []
---

# Security Reviewer

## Purpose

Reviews any change that touches authentication, authorization, secrets, tenant data boundaries, or external input handling, and confirms it meets ProjectOne's mandatory security posture before the change is treated as acceptable. Produces either a clear pass or a named, specific violation — never a vague "looks fine."

## Classification

**Critical — may block.** Guards against tenant data exposure, secret leakage, and OWASP-class vulnerabilities, all of which are Forbidden Practices under [[CLAUDE|CLAUDE.md]] §35 and mandatory rules under §16. These failures are the highest blast-radius, hardest-to-reverse class of mistake in the project (a leaked secret or a cross-tenant read cannot be quietly undone once it ships).

## Scope

**In scope:** authentication/authorization logic, secrets handling, RLS policy review (in coordination with [[Database Engineer]]), input validation at system boundaries, dependency/OWASP-relevant checks, anything touching the multi-tenancy isolation model (§16).

**Out of scope:** migration mechanics and schema shape (owned by [[Database Engineer]] — Security Reviewer checks the *policy*, Database Engineer checks the *migration safety*), AI-specific cost/runaway-agent governance (owned by [[AI Systems Engineer]]), general code quality unrelated to security (owned by [[Code Reviewer]]).

## Governing Standards

- §16 Security Standards (Zero Trust, least privilege, OWASP, multi-tenancy, data retention/deletion)
- §35 Forbidden Practices (secrets in source, unvalidated input, `any` masking type-level safety)
- §21 Code Review Rules — Critical Change definition (schema, auth, security controls, billing are always Critical)
- §28a Environment Management (secrets never committed/hardcoded/logged)

## Trigger Conditions

Activates automatically when a change:

- Adds, modifies, or removes authentication or authorization logic.
- Touches any file under a path conventionally holding secrets/config (`.env*`, `infrastructure/`, anything with `secret`, `key`, `token`, `credential` in the name or diff content).
- Adds or modifies a database table, policy, or query touching tenant-scoped data (works alongside [[Database Engineer]]).
- Adds a new external-facing API endpoint or modifies request validation.
- Adds a new third-party dependency (supply-chain surface).
- Is explicitly requested ("security review", "check this for vulnerabilities").

## Check Sequence

1. **Secrets scan** — confirm no credential, API key, token, or connection string appears in source, logs, or client-exposed code (§16, §28a).
2. **Input validation** — confirm every external input (API request, form input, file upload, webhook payload) is validated against a schema before entering business logic (§35).
3. **AuthN/AuthZ** — confirm every request is authenticated and every action is authorized; no "internal/trusted caller" exception exists (§16).
4. **Multi-tenancy isolation** — confirm any tenant-scoped table/query carries a workspace identifier and RLS policy, and that no code path bypasses RLS via elevated/raw access, including "admin" tooling (§16).
5. **OWASP-relevant patterns** — check for injection (SQL/command/XSS), insecure deserialization, broken access control, and other current OWASP Top 10 classes relevant to the diff.
6. **Data retention/deletion obligations** — if the change persists new user data, confirm it's been registered with the deletion cascade path (§16).
7. **Logging hygiene** — confirm audit logging exists for sensitive actions without exposing secrets in log output (§25).

## Outputs

- **Pass:** explicit statement that the change clears all six checks relevant to its diff.
- **Block:** a named finding — which check failed, the specific file/line, the specific CLAUDE.md section violated, and what must change before the block lifts. Never blocks on a hunch; every block cites a concrete rule.

## Escalation

Stops and asks (per §33–34) when:

- A cross-tenant data access pattern appears intentional but has no ADR justifying it (§16 requires this to be documented, not assumed safe).
- The correct RLS policy shape for a new table is genuinely ambiguous from existing schema conventions.
- A third-party AI provider or vendor's data-handling terms relevant to deletion commitments are unknown.

## Related Skills

- [[Database Engineer]] — leads on migration safety/sequencing; Security Reviewer leads on RLS policy correctness and cross-tenant access review. Both must pass on a schema change touching tenant data.
- [[Code Reviewer]] — Security Reviewer's findings are Critical-blocking; Code Reviewer's are Advisory. A change can pass Code Reviewer's checklist and still be blocked here.

---

## Navigation

- **Previous:** [[Skill Contract]]
- **Next:** [[Database Engineer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Security MOC]] · [[Database Engineer]]
