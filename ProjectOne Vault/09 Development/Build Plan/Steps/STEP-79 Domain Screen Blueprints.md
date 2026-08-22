---
title: STEP-79 Domain Screen Blueprints
category: Development/Build Step
status: draft
version: "1.2"
last_updated: 2026-08-22
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

Validate the approved product-experience blueprint against the product as it then actually is, complete what is missing, and obtain owner approval for the final implementation set.

## Why This Step Exists Now

**This step's role narrowed by owner decision on 2026-08-22.** It was written when no product-wide design existed and its job was to originate blueprints from zero. A complete blueprint arrived at STEP-31 instead — see [[STEP-31a Product Experience Blueprint Alignment]] and [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] — and STEP-31a adopted its *shared foundation* while deliberately rebuilding no domain page.

What remains is the half a blueprint drawn ahead of the product cannot do for itself. That blueprint is a hypothesis about behaviour that did not exist when it was drawn; by this point in the plan the behaviour does exist, and the two must be reconciled deliberately rather than assumed to agree. This is still the design pass the owner's policy defers to the point where behaviour is known rather than imagined — it now begins from a preserved proposal instead of from nothing.

## Dependencies

- [[STEP-41 Prompt Store and Versioning]]

## Scope

- **Enumerate the real product as it then stands** — every surface that actually exists, including every domain built in P2 through P11.
- **Validate the preserved blueprint against real behaviour**, surface by surface, and record where the two disagree.
- **Complete the missing states and screens** the blueprint does not cover, or covers against behaviour that turned out differently.
- **Reconcile deviations deliberately** — each one is an explicit decision to follow the blueprint or to depart from it, with the reason recorded. Neither silent adoption nor silent departure.
- Blueprints drawn against the STEP-26 tokens and component contracts, plus the shared contracts STEP-31a established under ADR-007.
- Any component gaps found are added to [[Design System]] rather than improvised per screen.
- **Owner approval of the final implementation set**, which is what [[STEP-80 Product-wide UI Rebuild]] then implements.

## Out of Scope

- No implementation — that is the next step.
- No new visual direction; STEP-26's direction and ADR-003 stand, as extended by ADR-007.
- **No blueprint for a capability that still does not exist by then.** A domain the product never built is not blueprinted here either; it stays `Proposed` under ADR-007 Decision 3.
- No re-litigation of the shared foundation STEP-31a already established and the owner already accepted.

## Surfaces Affected

**Documentation:** [[Design System]] and blueprints. No code.

## Required Tests and Proofs

- Every existing surface has a blueprint — checked by enumeration against the routes that exist.
- Every preserved-blueprint surface is marked validated, revised or withdrawn against real behaviour; none is left unreconciled.
- Every blueprint uses only defined tokens and contracts.
- Accessibility and responsive rules are applied per blueprint.

## Definition of Done

Every existing product surface has an owner-approved blueprint consistent with the STEP-26 system and the ADR-007 contracts, every deviation from the preserved blueprint is a recorded decision rather than an accident, and any new component contracts are added to [[Design System]].

## Risks and Governance Gates

**Owner approval gate.** The risk this step manages is the one the owner's design policy names: blueprinting speculative domains. Everything blueprinted here is behaviour that already exists — **and that rule is what the preserved blueprint puts under pressure**, since it drew surfaces for domains that had not been built when it was drawn. Reconciling it against reality is this step's work; adopting it unreconciled would be the failure. A blueprint surface with no corresponding behaviour is withdrawn here, not implemented.

## Audit Gaps Closed

Deferred design surface from STEP-26's restricted scope

---

## Navigation

- **Previous:** [[STEP-78 Scheduled Publishing]]
- **Next:** [[STEP-80 Product-wide UI Rebuild]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]] · [[STEP-31a Product Experience Blueprint Alignment]] · [[ADR-007 Product Experience Blueprint Authority and Adoption Boundary]] · [[Design System]]
