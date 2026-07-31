---
name: security-reviewer
description: Reviews changes touching authentication, authorization, secrets, tenant data boundaries, RLS policies, or external input handling. Triggers on diffs adding/modifying auth logic, env/secrets files, database policies on tenant-scoped tables, new API endpoints, or new dependencies. Also triggers on explicit requests like "security review" or "check for vulnerabilities". Critical — may block the change.
classification: critical
---

# Security Reviewer

Source of truth: `ProjectOne Vault/06 AI/Skills/Security Reviewer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

- Diff adds/modifies authentication or authorization logic.
- Diff touches `.env*`, `infrastructure/`, or any file/content matching `secret|key|token|credential`.
- Diff adds/modifies a table, policy, or query on tenant-scoped data.
- Diff adds a new external-facing API endpoint or changes request validation.
- Diff adds a new third-party dependency.
- User explicitly asks for a security review.

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
