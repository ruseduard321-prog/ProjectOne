---
title: STEP-40 Tool Calling Capability
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-40
step_status: Not Started
detail_level: outline
phase: "AI Capability Expansion"
---

# STEP-40 — Tool Calling Capability

**Status:** Not Started
**Phase:** AI Capability Expansion — Turning a chat-only AI layer into one that can produce media and take actions, with every prompt versioned before the agents that depend on them are written.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let a model request an action, and let the platform execute it under the approval model.

## Why This Step Exists Now

[[AI Chat]] promises the user can create projects, manage them and trigger workflows conversationally. None of that is possible today: chat can only answer. This is the capability that closes the gap between the specification and the product.

## Dependencies

- [[STEP-36 AI Capability Contract Expansion]]

## Scope

- Tool definition and invocation on the provider contract, with adapters.
- A tool registry with explicit, typed schemas.
- **Every tool declares its approval class**, defaulting to *requires approval* per [[CLAUDE|CLAUDE.md]] 15 — read-only tools may be exempt with the reasoning documented.
- A bounded tool-execution loop with a hard ceiling on iterations.
- Full execution logging of every tool call and its outcome.

## Out of Scope

- No specific tools beyond the minimum needed to prove the loop — [[STEP-42 Chat Tool Actions]].
- No agent uses tools yet.

## Surfaces Affected

**Backend:** `app/ai/`, tool registry, execution loop. **Database:** tool-call logging.

## Required Tests and Proofs

- A tool requiring approval does not execute without one, proven by attempting it.
- The execution loop terminates at its ceiling rather than looping.
- A malformed tool request from the model fails safely.
- Every tool call is logged with its arguments and outcome.

## Definition of Done

A model can request a tool, the platform executes it only within the approval model, the loop is hard-bounded, and every call is observable.

## Risks and Governance Gates

**Critical, and the highest-risk step in this phase** — this is where an AI stops advising and starts acting. The approval default and the loop ceiling are the two controls that make it safe; both are 15/15a requirements and neither is optional.

## Audit Gaps Closed

**Tool calling** — *Missing, P0, no step*; [[AI Chat]] action capabilities — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-39 Embeddings Capability]]
- **Next:** [[STEP-41 Prompt Store and Versioning]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
