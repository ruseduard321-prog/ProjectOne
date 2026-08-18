---
name: full-stack-engineer
description: Implements features spanning frontend and backend, applying Frontend Standards, Backend Standards, and API Standards during implementation. Triggers on implementation work that adds or changes feature behavior — new or modified features, pages, components, endpoints and services; shipped endpoint contracts and service logic; server actions, route handlers, loading/error/not-found and empty states; the typed API client; and repository, job, storage or workflow code where it changes feature behavior — plus frontend/backend wiring in either direction and explicit build or change requests. Not triggered by standalone refactors, renames, test-only, CI or documentation-only changes. Advisory — self-checks against standards, does not independently block.
classification: advisory
---

# Full Stack Engineer

Source of truth: `ProjectOne Vault/06 AI/Skills/Full Stack Engineer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

Fires on implementation work that **adds or changes feature behavior**, in one layer or several. A path being touched is never the trigger on its own.

**Feature surface — new or changed**

- New feature, page, component, endpoint, or service.
- Shipped endpoint behavior or contract — request/response shape, status codes, validation, pagination (`apps/api/app/routers/`, `apps/api/app/schemas/`). `API_VERSION` / `API_PREFIX` in `apps/api/app/core/api.py` → public API contract, **Critical** under §21.
- Business logic in `apps/api/app/services/`, with or without a router change.
- What a shipped page or component does (`apps/web/src/app/`, `apps/web/src/components/`), including Server↔Client Component conversions and props/composition changes to a component with existing consumers.

**Wiring** — frontend↔backend in either direction; the typed client layer (`apps/web/src/lib/api.ts`, `apps/web/src/lib/*-api.ts`).

**Next.js surfaces** — `actions.ts` and `route.ts` under `apps/web/src/app/` (apply §12/§14, not §11 alone); `loading.tsx`, `error.tsx`, `not-found.tsx`, in-component empty states.

**Supporting layers, only where behavior changes** — `apps/api/app/repositories/`, `apps/api/app/jobs/`, `apps/api/app/storage/`, `apps/api/app/workflows/`. A path match alone does not fire this skill.

**Explicit request** — "build this feature", "implement this endpoint", "change this feature", "modify this flow", "update this endpoint/service/component behavior".

**Not a trigger:** standalone refactor; rename or file move; test-only change; CI or tooling configuration change (all → `code-reviewer` on the finished diff); documentation-only change (→ `documentation-keeper`) — unless part of an explicit feature implementation request.

**Where another skill leads:** see Handoff. This skill still implements the surrounding feature code; the decision inside each boundary is not its own.

**The nine checks below are §11/§12/§14 only** — they do not cover job retry ceilings, storage isolation, workflow approval defaults, migration safety, AI spend limits, or performance consequences. Handoff routes each to its owner.

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

Each leads its own decision boundary; Full Stack Engineer still implements the surrounding feature code.

- Diagnosis of an unexplained defect → `bug-investigator` skill; it hands an established root cause back here for the fix.
- New architecture approval → `architecture-reviewer` skill (Critical); implement only against an Accepted ADR.
- Schema/migration design, and migration safety → `database-engineer` skill (Critical).
- Security-sensitive logic, trust boundary, auth and permissions (`apps/web/src/proxy.ts`, `apps/web/src/lib/session-cookies.ts`), storage or tenant isolation → `security-reviewer` skill (Critical).
- AI cost governance, AI spend limits, AI-related job retry ceilings, and AI/agent workflow approval defaults → `ai-systems-engineer` skill.
- Performance-significant runtime behavior the implementation adds, changes or removes — a fetch/query/render path whose runtime behavior changes materially, a result-set bound or parallel structure altered, caching/invalidation, loading/bundle behavior or worker cadence changed → `performance-reviewer` skill (advisory; its PASS never substitutes for `code-reviewer`, `database-engineer`, `ai-systems-engineer`, or owner review). A path, query, component or asset merely being touched is not sufficient; runtime performance behavior must change materially.
- Non-AI job retry behavior this checklist does not cover, and any remaining finished-diff concern → `code-reviewer` skill, on the finished diff.
