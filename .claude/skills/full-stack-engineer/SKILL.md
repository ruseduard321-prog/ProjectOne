---
name: full-stack-engineer
description: Implements end-to-end features spanning frontend and backend, applying Frontend Standards, Backend Standards, and API Standards during implementation. Triggers on new feature/page/component/endpoint/service implementation, or on wiring an existing frontend surface to a new backend endpoint. Advisory — self-checks against standards, does not independently block.
classification: advisory
---

# Full Stack Engineer

Source of truth: `ProjectOne Vault/06 AI/Skills/Full Stack Engineer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

- Implementing a new feature, page, component, endpoint, or service.
- Wiring an existing frontend surface to a new or changed backend endpoint.
- User explicitly requests a feature be built or an endpoint implemented.

## Check Sequence

1. **Server/Client boundary** — default to Server Components; Client Components only when browser APIs, local interactive state, animations, or event handlers require them.
2. **Component philosophy** — single responsibility, composition over inheritance, split before unreadable.
3. **State locality** — state as local as possible; no unnecessary global state; derived state computed, not duplicated.
4. **Props discipline** — explicit, strongly typed, minimal; no deep prop chains where composition solves it.
5. **Router/service separation** — routers validate/call/return only; services own business logic, HTTP-independent; consistent dependency injection.
6. **Input validation** — every external input validated against a schema before business logic.
7. **API contract discipline** — REST-first, idempotent where appropriate, standardized response/error shapes, full per-endpoint security present.
8. **UI completeness** — loading/empty/error states defined for every async UI state; Design System followed; accessibility present by default.
9. **TypeScript discipline** — strict mode, no `any`, explicit types on public APIs.

## Output Format

A self-check list against the nine items: what was applied, what tradeoff was made and why. Anything touching schema, auth, security, billing, public API, infrastructure, AI/agent architecture, memory, or multi-tenancy is flagged as Critical and routed to the owning skill before being considered complete — never marked done by this skill alone.

## Escalation

Stop and ask rather than deciding when:
- The feature's business logic or requirement is genuinely ambiguous.
- A database schema or API contract is referenced but not actually known — hand off to `database-engineer` rather than guessing.
- The feature appears to need new architecture with no Accepted ADR — hand off to `architecture-reviewer` rather than building ahead of approval.

## Handoff

- New architecture approval → `architecture-reviewer` skill.
- Schema/migration design → `database-engineer` skill.
- Security-sensitive logic review → `security-reviewer` skill.
- AI-call-triggering features → `ai-systems-engineer` skill.
- Independent review pass on finished output → `code-reviewer` skill.
