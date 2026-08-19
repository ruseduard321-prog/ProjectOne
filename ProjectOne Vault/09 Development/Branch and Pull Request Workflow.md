---
title: Branch and Pull Request Workflow
category: Development
status: stable
version: "1.1"
last_updated: 2026-08-19
tags: [engineering, workflow, governance, git]
aliases: ["Git Workflow", "PR Workflow", "Branch Workflow"]
---

# Branch and Pull Request Workflow

How work reaches `main` in ProjectOne. This note is binding on every contributor — the project owner, Claude, and OpenAI Codex alike — and applies to every change without exception, including a one-line documentation fix.

It is the canonical statement of the branch/PR protocol. [[Execution Protocol]] governs *what* a Build Plan step contains and when it may be marked `Done`; this note governs *how* that finished step travels from a working tree to `main`.

## `main` Is Protected

**`main` must never be modified directly.** A `Protect main` ruleset enforces this on GitHub: no direct pushes, no force pushes, no deletions.

**Never bypass, disable, or work around that ruleset.** A rejected push to `main` is the rule functioning correctly, not an obstacle to route around. This holds even for a change that is obviously safe, obviously trivial, or urgently needed — the value of a protected branch is that it has no exceptions, and one "just this once" is what turns a guarantee into a habit.

Only the project owner may alter the ruleset itself, and only deliberately.

## One Task, One Branch

Every task or Build Plan step gets its own branch, created from an up-to-date `main`.

**Never place two unrelated changes on one branch.** A branch is the unit of review, and a reviewer asked to evaluate two unrelated things at once does neither well.

### Naming

| Shape | Use | Example |
|---|---|---|
| `step-NN-short-name` | A [[Build Plan]] step | `step-23-ai-chat` |
| `fix/short-name` | A defect fix | `fix/rls-policy-leak` |
| `chore/short-name` | Tooling, dependencies, process | `chore/agent-collaboration-workflow` |
| `docs/short-name` | Documentation-only change | `docs/adr-template-alignment` |

Lowercase, hyphen-separated, descriptive enough to read in a branch list without opening it.

## The Workflow

1. **Start clean.** `git status` reports a clean tree, and `main` is current (`git fetch origin && git status`). Uncommitted work from an earlier session is dealt with first — see [[#Starting From a Dirty Tree]].
2. **Branch** from `main` using the naming above.
3. **Implement** the task, and only the task. Scope discipline is [[CLAUDE|CLAUDE.md]] §29/§35.
4. **Validate locally.** Run every check for every layer the change touches — lint, type-check, tests, build. Observed, not assumed. The commands are listed per layer in [[AGENTS|AGENTS.md]] and are the same ones CI runs.
5. **Commit.** Atomic, explaining *why* rather than restating the diff ([[CLAUDE|CLAUDE.md]] §20).
6. **Push the branch** and open a **Pull Request into `main`**.
7. **CI must pass.** See [[#Continuous Integration]].
8. **Supply a manual test checklist** where the change has user-visible behavior, and complete it — see [[#Manual Test Checklist]].
9. **Resolve every review conversation.** An open thread blocks merge.
10. **Iterate with additional commits.** CI failures and review feedback are fixed by pushing more commits, **never** by amending, rebasing or force-pushing a commit that has already been pushed — see [[#Iterating on a Pull Request]].
11. **Obtain owner approval** for consequential changes — see [[#Owner Approval]].
12. **Squash merge.** Never a merge commit, never a rebase merge — see [[#Squash Merge Only]].
13. **Delete the branch** after merge.

## Continuous Integration

The pipeline in `.github/workflows/ci.yml` runs on **every pull request**, and on **pushes to `main`** — the squashed commit, after merge. It must be **green before merge**.

A red pipeline is never merged and never overridden. If CI fails on something the change did not cause, fix the underlying flake or state the cause explicitly in the PR — do not re-run until it passes by luck. A test that passes intermittently is a defect, not noise.

CI runs three jobs:

- **web** — `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
- **api** — `pip install -e ".[dev]"`, `ruff check .`, `ruff format --check .`, `mypy app`, `pytest -ra --tb=short`
- **governance docs (sync check)** — `./scripts/sync-governance-docs.sh --check`

The API job runs against a throwaway PostgreSQL container with `PROJECTONE_REQUIRE_DATABASE_TESTS=1`, so the Row Level Security isolation tests cannot silently downgrade to skips.

**One full run per PR update.** `push` is scoped to `main` so that pushing to a PR branch does not also start a second run of the same pipeline against the same commit. Both would report the same required check names, and a pending context from *either* holds the gate — so a stuck duplicate blocks a merge whose PR run is already green. A branch pushed before its PR exists gets no run until the PR is opened: CI is a merge gate, and the PR is opened immediately after the first push.

Runs are superseded per pull request — a newer push cancels the older run for that PR, and never for another PR. Each push to `main` gets its own run, which a later push to `main` cannot cancel or replace through this workflow's concurrency configuration, because a commit already on `main` must be validated.

Every job declares an explicit `timeout-minutes` ceiling, so a hung step fails its job instead of holding a required check pending for GitHub's six-hour default.

> [!warning] A job that runs is not automatically a merge gate
> **Running in CI and being *required* by the `Protect main` ruleset are two different things.** A job that runs on every PR but is not listed as a required check can be red while the merge button stays green — it informs, it does not block.
>
> The ruleset requires **all three** checks — `web (lint, typecheck, test, build)`, `api (lint, format, typecheck, test)` and `governance docs (sync check)` — by those exact names, and requires a branch to be up to date with `main` before merging.
>
> **The names must match the ruleset exactly.** Renaming a job does not quietly drop its gate — it strands it: the ruleset keeps expecting a context nothing reports, and GitHub holds the PR waiting for a status that never arrives, blocking every merge until the ruleset is corrected. `apps/api/tests/test_ci_configuration.py` asserts each name still exists in the workflow.
>
> Adding a job to CI and adding it to the required-checks list are separate actions, and only the owner can perform the second. When adding a job intended as a gate, say explicitly that the ruleset still needs updating rather than assuming the two happened together.

## Manual Test Checklist

Automated tests do not cover everything, and the gap is widest exactly where it matters most — how a change actually behaves for a user.

**Where a change has user-visible behavior, the PR description carries a manual test checklist**, written as concrete steps with expected outcomes, and it is completed before merge. Each item names what was done and what was observed, not "works fine."

Include the states that are easiest to skip and most often broken: loading, empty, and error ([[CLAUDE|CLAUDE.md]] §11/§24), plus keyboard access for anything interactive.

A change with no user-visible surface — a refactor with identical behavior, a documentation edit, a CI configuration change — states that the checklist does not apply and why. Silence is not the same as "not applicable."

## Iterating on a Pull Request

A PR that needs changes — a red CI job, a reviewer's correction, a manual test that failed — is fixed by **pushing additional commits to the branch**.

**Never rewrite a pushed commit.** No `--amend`, no interactive rebase, no force-push over history that has been published and that a reviewer may already have read ([[CLAUDE|CLAUDE.md]] §20). A reviewer returning to a PR must find their comments still anchored to the code they described; rewriting history detaches them and quietly discards the review record.

This costs nothing in the permanent history, because the PR is squash-merged ([[#Squash Merge Only]]) — every intermediate commit collapses into one. **Branch tidiness is not a reason to rewrite anything.**

**Scope discipline still applies.** A correction addresses the specific failure or comment. Review is not an invitation to widen the change, and an issue surfaced in review that lies outside the branch's purpose is reported as its own task rather than folded in ([[CLAUDE|CLAUDE.md]] §29/§35).

## Owner Approval

Consequential changes require the project owner's **explicit approval** before merge. Claude and Codex may draft, implement, and open the PR; neither merges these on its own judgment. **Silence is never approval.**

The categories, per [[CLAUDE|CLAUDE.md]] §21:

- Database schema, migrations, and Row Level Security policies
- Authentication, authorization, and security controls
- Billing and payment logic
- Any public API contract, and any breaking change of any kind
- Infrastructure and deployment configuration
- AI/agent architecture, the Memory System, and AI cost governance controls
- Multi-tenancy boundaries

New architecture additionally requires an **Accepted** ADR before implementation begins ([[CLAUDE|CLAUDE.md]] §7). A `Draft` or `Review` ADR authorizes a scoped prototype, never production work.

**When uncertain whether a change qualifies, treat it as if it does.** Flag it in the PR description rather than deciding quietly that it is routine.

## Squash Merge Only

Every PR merges to `main` as a **single squashed commit**. Merge commits and rebase merges are not used.

**Why.** `main`'s history should read as a sequence of completed units of work — one line per task, one line per Build Plan step. That keeps the log legible as the [[Build Plan]] itself, makes any change revertable in one operation, and keeps the intermediate "fix typo" and "address review" commits out of a history that will be read far more often than it is written ([[CLAUDE|CLAUDE.md]] §38).

This is also what makes [[#Iterating on a Pull Request]] safe. Because the squash discards intermediate commits at merge time, a branch is free to carry as many as review requires — the constraint is on `main`, never on the working branch. The two rules depend on each other: without the squash, "never rewrite a pushed commit" would mean a messy permanent history, and without the freedom to add commits, review feedback would have nowhere to go.

The squashed commit message follows [[CLAUDE|CLAUDE.md]] §20 — atomic, explaining *why*. For a Build Plan step it names the step (`STEP-NN`) so history and plan stay traceable to each other.

Delete the branch after merge. A merged branch left in place is noise that makes the live branches harder to see.

## Starting From a Dirty Tree

Uncommitted changes at the start of a task mean a previous session left work in place — most often a `Blocked` Build Plan step, which is deliberately never committed ([[Execution Protocol#Blocked Steps Are Never Committed]]).

**Do not discard it and do not commit it.** Identify what the work is, confirm with the project owner whether to resume, stash, discard, or commit it, and act on that answer before starting anything new.

Where the owner's answer is to set it aside, `git stash push -u -m "<description>"` preserves it without committing a partial step. Work stashed this way is restored on the branch that owns it — a stashed Build Plan step resumes on its own `step-NN-*` branch cut from the updated `main`, not on whatever branch happens to be checked out next.

## Why This Exists

Before this protocol, work reached `main` directly from a local working tree. That is workable for exactly one contributor who never makes a mistake, and it fails the moment there are two — which ProjectOne now has, with Claude and OpenAI Codex both implementing against the same repository.

A protected `main` with a mandatory PR closes the failure modes that matter: nothing reaches the default branch without CI having run against it, no consequential change merges without the owner having seen it, two agents cannot silently overwrite each other's work, and every change on `main` has a reviewable record of what it was for. The cost is one branch and one PR per task. That is the cheapest insurance this project buys.

---

## Navigation

- **Previous:** [[Environment Setup]]
- **Next:** —
- **Parent:** [[Development MOC]]
- **Related Notes:** [[Execution Protocol]] · [[Task Workflow]] · [[AGENTS|AGENTS.md]] · [[CLAUDE|CLAUDE.md]] · [[Chapter 11 - Code Review Standards]]
