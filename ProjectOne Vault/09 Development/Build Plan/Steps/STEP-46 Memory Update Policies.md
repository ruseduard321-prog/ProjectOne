---
title: STEP-46 Memory Update Policies
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-46
step_status: Not Started
detail_level: outline
phase: "Context and Memory"
---

# STEP-46 — Memory Update Policies

**Status:** Not Started
**Phase:** Context and Memory — Shared context assembly and the five-scope Memory System, with the user controls [[CLAUDE|CLAUDE.md]] §15 requires of it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Decide and enforce what is worth remembering, and write it.

## Why This Step Exists Now

[[Memory System]] requires storing only useful information. Without an explicit policy, memory becomes either an unbounded transcript archive or an empty table.

## Dependencies

- [[STEP-45 Memory Retrieval]]

## Scope

- Explicit write policies per scope — what qualifies, what does not.
- Extraction and summarisation into memory entries.
- Deduplication and supersession, so memory does not accumulate near-identical entries.
- Retention bounds per scope.

## Out of Scope

- No user-facing controls — the next step.
- No cross-workspace learning of any kind.

## Surfaces Affected

**Backend:** memory write service, extraction. **Database:** possible supersession columns.

## Required Tests and Proofs

- A trivial exchange does not produce a memory entry.
- Superseded facts do not both survive.
- Write policy is bounded — no unbounded growth per conversation.
- Extraction cost is metered if it uses an AI call.

## Definition of Done

Memory is written according to a stated per-scope policy, deduplicated, bounded, and metered where AI is involved.

## Risks and Governance Gates

**Critical** — AI architecture, and if extraction uses an AI call it is a new spend surface needing its own ceiling.

## Audit Gaps Closed

Memory update policies — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-45 Memory Retrieval]]
- **Next:** [[STEP-47 Memory Inspection and Control]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
