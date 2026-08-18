---
title: Code Reviewer
category: AI/Skills
status: stable
version: "1.2"
last_updated: 2026-08-18
tags: [ai, engineering]
aliases: []
---

# Code Reviewer

## Purpose

Runs the CLAUDE.md §21/§36 review checklist against any non-trivial change, surfacing quality, consistency, and completeness gaps before a human reviewer has to find them manually.

## Classification

**Advisory — recommends only.** Quality and consistency issues are real but not irreversible; the right response is a clear recommendation the author weighs, not an automatic block. (Contrast with [[Security Reviewer]] and [[Database Engineer]], which guard irreversible failure modes and may block.)

## Scope

**In scope:** naming/folder placement conventions, unnecessary complexity, TypeScript/React/Next.js per-domain checklist items (§21), Definition of Done completeness (§22), unrelated-refactor detection (§29), the general §36 Quality Checklist — applied to code being added, changed, or removed, plus the two surfaces that carry the checklist's own evidence: the test suite (including the guard tests that encode a standard rather than exercise a feature) and the lint, type-check and test configuration that defines the bar the per-domain checklist is applied against.

**Out of scope:** security-specific findings (hands off to [[Security Reviewer]]), migration safety (hands off to [[Database Engineer]]), AI cost-governance specifics (hands off to [[AI Systems Engineer]]), documentation drift specifically (hands off to [[Documentation Keeper]], though Code Reviewer flags if docs were touched at all), whether a new module, dependency, or framework is *permitted* at all (hands off to [[Architecture Reviewer]]), and the security posture of infrastructure and deployment configuration (hands off to [[Security Reviewer]] — Code Reviewer reads the quality gates in that configuration, not its credentials or its exposure).

## Governing Standards

- §21 Code Review Rules (checklist: architecture, readability, security, tests, documentation; per-domain TypeScript/React/Next.js checklists)
- §36 Quality Checklist (the full pre-completion gate)
- §29 Refactoring Rules (scope discipline)
- §27 Naming Conventions
- §8–9 Repository Rules and Folder Structure
- §18 Testing Standards (business logic requires unit tests; bugs are verified, not just closed — the rule check 5 enforces)
- §22 Definition of Done (partial completion is not completion — the list check 7 walks)
- §30b AI Development Workflow Automation (a check that silently stops running is worse than no check, because it is trusted while being absent)

## Trigger Conditions

[[CLAUDE|CLAUDE.md]] §6a routes **"a non-trivial diff, or any change presented as ready for review"** to this skill. That row is a routing summary, not a boundary — this section is the complete activation surface, and it defines *non-trivial* for this repository, because a threshold nobody can evaluate is not a threshold.

**A diff is non-trivial unless every hunk in it falls under the exclusions at the end of this section.** Triviality is a property of the whole diff, not of any single hunk: one behavioural line makes the entire change reviewable, however much formatting travels alongside it.

**Application code** — under `apps/api/app/`, `apps/web/src/`, `packages/`, or `scripts/`:

- **Additions** — a module, endpoint, component, service, repository, route, or hook that did not exist before.
- **Modifications to code that already ships.** This is now the common case in this repository, not the rare one, and the previous "adds or modifies" wording gave it no weight of its own. A signature change rippling through call sites, a widened public interface, a changed default, a module moved between layers (§8 requires dependencies to keep flowing inward), or a rename reaching names outside the file it starts in — each alters code other code already depends on, which is a strictly harder review than reading something new in isolation.
- **Deletions** — a module, function, endpoint, component, export, or branch removed. Absent from the trigger list until now, and the one shape where the checklist's usual question inverts: the review is what still depends on the removed code, whether removing it falls inside the approved task at all (§29 and §35 forbid unrelated changes in *either* direction), and whether the tests covering it were deleted along with it. Deleting the last caller of something is not the same as deleting something unused.

**Tests** — `apps/api/tests/`, any `apps/web/src/**/*.test.ts(x)`, and the shared fixtures they rest on (`conftest.py`, `fakes.py`):

- A test-only diff carries no product behaviour, and precisely for that reason nothing else reviews it — while §18 makes the test the evidence that a rule holds at all.
- Specifically: an assertion removed, a test skipped or marked expected-to-fail (`pytest.mark.skip`, `xfail`, `.skip`, `.only`), a fixture or fake widened until it no longer constrains, or a test edited to match code that changed rather than the code fixed to match the test. Each ends with a green suite proving less than it did the day before, and green is what §22 reads.
- **Guard tests get the scrutiny of the rule they hold, not the size of their diff.** `test_api_conventions.py`, `test_ci_configuration.py` and `test_governance_docs_sync.py` encode standards rather than exercise features — the first is explicit that credential redaction "fails silently when it breaks: nothing turns red, the token is simply in the log file. These assertions are what turn it red." Relaxing one relaxes the standard everywhere, in a diff touching no application code.

**Quality-gate configuration** — the machinery the checklist and §22 are enforced by:

- `.github/workflows/ci.yml`. The `Protect main` ruleset matches required status checks on the literal check name, so renaming a job removes the gate while every job still passes — the file states this of `governance docs (sync check)`, and it holds equally for `web` and `api`. Removing a step, making one conditional, or making it non-blocking is the same class of change.
- The configuration defining the bar itself: `select` / `ignore` / `per-file-ignores` under `[tool.ruff.lint]` and `strict` under `[tool.mypy]` in `apps/api/pyproject.toml`; `"strict"` in `apps/web/tsconfig.json`; `globalIgnores` and rule overrides in `apps/web/eslint.config.mjs`; the test configuration in `apps/web/vitest.config.mts` (its `include` globs and `passWithNoTests: true`, which makes a suite that stopped matching any file exit 0) and `[tool.pytest.ini_options]`. §11 keeps strict mode on and `any` forbidden; loosening one of these relaxes that for the entire codebase without editing a line of it.
- Infrastructure and deployment configuration remains **Critical** under §21 whatever this Advisory skill concludes. Check 8 flags it for owner review, and nothing in this section's narrowing changes what that step flags or who it routes to.

**Presented as done** — a change described as complete, finished, or ready for review, **whatever its size**. This fires independently of the non-trivial threshold above: a one-line fix called done still gets the §22 walk, because "done except for X" is exactly what check 7 exists to catch.

**Explicit request** — "review this", "check this against our standards".

**Deliberately not a trigger:**

- **Diffs that cannot change behaviour, structure, or coverage** — a comment- or docstring-only edit, a pure `ruff format` or lint-autofix reflow, or a change confined to files not authored here (`node_modules/`, `.venv/`, `__pycache__/`, `.mypy_cache/`, `*.egg-info/`, `tsconfig.tsbuildinfo`, `next-env.d.ts`).
- **A lockfile-only diff** (`package-lock.json`) — supply-chain surface already claimed by [[Security Reviewer]]'s dependency trigger, and nothing a quality checklist reads.
- **A documentation-only change under `ProjectOne Vault/`** — [[Documentation Keeper]] leads on vault consistency, [[Architecture Reviewer]] on ADR content. This replaces the standing instruction this note previously carried, to apply a non-code subset of §36 to Markdown and ADR changes: it described a repository that had no code yet, and left this skill reviewing documentation by default while the shipped code it was written for reached it only by the sentence above. Such a change still triggers here when it is *presented as ready for review*, where §22 applies to it as it does to anything else.

## Check Sequence

1. **Scope discipline** — does the diff match the stated task, or does it bundle unrelated refactors (§29, §35)?
2. **Naming and placement** — correct casing conventions (§27), correct folder per §8–9, no `utils`-style dumping ground.
3. **No `any`, no unvalidated input** — TypeScript strict-mode violations, missing schema validation at boundaries.
4. **Per-domain checklist** — apply the relevant one(s): TypeScript (type safety, error handling, testability), React (component size, hooks, accessibility, design-system adherence), Next.js (Server/Client separation, data fetching, routing, bundle impact).
5. **Test coverage** — is business logic touched covered by a unit test; are DB/API interactions covered by an integration test where relevant (§18)?
6. **Documentation currency** — if architecture or behavior changed, has the affected documentation been identified (§19)? (Full remediation is [[Documentation Keeper]]'s job; Code Reviewer just flags the gap.)
7. **Definition of Done** — walk the §22 list; call out anything marked "done except for X."
8. **Critical Change flag** — if the diff touches schema, auth, security, billing, public API, infrastructure, AI/agent architecture, memory, or multi-tenancy, flag it as Critical per §21 and note it needs owner review regardless of this skill's own (Advisory) verdict.

## Outputs

A ranked findings list (most-severe first), each with file/line reference, the specific rule violated, and a one-line fix suggestion. Never a block verdict — always framed as "recommend before merge," with the Critical Change flag (step 8) called out separately since that's a process requirement, not a Code Reviewer opinion.

## Escalation

Stops and asks (per §33–34) when:

- Whether a refactor is "unrelated" to the stated task is genuinely ambiguous — asks rather than assuming either way (§29 requires explicit agreement before folding in a refactor).
- A per-domain checklist item depends on a design-system or architecture decision not yet documented anywhere accessible.

## Related Skills

- [[Security Reviewer]] and [[Database Engineer]] — Critical-blocking skills that lead when their domains overlap with a change Code Reviewer is also looking at; Code Reviewer's verdict never overrides theirs. On `apps/api/pyproject.toml` and `apps/web/package.json` specifically, both skills may fire on one diff: Security Reviewer leads on dependency versions and supply-chain risk, Code Reviewer on the lint, type-check and test configuration in the same files.
- [[Documentation Keeper]] — receives the documentation-currency flag from step 6 for actual remediation, and leads outright on a documentation-only vault change.
- [[AI Systems Engineer]] — receives any AI/agent-architecture-flagged change from step 8 for cost-governance-specific review.
- [[Architecture Reviewer]] — leads on whether a new module, dependency, or framework is permitted (§10 stack table, ADR requirement) and on ADR content; Code Reviewer leads on whether what was built is placed, named, and covered correctly (§8–9, §27, §18). Both may comment on one change that adds a module.

---

## Navigation

- **Previous:** [[Database Engineer]]
- **Next:** [[AI Systems Engineer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Engineering Handbook MOC]]
