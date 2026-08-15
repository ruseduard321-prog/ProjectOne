---
title: STEP-78 Prompt Store and Versioning
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, automation, backend]
step_id: STEP-78
step_status: Not Started
detail_level: outline
phase: "Automation"
---

# STEP-78 — Prompt Store and Versioning

**Status:** Not Started
**Phase:** Automation — Scheduled and triggered execution, once there is something worth automating.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Move system prompts out of inline constants into a versioned, reviewable store.

## Why This Step Exists Now

[[CLAUDE|CLAUDE.md]] §31 requires every system prompt to be versioned and documented in `06 AI/Prompts/`, and [[AI Architecture]] names a Prompt Engine as a core component. Prompts are currently inline string constants across chat and every agent — by this point there are many, and the drift is real.

## Dependencies

- [[STEP-77 Workspace and Collaboration Foundations]]

## Scope

- A prompt store with versioning.
- Existing prompts migrated out of inline constants.
- A prompt change treated as a behaviour change to the feature it powers, per 31.
- Vault documentation in `06 AI/Prompts/` using [[Prompt Template]].

## Out of Scope

- No user-editable prompts.
- No prompt A/B testing.

## Surfaces Affected

**Backend:** prompt store. **Documentation:** `06 AI/Prompts/`.

## Required Tests and Proofs

- Every shipped prompt is versioned and retrievable.
- Behaviour is unchanged by the migration, proven by the existing suites.
- A prompt change is traceable to the version that produced a given output.

## Definition of Done

Every system prompt lives in a versioned store, documented in the vault, with behaviour provably unchanged by the migration.

## Risks and Governance Gates

A refactor of behaviour-defining strings. The existing agent and chat suites are the control against silent drift.

## Audit Gaps Closed

**Prompt Engine / versioned prompt store** — *Foundation / Partial, P2, no step*

---

## Navigation

- **Previous:** [[STEP-77 Workspace and Collaboration Foundations]]
- **Next:** [[STEP-79 Domain Screen Blueprints]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
