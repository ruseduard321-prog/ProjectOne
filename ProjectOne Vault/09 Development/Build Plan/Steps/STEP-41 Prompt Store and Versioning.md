---
title: STEP-41 Prompt Store and Versioning
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-41
step_status: Not Started
detail_level: outline
phase: "AI Capability Expansion"
---

# STEP-41 — Prompt Store and Versioning

**Status:** Not Started
**Phase:** AI Capability Expansion — Turning a chat-only AI layer into one that can produce media and take actions, with every prompt versioned before the agents that depend on them are written.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Establish the versioned prompt store **before** the specialized agent chain is written, and migrate the prompts that already exist into it.

## Why This Step Exists Now

**Moved here by owner decision on 2026-08-15**, from a later position in the sequence. [[CLAUDE|CLAUDE.md]] §31 requires every system prompt to be versioned and documented, and [[AI Architecture]] names a Prompt Engine as a core component. Building Research, Script, Media, QA, Publishing, Analytics and Strategy agents against inline string constants and migrating them afterwards would be deliberately creating the drift §31 exists to prevent — so the store lands before the agents that will fill it, not after.

Only chat's and the planning agent's prompts exist today, which makes this the cheapest moment the migration will ever have.

## Dependencies

- [[STEP-40 Tool Calling Capability]]

## Scope

- A prompt store with versioning, and a retrieval interface every AI caller uses.
- The prompts that exist today — chat's system instruction and `PlanningAgent`'s — migrated out of inline constants.
- A prompt change treated as a behaviour change to the feature it powers, per [[CLAUDE|CLAUDE.md]] §31.
- Vault documentation in `06 AI/Prompts/`, so a shipped prompt is reviewable as code.
- **The convention every later agent follows**: an agent defines its prompt in the store, never inline.

## Out of Scope

- No user-editable prompts.
- No prompt A/B testing or evaluation harness.
- No new agent — this establishes the mechanism the agent phases will use.

## Surfaces Affected

**Backend:** prompt store. **Documentation:** `06 AI/Prompts/`.

## Required Tests and Proofs

- Every shipped prompt is versioned and retrievable from the store.
- Chat and planning behaviour is unchanged by the migration, proven by their existing suites passing untouched.
- A prompt change is traceable to the version that produced a given output.
- No inline system-prompt constant remains in the AI or workflow packages, asserted by test.

## Definition of Done

Every system prompt lives in a versioned store documented in the vault, existing behaviour is provably unchanged, and no inline system-prompt constant remains — so every agent built afterwards has a versioned home for its prompt from its first commit.

## Risks and Governance Gates

A refactor of behaviour-defining strings, with the existing chat and agent suites as the control against silent drift. The governance risk it removes is larger than the one it carries: without this, seven agents would each ship an unversioned prompt.

## Audit Gaps Closed

**Prompt Engine / versioned prompt store** — *Foundation / Partial, P2, no step*

---

## Navigation

- **Previous:** [[STEP-40 Tool Calling Capability]]
- **Next:** [[STEP-42 Chat Tool Actions]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
