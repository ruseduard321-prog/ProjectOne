---
title: STEP-44 Memory Schema and Scopes
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-44
step_status: Not Started
detail_level: outline
phase: "Context and Memory"
---

# STEP-44 — Memory Schema and Scopes

**Status:** Not Started
**Phase:** Context and Memory — Shared context assembly and the five-scope Memory System, with the user controls [[CLAUDE|CLAUDE.md]] §15 requires of it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Create the memory store with the five scopes [[Memory System]] specifies.

## Why This Step Exists Now

[[Database Architecture]] names AI Memory as a core domain with no schema. The audit records four of five scopes as entirely missing and the fifth as a bounded replay window rather than memory.

## Dependencies

- [[STEP-39 Embeddings Capability]]
- [[STEP-43 Shared Context Manager]]

## Scope

- Memory schema covering conversation, project, channel, workspace and user-preference scopes, with RLS in the creating migration.
- Scope isolation: workspace memory never leaks across workspaces, per [[CLAUDE|CLAUDE.md]] 16.
- Embedding storage attached to memory entries.
- Erasure registration for every scope.

## Out of Scope

- No retrieval policy — [[STEP-45 Memory Retrieval]].
- No write policy — [[STEP-46 Memory Update Policies]].
- No UI — [[STEP-47 Memory Inspection and Control]].
- Channel-scope rows are unreachable until channels exist, which is expected.

## Surfaces Affected

**Database:** memory tables with RLS. **Backend:** repository and service.

## Required Tests and Proofs

- Every scope is tenant-isolated, proven through the route layer.
- Erasure removes all five scopes — the audit names this as a 16 obligation.
- Scope boundaries hold: project memory does not surface in another project's context.

## Definition of Done

All five memory scopes exist with RLS, isolation proven per scope, and erasure covering every one.

## Risks and Governance Gates

**Critical** — new tenant-scoped schema, RLS, and a store carrying inferred personal data with direct [[Privacy and Data Protection]] implications.

## Audit Gaps Closed

**Memory System** — Project, Channel, Workspace and User Preference scopes all *Missing, P1/P2, no step*

---

## Navigation

- **Previous:** [[STEP-43 Shared Context Manager]]
- **Next:** [[STEP-45 Memory Retrieval]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
