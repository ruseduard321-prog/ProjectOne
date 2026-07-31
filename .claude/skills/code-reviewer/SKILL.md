---
name: code-reviewer
description: Runs the project's code-review checklist (naming, folder placement, scope discipline, test coverage, per-domain TypeScript/React/Next.js rules, Definition of Done) against non-trivial changes. Triggers on new/modified application code, on a change presented as ready for review, or on explicit request. Advisory — recommends only, never blocks.
classification: advisory
---

# Code Reviewer

Source of truth: `ProjectOne Vault/06 AI/Skills/Code Reviewer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

- Diff adds/modifies application code (once `apps/`/`packages/` exist).
- Change is presented as done or ready for review.
- User explicitly asks for a review.
- Today (pre-implementation stage), applies the non-code-specific subset of this checklist to substantive Markdown/ADR/config changes.

## Check Sequence

1. **Scope discipline** — diff matches the stated task; no bundled unrelated refactors.
2. **Naming and placement** — correct casing conventions, correct folder, no `utils`-style dumping ground.
3. **No `any`, no unvalidated input** — TypeScript strict-mode violations, missing schema validation at boundaries.
4. **Per-domain checklist** — TypeScript (type safety, error handling, testability), React (component size, hooks, accessibility, design-system adherence), Next.js (Server/Client separation, data fetching, routing, bundle impact) — whichever apply.
5. **Test coverage** — business logic touched has unit tests; DB/API interactions have integration tests where relevant.
6. **Documentation currency** — if architecture/behavior changed, is the affected documentation identified? (Flag only — remediation is `documentation-keeper`'s job.)
7. **Definition of Done** — walk the full list; call out anything "done except for X."
8. **Critical Change flag** — if the diff touches schema, auth, security, billing, public API, infrastructure, AI/agent architecture, memory, or multi-tenancy, flag as Critical and note it needs owner review regardless of this skill's own verdict.

## Output Format

A ranked findings list (most severe first): file/line reference, the rule violated, a one-line fix suggestion. Always advisory phrasing ("recommend before merge") — never a block/pass verdict. The Critical Change flag (step 8) is called out as a separate process note, not a verdict this skill renders.

## Escalation

Stop and ask rather than deciding when:
- Whether a refactor is "unrelated" to the stated task is genuinely ambiguous.
- A checklist item depends on a design-system/architecture decision not yet documented anywhere accessible.

## Handoff

- Security-domain findings → `security-reviewer` skill (Critical, leads over this skill's verdict).
- Schema/migration findings → `database-engineer` skill (Critical, leads over this skill's verdict).
- Documentation-currency flag (step 6) → `documentation-keeper` skill for remediation.
- AI/agent-architecture-flagged changes (step 8) → `ai-systems-engineer` skill.
