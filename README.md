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
| `09 Development/Build Plan/` | The 26-step execution plan from empty repo to first release |

[`CLAUDE.md`](CLAUDE.md) at the repository root is the operating manual governing how Claude works
in this codebase.

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

Pre-alpha. No application code exists yet — the repository skeleton and documentation are in place
and the build is executing STEP-01 onward of
[`Build Plan`](ProjectOne%20Vault/09%20Development/Build%20Plan/Build%20Plan.md).
