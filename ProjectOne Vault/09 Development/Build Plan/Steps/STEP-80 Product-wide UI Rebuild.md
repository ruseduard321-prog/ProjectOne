---
title: STEP-80 Product-wide UI Rebuild
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, design, frontend]
step_id: STEP-80
step_status: Not Started
detail_level: outline
phase: "Product UI Consolidation"
---

# STEP-80 — Product-wide UI Rebuild

**Status:** Not Started
**Phase:** Product UI Consolidation — The product-wide visual rebuild, run once the real product surface exists.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Implement the approved blueprints across the entire product in one consistent pass.

## Why This Step Exists Now

This is the former STEP-27, moved here by owner decision. Rebuilding before the product surface existed would have restyled a fraction of the product and left every later domain to drift again. One pass, once, when there is a whole product to make consistent.

## Dependencies

- [[STEP-79 Domain Screen Blueprints]]

## Scope

- Implement the approved design across every page and every state.
- Cover loading, empty, error and success on every async surface ([[CLAUDE|CLAUDE.md]] §11).
- Preserve existing functional behaviour exactly — this is a presentation change.
- **The design is not revised during implementation**: a wrong blueprint means stopping and updating STEP-79 with owner re-approval, not improvising.

## Out of Scope

- No behavioural change. No API, schema, auth or AI change.
- No new features.

## Surfaces Affected

**Frontend:** every page and shared component. **Backend:** none.

## Required Tests and Proofs

- Every existing behavioural test stays green, unmodified — a rebuild requiring deleted assertions changed behaviour.
- Every page renders all four async states.
- Accessibility: keyboard order, focus and contrast across the product.
- Responsive behaviour at every defined breakpoint.

## Definition of Done

Every page implements the approved design in every state, with all existing behavioural tests green and unmodified, and accessibility and responsive rules verified across the product.

## Risks and Governance Gates

Large surface area, low architectural risk. The binding rule is the no-redesign-during-implementation gate inherited from the former STEP-27, which is what makes the split worth having.

## Audit Gaps Closed

Design system application — completes the [[Design System]] rollout

---

## Navigation

- **Previous:** [[STEP-79 Domain Screen Blueprints]]
- **Next:** [[STEP-81 Billing Schema and Subscription Management]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
