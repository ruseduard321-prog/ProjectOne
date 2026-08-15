---
title: STEP-26 Product Design System Foundation
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, design, frontend]
step_id: STEP-26
step_status: Not Started
detail_level: full
phase: "Design Foundation"
---

# STEP-26 — Product Design System Foundation

**Status:** Not Started
**Phase:** Design Foundation — The shared visual and interaction system, established once against the surfaces that actually exist.
**Detail level:** full — this is the next step and is written at full detail.

## Objective

Decide the product's visual and interaction language once, and record it in [[Design System]] as tokens, rules and component contracts.

## Why This Step Exists Now

Every screen built from here inherits it. Deciding it once, now, is what stops each new domain inventing its own spacing scale and its own error state. It is also the only design work that can be done honestly today: the surfaces it covers all exist.

## Dependencies

- [[STEP-25a Foundation Remediation]] — `Done`

## Scope

- **Visual direction** — the owner-approved ivory canvas, matte-black navigation, vermilion accent and editorial typography, written as rules rather than adjectives.
- **Design tokens** — colour, type scale, weight, radius, elevation as token values.
- **Typography** — families, scale and hierarchy.
- **Spacing and layout rules** — one scale, applied consistently.
- **Navigation conventions** — structure, states and behaviour.
- **Shared component contracts** — the reusable set, each with a defined public interface.
- **Accessibility rules** — contrast, focus, keyboard order and semantics as system-level rules, carrying forward the accessibility findings in [[Foundation Audit Findings]].
- **Responsive behaviour** — breakpoints and collapse rules, stated rather than improvised per screen.
- **Loading, empty, error and success states** — defined as a system, since [[CLAUDE|CLAUDE.md]] §11 requires them of every async surface and a per-screen answer produces per-screen drift.

### Approved visual direction

Recorded by owner decision on 2026-08-14 and **carried forward unchanged** from the superseded [[STEP-26 Product Design System and Screen Blueprints]]. Binding on this step's output:

- Warm ivory/cream canvas.
- Matte-black navigation.
- Burnt-orange / vermilion primary accent.
- Editorial typography.
- Cinematic production cues — film-production language and imagery over generic SaaS iconography.
- **No** generic blue/purple AI gradients.
- **No** glassmorphism-heavy or generic KPI-dashboard design.

The product must read as premium creative-production software, not as an admin panel.

This direction **supersedes** the dark-interface visual rules previously recorded in [[Design Backlog and UI Vision]].

### Reference image

The owner-approved concept reference, supplied on 2026-08-14:

![[ProjectOne_Product_Design_Direction_v1.0.png]]

It is a **concept, not a specification.** The workspace name, projects, campaign copy, thumbnails, spend figures and activity entries are illustrative and constrain nothing.

What it *is* authoritative about is the visual language: the ivory canvas against matte-black navigation, the vermilion accent used sparingly on the primary action, the editorial serif paired with a plain UI sans, and the film-production cues that carry the product's identity.

Two cautions carry forward:

- **It depicts navigation and surfaces that do not exist** — Studio, Automations, notifications, a "Build campaign" composer. This step designs the *system*, not those screens; several of them become real later in this plan and are blueprinted in [[STEP-79 Domain Screen Blueprints]].
- **Where the image and the written direction disagree, the written direction wins.** Text survives re-export and recolouring; a screenshot does not.

## Out of Scope

- **No screen blueprints for domains that do not exist.** Video Generation, Analytics, Publishing, Billing and every other future domain are excluded by owner decision — each domain's surface is designed in its own phase, once its behaviour is known.
- No application styling is implemented and no page is rebuilt. The product-wide rebuild is [[STEP-80 Product-wide UI Rebuild]].
- No new shared component is built for a screen that does not exist yet.

## Surfaces Affected

**Frontend:** [[Design System]], token definitions, shared component contracts. **Backend / database / infrastructure:** none.

## Required Tests and Proofs

- Token set is internally consistent — no colour, spacing or type value appears in a rule without being a token.
- Contrast ratios meet WCAG AA, measured rather than asserted.
- Every shared component contract states its loading, empty and error states.
- Accessibility findings carried forward from [[Foundation Audit Findings]] are addressed at system level.

## Definition of Done

[[Design System]] carries the complete approved visual language — tokens, typography, spacing, navigation, component contracts, accessibility and responsive rules, and the four async states — with the owner's approval recorded. No application code changes.

## Risks and Governance Gates

**Owner approval gate** — the visual direction is the owner's decision, not Claude's. **ADR checkpoint:** if this changes foundational token values or shared component contracts that other code is built against, an ADR must reach `Accepted` before any step consumes it ([[CLAUDE|CLAUDE.md]] §7/§39).

## Audit Gaps Closed

Design system (tokens) — *Foundation / Partial*

---

## Navigation

- **Previous:** [[STEP-25a Foundation Remediation]]
- **Next:** [[STEP-27 Storage Provider Abstraction]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
