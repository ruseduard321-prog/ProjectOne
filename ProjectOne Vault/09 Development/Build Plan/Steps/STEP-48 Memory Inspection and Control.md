---
title: STEP-48 Memory Inspection and Control
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-48
step_status: Not Started
detail_level: outline
phase: "Context and Memory"
---

# STEP-48 — Memory Inspection and Control

**Status:** Not Started
**Phase:** Context and Memory — Shared context assembly and the five-scope Memory System, with the user controls CLAUDE.md §15 requires of it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let users see, edit, disable and delete everything the AI remembers about them.

## Why This Step Exists Now

Not a nicety: [[CLAUDE|CLAUDE.md]] §15 requires memory to be user-inspectable, editable and deletable, and [[Memory System]] states it must never hide what the AI remembers. Shipping memory without this is shipping a hidden store the constitution forbids.

## Dependencies

- [[STEP-47 Memory Update Policies]]
- [[STEP-26 Product Design System Foundation]]

## Scope

- A memory surface listing entries by scope.
- Edit and delete for individual entries.
- Disable memory per scope.
- Immediate effect: a deleted memory stops influencing the next turn, proven rather than assumed.

## Out of Scope

- No memory export as a separate feature — existing data export covers it.
- No bulk editing tools.

## Surfaces Affected

**Frontend:** memory management surface. **Backend:** read/update/delete routes.

## Required Tests and Proofs

- A deleted memory does not appear in the next turn's context, proven end to end.
- Disabling a scope stops both retrieval and writing for it.
- A user cannot read or edit another user's memory.
- All four async states render.

## Definition of Done

A user can inspect, edit, disable and delete memory by scope, with deletion provably affecting the very next AI turn.

## Risks and Governance Gates

**Critical** — privacy control surface and a direct 15 obligation. This step is what makes the Memory System compliant rather than merely functional.

## Audit Gaps Closed

**Memory inspection / edit / delete** — *Missing, P1, no step* — an explicit 15 requirement

---

## Navigation

- **Previous:** [[STEP-47 Memory Update Policies]]
- **Next:** [[STEP-49 Richer Chat Context]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
