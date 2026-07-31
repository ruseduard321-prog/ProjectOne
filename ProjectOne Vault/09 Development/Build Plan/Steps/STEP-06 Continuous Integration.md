---
title: STEP-06 Continuous Integration
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, testing]
step_id: STEP-06
step_status: Not Started
---

# STEP-06 — Continuous Integration

**Status:** Not Started

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
3. Jobs for `apps/api`: install, lint, type-check, test.
4. Configure the test runners for both apps. An empty suite must **pass**, not error on "no tests found" — otherwise the pipeline is red from day one and everyone learns to ignore it.
5. Add one trivial passing test per app to prove the runner actually executes.
6. Ensure CI never has access to production secrets; use repository secrets scoped to non-production only.

## Validation

- A push triggers the workflow and it completes green.
- Deliberately breaking a type locally causes the type-check job to fail (verify the pipeline can actually go red, then revert).
- Both trivial tests execute and report as passing in the CI log.

## Definition of Done

CI runs on every push, enforces lint + type-check + tests for both apps, is verified green on the current skeleton, and is verified capable of failing. No production secrets are reachable from CI.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — infrastructure/deployment configuration): flag for owner review.

---

## Navigation

- **Previous:** [[STEP-05 Environment and Secrets]]
- **Next:** [[STEP-07 Supabase Provisioning]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Chapter 11 - Code Review Standards]] · [[Testing Strategy]]
