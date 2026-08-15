---
title: STEP-56 Script Review and Editing UI
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, agents]
step_id: STEP-56
step_status: Not Started
detail_level: outline
phase: "Content Intelligence"
---

# STEP-56 — Script Review and Editing UI

**Status:** Not Started
**Phase:** Content Intelligence — The first real agent chain: research and script, producing content worth generating media for.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let a user read, edit and approve a generated script before anything expensive is generated from it.

## Why This Step Exists Now

[[Video Generation]]'s user control section requires preview, edit and approval. Reviewing the script is also the cheapest possible place to catch a bad direction — every downstream step costs materially more.

## Dependencies

- [[STEP-55 Script Agent]]
- [[STEP-26 Product Design System Foundation]]

## Scope

- Script display by segment.
- Per-segment editing.
- Approval that releases the workflow to continue, using the existing approval gate.
- All four async states.

## Out of Scope

- No collaborative or real-time editing.
- No version history beyond what the asset model provides.

## Surfaces Affected

**Frontend:** script review surface. **Backend:** script update routes.

## Required Tests and Proofs

- An edit persists and is what the next step consumes, proven end to end.
- Approval releases exactly one gated step, consistent with STEP-22's model.
- Accessibility on the editing surface.
- Concurrent edits do not silently overwrite.

## Definition of Done

A user reviews, edits per segment and approves a script, and the approved version is provably what downstream steps consume.

## Risks and Governance Gates

This is the product's first real approval UX for expensive work. A confusing approval here causes either wasted spend or blocked workflows.

## Audit Gaps Closed

[[Video Generation]] user control — preview, edit, approve

---

## Navigation

- **Previous:** [[STEP-55 Script Agent]]
- **Next:** [[STEP-57 Media Generation Agent]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
