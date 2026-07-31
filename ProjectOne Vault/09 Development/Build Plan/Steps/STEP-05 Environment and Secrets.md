---
title: STEP-05 Environment and Secrets
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, security]
step_id: STEP-05
step_status: Not Started
---

# STEP-05 — Environment and Secrets

**Status:** Not Started

## Goal

Establish environment configuration conventions for both apps before any real secret exists — so the first credential added in STEP-07 lands in a system already built to protect it.

## Prerequisites

- [[STEP-04 API App Skeleton]] — `Done`

## Required Documentation

- [[CLAUDE|CLAUDE.md]] §28a — environment management, feature flags, config ownership
- [[Infrastructure]] — environment isolation model
- [[Chapter 09 - Security Standards]] — secret handling

## Tasks

1. Define `.env.example` for `apps/web` and `apps/api` — every required variable named, **every value a placeholder**. Committed; real `.env` files never are.
2. Implement typed, validated config loading in both apps. A missing or malformed required variable fails at startup with a clear message, not at first use.
3. Document the dev/staging/production split per [[CLAUDE|CLAUDE.md]] §28a — separate credentials, separate data, separate AI provider keys.
4. Establish the feature-flag mechanism: every flag has an owner, defaults off, and carries a removal date.
5. Confirm no environment-conditional business logic exists anywhere — configuration changes behavior, not code paths.

## Validation

- Both apps refuse to start with a required variable missing, and the error names the variable.
- `git status` shows no `.env` file as trackable.
- No `.env.example` value is a real credential (inspect every line).
- `grep` for `NODE_ENV ===` / `ENV ==` style branching returns no business-logic hits.

## Definition of Done

Both apps load validated config from environment variables, fail fast and legibly when misconfigured, and no real secret exists anywhere in the repository. The feature-flag convention is documented.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — security controls): flag for owner review.

---

## Navigation

- **Previous:** [[STEP-04 API App Skeleton]]
- **Next:** [[STEP-06 Continuous Integration]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Infrastructure]] · [[Chapter 09 - Security Standards]]
