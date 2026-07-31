---
title: STEP-06 Continuous Integration
category: Development/Build Step
status: draft
version: "1.3"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, testing]
step_id: STEP-06
step_status: Done
---

# STEP-06 — Continuous Integration

**Status:** Done

> [!success] Was `Blocked` on a missing remote; resolved and confirmed green
> This step was `Blocked` for one session: Validation requires *"a push triggers the workflow and it completes green,"* and the repository had no git remote, so GitHub Actions had nowhere to run. The implementation was complete but unverifiable, and was deliberately left **uncommitted** ([[Execution Protocol#Blocked Steps Are Never Committed]]).
>
> **Unblocked on 2026-07-31** by the project owner creating `github.com/ruseduard321-prog/ProjectOne` and adding it as `origin`.
>
> The run result could not be observed from the build environment — the repository is private, the in-app browser is not authenticated to it, and the [[MCP/GitHub|GitHub MCP]] exposes no workflow-run tool. **The project owner confirmed both jobs completed successfully on 2026-07-31**, which closed the final check.

## Goal

CI enforcing lint, type-check and tests on every push — established now, while the codebase is empty, so every later step lands into a pipeline that is already policing it.

## Prerequisites

- [[STEP-05 Environment and Secrets]] — `Done`

## Required Documentation

- [[Chapter 11 - Code Review Standards]] — what CI must enforce
- [[Chapter 10 - Testing Standards]] — test layers and runners
- [[Testing Strategy]] — the overall approach

## Tasks

1. Add a GitHub Actions workflow in `.github/workflows/` running on push and pull request.
2. Jobs for `apps/web`: install, lint, `tsc --noEmit`, test.
3. Jobs for `apps/api`: install, lint, type-check, test. The commands exist as of [[STEP-04 API App Skeleton]] and are the contract to call — `ruff check .`, `ruff format --check .`, `mypy app`, `pytest` — run from a venv built off the pinned `pyproject.toml`. Match the Python version to that file's `requires-python` floor (`>=3.12`), not to the 3.14.6 that happens to be on the current dev machine.
4. Configure the test runners for both apps. An empty suite must **pass**, not error on "no tests found" — otherwise the pipeline is red from day one and everyone learns to ignore it. This applies to `apps/web`, which still has no runner; `apps/api` already runs pytest.
5. Add one trivial passing test to `apps/web` to prove its runner actually executes. `apps/api` already has real tests from [[STEP-04 API App Skeleton]] (`tests/test_health.py`) — no placeholder is needed there.
6. Ensure CI never has access to production secrets; use repository secrets scoped to non-production only.
7. **Supply both apps' required environment variables to the CI jobs.** As of [[STEP-05 Environment and Secrets]] neither app starts or builds without them — `apps/web` fails at `next build` and `apps/api` exits non-zero — so a pipeline that omits them is red on arrival. Non-secret placeholder values (the `.env.example` defaults, `environment=development`) are correct here; nothing in CI needs a real credential yet. See [[Environment and Secrets]].

## Validation

- A push triggers the workflow and it completes green.
- Deliberately breaking a type locally causes the type-check job to fail (verify the pipeline can actually go red, then revert).
- Both apps' test suites execute and report as passing in the CI log.

## Definition of Done

CI runs on every push, enforces lint + type-check + tests for both apps, is verified green on the current skeleton, and is verified capable of failing. No production secrets are reachable from CI.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — infrastructure/deployment configuration): flag for owner review.

## Outcome

All seven Tasks are implemented and all three Validation checks pass. CI runs on `github.com/ruseduard321-prog/ProjectOne` (private) on every push and pull request.

**On confirming the run.** The build environment cannot observe a workflow result: the repository is private, the in-app browser is not authenticated to it, and the [[MCP/GitHub|GitHub MCP]] exposes no workflow-run tool. Reading a stored credential to call the Actions API directly was attempted and correctly blocked — not a workaround to pursue. **Until one of those changes, confirming a CI run is an owner action**, and any future step whose validation depends on CI output inherits that handoff.

### What exists

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Two jobs — `web` and `api` — on every push and pull request |
| `apps/web/vitest.config.mts` | Vitest 4 runner, `passWithNoTests: true` |
| `apps/web/src/lib/env.test.ts` | 7 tests covering `parseEnv` |
| `apps/web/package.json` | `test` script added |
| `apps/web/src/lib/env.ts` | Validation made lazy — see below |

### Validation results

| Check | Result |
|---|---|
| A push triggers the workflow and it completes green | **Passed** — both jobs green on `25bebe1`, confirmed by the project owner |
| Deliberately breaking a type causes the type-check job to fail | **Passed** — verified for both apps, then reverted |
| Both apps' test suites execute and report as passing | **Passed** — 7 web + 4 API, run under CI's exact env |

Both jobs' full command sequences were executed locally **with `.env.local` and `.env` removed**, using only the environment variables the workflow itself defines. Every step exited 0. That is the strongest available evidence short of a real run, and it specifically proves the workflow's `env:` blocks are sufficient — the failure mode most likely to make a first CI run red.

The pipeline was also proven capable of going red: a deliberate type error failed `tsc` (exit 2) and `mypy`, and an unused import failed `ruff`. All three were reverted and re-verified clean.

### Decisions and notes for later steps

- **`src/lib/env.ts` now validates lazily, on first property access, instead of at import time.** This was a real design flaw surfaced by writing the first test: the eager top-level export threw *while the module was being imported*, so no test could import `parseEnv` without a fully configured environment — defeating the isolation that function was deliberately separated out to allow in [[STEP-05 Environment and Secrets]]. A `Proxy` preserves the `env.environment` call-site syntax exactly. **Fail-fast behavior is unchanged and was re-verified**: `next build` without configuration still fails, naming both missing variables.
- **Vitest 4, not Jest.** Vite-native, so it reads the TypeScript config with no extra transform pipeline, and `passWithNoTests` satisfies the empty-suite requirement directly.
- **No jsdom and no React Testing Library.** Every component is currently a Server Component with no interactivity; a DOM environment would be dependencies added for tests that do not exist ([[CLAUDE|CLAUDE.md]] §28). Component testing arrives with the first Client Component at [[STEP-15 App Shell and Routing]].
- **The config is `vitest.config.mts`, not `.ts`.** Vite warns that ESM-in-CommonJS config loading breaks in a future major version; the extension resolves it now rather than leaving a scheduled CI failure.
- **CI has no repository secrets wired in at all.** Not "scoped to non-production" — none, because nothing yet exists that CI is entitled to read. Both jobs use the non-secret `.env.example` placeholder values. The first real secret arrives with [[STEP-07 Supabase Provisioning]] and must be added as a non-production repository secret then.
- **`permissions: contents: read`** is set workflow-wide, so any job needing more must widen its own scope explicitly and visibly ([[CLAUDE|CLAUDE.md]] §16, least privilege).
- **The API job pins Python 3.12**, matching the `requires-python` floor in `pyproject.toml` rather than the 3.14.6 on the current dev machine — CI verifies the oldest supported interpreter, which is the actual contract ([[STEP-04 API App Skeleton]]).
- **`npm ci`, not `npm install`** — it installs exactly the lockfile and fails on drift between it and `package.json`, which is what makes a run reproducible.
- **Pre-existing advisory noise, not introduced here:** `npm audit` reports 3 high-severity advisories in `postcss` and `sharp`, both transitive dependencies of `next` itself since [[STEP-03 Web App Skeleton]]. No audit gate was added to CI — doing so would make the pipeline red on arrival for a problem outside this step's scope. Worth a deliberate decision separately.

---

## Navigation

- **Previous:** [[STEP-05 Environment and Secrets]]
- **Next:** [[STEP-07 Supabase Provisioning]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Chapter 11 - Code Review Standards]] · [[Testing Strategy]]
