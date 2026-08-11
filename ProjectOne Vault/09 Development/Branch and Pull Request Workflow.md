---
title: Branch and Pull Request Workflow
category: Development
status: stable
version: "1.0"
last_updated: 2026-08-11
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
5. **Commit.** Atomic, explaining *why* rather than restating the diff ([[CLAUDE|CLAUDE.md]] §20). A Build Plan step is exactly one commit ([[Execution Protocol#One Step One Commit]]).
6. **Push the branch** and open a **Pull Request into `main`**.
7. **CI must pass.** See [[#Continuous Integration]].
8. **Supply a manual test checklist** where the change has user-visible behavior, and complete it — see [[#Manual Test Checklist]].
9. **Resolve every review conversation.** An open thread blocks merge.
10. **Obtain owner approval** for consequential changes — see [[#Owner Approval]].
11. **Squash merge.** Never a merge commit, never a rebase merge — see [[#Squash Merge Only]].
12. **Delete the branch** after merge.

## Continuous Integration

The pipeline in `.github/workflows/ci.yml` runs on every push and every pull request. It must be **green before merge**.

A red pipeline is never merged and never overridden. If CI fails on something the change did not cause, fix the underlying flake or state the cause explicitly in the PR — do not re-run until it passes by luck. A test that passes intermittently is a defect, not noise.

CI runs, per application:

- **web** — `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
- **api** — `pip install -e ".[dev]"`, `ruff check .`, `ruff format --check .`, `mypy app`, `pytest -ra --tb=short`

The API job runs against a throwaway PostgreSQL container with `PROJECTONE_REQUIRE_DATABASE_TESTS=1`, so the Row Level Security isolation tests cannot silently downgrade to skips.

## Manual Test Checklist

Automated tests do not cover everything, and the gap is widest exactly where it matters most — how a change actually behaves for a user.

**Where a change has user-visible behavior, the PR description carries a manual test checklist**, written as concrete steps with expected outcomes, and it is completed before merge. Each item names what was done and what was observed, not "works fine."

Include the states that are easiest to skip and most often broken: loading, empty, and error ([[CLAUDE|CLAUDE.md]] §11/§24), plus keyboard access for anything interactive.

A change with no user-visible surface — a refactor with identical behavior, a documentation edit, a CI configuration change — states that the checklist does not apply and why. Silence is not the same as "not applicable."

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
