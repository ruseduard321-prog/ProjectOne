---
title: STEP-29 Asset Management UI
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-29
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-29 — Asset Management UI

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, notifications.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let a user upload, browse, preview and delete a project's assets from the product.

## Why This Step Exists Now

[[Dashboard]] lists *Upload Files* as a quick action and [[Projects]] requires assets to be organised and reviewable. Both have been unbuildable until now; with STEP-28 merged they become a screen.

## Dependencies

- [[STEP-28 Asset Upload and Download]]
- [[STEP-26 Product Design System Foundation]]

## Scope

- Upload control with progress and failure handling.
- Asset list per project, using the [[Design System]] contracts from STEP-26.
- Preview for the kinds that can be previewed; an honest fallback for those that cannot.
- Delete with confirmation.
- Loading, empty, error and success states as [[CLAUDE|CLAUDE.md]] §11 requires.

## Out of Scope

- No bulk operations, no folders, no tagging, no search.
- No inline editing of asset content.

## Surfaces Affected

**Frontend:** project asset surfaces and shared upload component. **Backend:** none beyond STEP-28's routes.

## Required Tests and Proofs

- Upload failure surfaces an actionable message rather than a silent no-op.
- All four async states render.
- Keyboard reachability and focus order on every interactive control.
- A preview of an unsupported kind degrades honestly instead of erroring.

## Definition of Done

A user can upload, see, preview and delete project assets, with every async state defined and accessibility preserved.

## Risks and Governance Gates

First real consumer of the STEP-26 component contracts. If they do not survive contact with a real screen, the finding belongs back in [[Design System]] rather than being worked around here.

## Audit Gaps Closed

Asset download / preview — *Missing, P1*; [[Dashboard]] Upload Files quick action

---

## Navigation

- **Previous:** [[STEP-28 Asset Upload and Download]]
- **Next:** [[STEP-30 Async Job Infrastructure]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
