---
title: STEP-01 Repository Bootstrap
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step]
step_id: STEP-01
step_status: Done
---

# STEP-01 — Repository Bootstrap

**Status:** Done

## Goal

Turn the project root into a version-controlled repository with the canonical folder skeleton, so every later step has a correct place to put files.

## Prerequisites

None. This is the first step.

## Required Documentation

- [[Chapter 02 - Repository Architecture]] — the folder structure and ownership rules
- [[CLAUDE|CLAUDE.md]] §8–9 — repository rules and folder structure

## Tasks

1. Initialize git in `D:\ProjectOne ProjectBible` (currently not a repository).
2. Create the top-level skeleton: `apps/`, `packages/`, `infrastructure/`, `docs/`, `scripts/`, `.github/`.
3. Write a root `README.md` — what ProjectOne is, and a pointer to `ProjectOne Vault/` as the source of truth.
4. Write `.gitignore` covering Node, Python, environment files, editor and OS artifacts. `.env*` must be ignored from the first commit — a secret committed once is committed forever ([[CLAUDE|CLAUDE.md]] §16).
5. Write `docs/README.md` linking back to the Obsidian Vault per [[Chapter 02 - Repository Architecture]] §2.6, so `docs/` never becomes a competing source of truth.
6. Make the initial commit.

## Validation

- `git status` runs and reports a clean tree.
- `git log` shows exactly one commit.
- All six directories exist.
- A file named `.env` in the root is ignored by git (verify with `git check-ignore -v .env`).

## Definition of Done

The repository exists, the skeleton matches [[Chapter 02 - Repository Architecture]], `.env` is provably ignored, and one clean initial commit is in history. The vault's `ProjectOne Vault/` directory is tracked — it is part of the product, not scratch work.

---

## Navigation

- **Previous:** [[Execution Protocol]]
- **Next:** [[STEP-02 Stack Confirmation ADR]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Chapter 02 - Repository Architecture]]
