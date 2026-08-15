---
title: STEP-79 Domain Screen Blueprints
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, design, frontend]
step_id: STEP-79
step_status: Not Started
detail_level: outline
phase: "Product UI Consolidation"
---

# STEP-79 — Domain Screen Blueprints

**Status:** Not Started
**Phase:** Product UI Consolidation — The product-wide visual rebuild, run once the real product surface exists.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Design the screen blueprints for every product surface that now exists, against the STEP-26 design system.

## Why This Step Exists Now

STEP-26 deliberately excluded blueprints for domains that did not exist. They exist now. This is the design pass the owner's policy defers to the point where behaviour is known rather than imagined.

## Dependencies

- [[STEP-78 Prompt Store and Versioning]]

## Scope

- A blueprint per existing application surface, including every domain built in P2 through P11.
- Blueprints drawn against the STEP-26 tokens and component contracts.
- Any component gaps found are added to [[Design System]] rather than improvised per screen.
- Owner approval of the blueprint set.

## Out of Scope

- No implementation — that is the next step.
- No new visual direction; STEP-26's direction stands.

## Surfaces Affected

**Documentation:** [[Design System]] and blueprints. No code.

## Required Tests and Proofs

- Every existing surface has a blueprint — checked by enumeration against the routes that exist.
- Every blueprint uses only defined tokens and contracts.
- Accessibility and responsive rules are applied per blueprint.

## Definition of Done

Every existing product surface has an owner-approved blueprint consistent with the STEP-26 system, with any new component contracts added to [[Design System]].

## Risks and Governance Gates

**Owner approval gate.** The risk this step manages is the one the owner's design policy names: blueprinting speculative domains. Everything blueprinted here is behaviour that already exists.

## Audit Gaps Closed

Deferred design surface from STEP-26's restricted scope

---

## Navigation

- **Previous:** [[STEP-78 Prompt Store and Versioning]]
- **Next:** [[STEP-80 Product-wide UI Rebuild]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
