---
title: STEP-45 Memory Retrieval
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-45
step_status: Not Started
detail_level: outline
phase: "Context and Memory"
---

# STEP-45 — Memory Retrieval

**Status:** Not Started
**Phase:** Context and Memory — Shared context assembly and the five-scope Memory System, with the user controls [[CLAUDE|CLAUDE.md]] §15 requires of it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Retrieve memory by relevance rather than recency, and inject it through the Context Manager.

## Why This Step Exists Now

[[Memory System]]'s retrieval flow is Context Detection then Relevant Memory Retrieval. With the schema and embeddings in place, this is the step that makes memory useful instead of merely stored.

## Dependencies

- [[STEP-44 Memory Schema and Scopes]]
- [[STEP-43 Shared Context Manager]]

## Scope

- Relevance retrieval across scopes using embeddings.
- Scope precedence rules — which scope wins when several are relevant.
- Bounded injection: retrieved memory counts against the same context budget as history ([[CLAUDE|CLAUDE.md]] 15a).
- Retrieval decisions logged so a surprising answer is explainable.

## Out of Scope

- No automatic memory writing — the next step.
- No user controls yet.

## Surfaces Affected

**Backend:** retrieval service, Context Manager integration.

## Required Tests and Proofs

- Retrieval never crosses a workspace boundary, proven directly.
- Injected context stays inside its budget.
- Retrieval is deterministic for a fixed store and query.
- A retrieval decision is reconstructable from logs.

## Definition of Done

Relevant memory is retrieved across scopes, bounded, tenant-isolated and observable, and reaches the model through the Context Manager.

## Risks and Governance Gates

**Critical** — AI architecture and a cross-scope data path. A retrieval bug here surfaces one user's context inside another's conversation, which is the worst failure mode in the product.

## Audit Gaps Closed

**Memory retrieval flow** — *Missing, P1, no step*

---

## Navigation

- **Previous:** [[STEP-44 Memory Schema and Scopes]]
- **Next:** [[STEP-46 Memory Update Policies]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
