# ProjectOne

An AI Operating System for content businesses.

ProjectOne unifies ideation, script writing, media generation, editing, publishing, analytics
and automation into one coherent platform — not a bundle of disconnected tools wearing the same
logo. The goal is that a creator can run an entire content business from a single place, with the
AI doing the repetitive work and the human keeping every creative decision.

**North Star metric:** hours of creator work saved per active customer.

## Source of Truth

This repository's documentation lives in the **ProjectOne Obsidian Vault** at
[`ProjectOne Vault/`](ProjectOne%20Vault/). The vault — not memory, not a prior conversation, not
this README — is the authoritative record of what ProjectOne is, how it is built, and why.

Start at [`ProjectOne Vault/01 Claude OS/Start Here.md`](ProjectOne%20Vault/01%20Claude%20OS/Start%20Here.md),
then [`ProjectOne Vault/02 Home/Home.md`](ProjectOne%20Vault/02%20Home/Home.md).

Key entry points inside the vault:

| Document | Purpose |
|---|---|
| `01 Claude OS/` | How to work in this vault — discovery, reading priority, task workflow |
| `03 Project Bible/` | Product specification: vision, principles, features |
| `04 Engineering Handbook/` | Binding engineering standards, Chapters 1–11 |
| `08 ADR/` | Architecture Decision Records |
| `09 Development/Build Plan/` | The step-by-step execution plan, from empty repo to private beta and commercial readiness — authoritative for what is done and what comes next |

Two root files tell coding agents how to work in this codebase, one per agent:

| File | Read by | Canonical source |
|---|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Claude Code | [`ProjectOne Vault/00 Governance/CLAUDE.md`](ProjectOne%20Vault/00%20Governance/CLAUDE.md) |
| [`AGENTS.md`](AGENTS.md) | OpenAI Codex | [`ProjectOne Vault/00 Governance/AGENTS.md`](ProjectOne%20Vault/00%20Governance/AGENTS.md) |

**Both are generated.** Edit the canonical source, then regenerate —
`./scripts/sync-governance-docs.sh` on macOS/Linux/Git Bash, or
`.\scripts\sync-governance-docs.ps1` on Windows PowerShell. Never edit a root copy directly; CI
fails when one is stale.

`CLAUDE.md` is the full constitution. `AGENTS.md` is a concise adapter that points Codex at the same
canonical sources — it deliberately does not restate the constitution.

## Contributing

`main` is protected and is never modified directly. Every change — including a one-line
documentation fix — reaches it through a branch and a Pull Request with green CI, squash-merged.
See [`Branch and Pull Request Workflow`](ProjectOne%20Vault/09%20Development/Branch%20and%20Pull%20Request%20Workflow.md).

## Repository Structure

```
projectone/
├── apps/              # executable applications (frontend, backend, future workers)
├── packages/          # reusable, framework-agnostic shared code
├── infrastructure/    # deployment config, Docker, CI/CD, monitoring, secrets templates
├── docs/              # pointer to the vault — see docs/README.md
├── scripts/           # deterministic, idempotent automation scripts
├── .github/           # CI/CD workflows and repository configuration
└── ProjectOne Vault/  # the Obsidian vault — single source of truth
```

Dependencies always flow inward: applications depend on shared packages; shared packages never
depend on applications. Circular dependencies are prohibited. See
[`Chapter 02 - Repository Architecture`](ProjectOne%20Vault/04%20Engineering%20Handbook/Chapter%2002%20-%20Repository%20Architecture.md).

## Status

Pre-alpha — no release has shipped yet. The first will be a private, invite-only beta.

The foundation is built and running. Both applications exist and build clean: authentication,
workspace multi-tenancy enforced by Row Level Security, role-based authorization, a
provider-agnostic AI router with cost governance, AI Chat, Projects, a Dashboard, a minimum
workflow engine and a vendor-neutral storage abstraction. Every change runs through CI — lint,
type-check, tests and build for both apps, plus colour-contrast, migration-reversal and
backup-restore verification.

Progress is tracked step by step in
[`Build Plan`](ProjectOne%20Vault/09%20Development/Build%20Plan/Build%20Plan.md), which is the
source of truth for what is complete and what comes next.
