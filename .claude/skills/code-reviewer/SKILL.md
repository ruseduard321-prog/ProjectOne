---
name: code-reviewer
description: Runs the project's code-review checklist (naming, folder placement, scope discipline, test coverage, per-domain TypeScript/React/Next.js rules, Definition of Done) against non-trivial changes. Triggers on application code added, modified, OR deleted; on test-only changes including skipped/removed assertions and the guard tests that encode a standard; on CI workflow and lint/type-check/test configuration changes that move the quality bar; on any change presented as ready for review whatever its size; and on explicit request. Advisory — recommends only, never blocks, and never lifts the Critical-change owner gate.
classification: advisory
---

# Code Reviewer

Source of truth: `ProjectOne Vault/06 AI/Skills/Code Reviewer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

CLAUDE.md §6a routes "a non-trivial diff, or any change presented as ready for review" here. **A diff is non-trivial unless every hunk falls under "Not a trigger" below** — triviality is a property of the whole diff, not of one hunk.

**Application code** — `apps/api/app/`, `apps/web/src/`, `packages/`, `scripts/`:

- **Adds** a module, endpoint, component, service, repository, route, or hook.
- **Modifies** already-shipped code — signature changes across call sites, widened public interface, changed default, module moved between layers (§8 inward dependency flow), rename reaching outside its own file.
- **Deletes** code — module, function, endpoint, component, export, or branch. Review what still depends on it, whether removal is in the approved task (§29/§35 cut both ways), and whether its tests were deleted with it.

**Tests** — `apps/api/tests/`, `apps/web/src/**/*.test.ts(x)`, `conftest.py`, `fakes.py`:

- Any test-only diff. Nothing else reviews it, and §18 makes the test the evidence.
- Flag: removed assertions; `pytest.mark.skip` / `xfail` / `.skip` / `.only`; a fixture or fake widened until it stops constraining; a test edited to match changed code rather than the code fixed.
- Guard tests carry the weight of the rule, not their diff size: `test_api_conventions.py`, `test_ci_configuration.py`, `test_governance_docs_sync.py`.

**Quality-gate configuration**

- `.github/workflows/ci.yml` — job renames (branch protection matches required checks by literal name, so a rename removes the gate while CI stays green), removed steps, steps made conditional or non-blocking.
- The bar itself: `[tool.ruff.lint]` `select`/`ignore`/`per-file-ignores` and `[tool.mypy] strict` in `apps/api/pyproject.toml`; `"strict"` in `apps/web/tsconfig.json`; `globalIgnores`/rule overrides in `apps/web/eslint.config.mjs`; `include` globs and `passWithNoTests` in `apps/web/vitest.config.mts`; `[tool.pytest.ini_options]`.
- Infrastructure/deployment configuration stays **Critical** under §21 regardless of this skill's Advisory verdict — check 8 flags it for owner review.

**Presented as done** — described as complete, finished, or ready for review, **whatever its size** (fires independently of the non-trivial threshold).

**Explicit request** — "review this", "check this against our standards".

**Not a trigger:** comment/docstring-only edits; pure `ruff format` or lint-autofix reflow; files not authored here (`node_modules/`, `.venv/`, `__pycache__/`, `.mypy_cache/`, `*.egg-info/`, `tsconfig.tsbuildinfo`, `next-env.d.ts`); lockfile-only diffs (`package-lock.json` → `security-reviewer`); documentation-only changes under `ProjectOne Vault/` (→ `documentation-keeper`, ADRs → `architecture-reviewer`) unless presented as ready for review.

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

- Security-domain findings → `security-reviewer` skill (Critical, leads over this skill's verdict). On `apps/api/pyproject.toml` / `apps/web/package.json`, it leads on dependency versions; this skill leads on the lint/type/test configuration in the same file.
- Schema/migration findings → `database-engineer` skill (Critical, leads over this skill's verdict).
- Documentation-currency flag (step 6) → `documentation-keeper` skill for remediation; it leads outright on documentation-only vault changes.
- AI/agent-architecture-flagged changes (step 8) → `ai-systems-engineer` skill.
- Whether a new module/dependency/framework is permitted, and ADR content → `architecture-reviewer` skill (Critical); this skill still owns placement, naming, and coverage of what was built.
