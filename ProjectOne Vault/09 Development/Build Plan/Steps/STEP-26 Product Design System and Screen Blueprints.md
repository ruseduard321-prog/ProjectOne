---
title: STEP-26 Product Design System & Screen Blueprints
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-14
tags: [engineering, workflow, build-step, design, frontend]
step_id: STEP-26
step_status: Not Started
detail_level: outline
---

# STEP-26 — Product Design System & Screen Blueprints

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-25 Foundation Audit and Internal Readiness]], per [[Execution Protocol]].

## Goal

Decide the product's visual language once, in one place, and draw every screen against it — before any screen is rebuilt. This step produces an approved design system and a blueprint per page; it does **not** implement them. [[STEP-27 Product-wide UI Rebuild]] implements what this step approves.

The separation is the point: designing while implementing is how a product ends up with eleven variations of the same button.

## Scope

### Approved visual direction

Recorded here by owner decision on 2026-08-14, and binding on this step's output:

- Warm ivory/cream canvas.
- Matte-black navigation.
- Burnt-orange / vermilion primary accent.
- Editorial typography.
- Cinematic production cues — film-production language and imagery over generic SaaS iconography.
- **No** generic blue/purple AI gradients.
- **No** glassmorphism-heavy or generic KPI-dashboard design.

The product must read as premium creative-production software, not as an admin panel.

This direction **supersedes** the dark-interface visual rules previously recorded in [[Design Backlog and UI Vision]]. That note's superseded status is marked there rather than erased — the earlier direction remains readable as history.

### Deliverables

- **Canonical visual direction** — written into [[Design System]], which remains the single source of truth a component may be built against.
- **Design tokens and typography** — colour, type scale, weight and hierarchy as token values, not adjectives.
- **Layout and spacing system** — one scale, applied consistently.
- **Navigation** — structure, states and behaviour.
- **Shared components** — the reusable set, each with a defined contract.
- **Responsive rules** — breakpoints and collapse behaviour, stated rather than improvised per screen.
- **Accessibility rules** — contrast, focus, keyboard order and semantics as system-level rules, carrying forward the accessibility findings from [[STEP-25 Foundation Audit and Internal Readiness]].
- **Loading, empty, error and success states** — defined as a system, since [[CLAUDE|CLAUDE.md]] §11 requires every async surface to define them and a per-screen answer produces per-screen drift.
- **An approved screen blueprint for every existing application page** — every page that exists at the time this step runs, with no page left to be improvised during STEP-27.

### Reference image

The owner-approved concept reference, supplied on 2026-08-14:

![[ProjectOne_Product_Design_Direction_v1.0.png]]

It is a **concept, not a specification** — the same standing as the mockup in [[Design Backlog and UI Vision]]. The workspace name, projects, campaign copy, thumbnails, spend figures and activity entries are illustrative, and nothing in them constrains what any screen must contain.

What it *is* authoritative about is the visual language: the ivory canvas against matte-black navigation, the vermilion accent used sparingly on the primary action, the editorial serif paired with a plain UI sans, and the film-production cues (clapperboard, contact-sheet strip, taped-paper brief, duration badges) that carry the product's identity.

Two cautions for whoever draws the blueprints:

- **It depicts navigation and surfaces that do not exist** — Studio, Automations, notifications, a "Build campaign" composer. Blueprints are drawn for the pages the product *has* at the time this step runs, per the deliverable above. Anything else is a [[Roadmap]] question, not a design one.
- **Where the image and the written direction disagree, the written direction wins.** Text survives re-export and recolouring; a screenshot does not.

The textual direction above stands on its own and does not depend on this image.

### ADR checkpoint

**A real stop, not a formality.** If this step changes foundational design tokens or shared component contracts — the values and interfaces other code is built against — that is an architectural decision under [[CLAUDE|CLAUDE.md]] §7 and §39, and an ADR must be prepared and reach `Accepted` before [[STEP-27 Product-wide UI Rebuild]] begins. Restyling within existing token and component contracts does not require one.

Where it is unclear which side a change falls on, it resolves toward the ADR ([[CLAUDE|CLAUDE.md]] §21).

### Out of scope

No application styling is implemented in this step. No page is rebuilt. The output is documentation and approved blueprints.

## Prerequisites

- [[STEP-25 Foundation Audit and Internal Readiness]] — `Done`

## Required Documentation

- [[Design System]]
- [[Design Backlog and UI Vision]]
- [[Frontend Architecture]]
- [[Chapter 04 - React Standards]]

## Tasks

Not yet expanded. [[STEP-25 Foundation Audit and Internal Readiness]] writes this section, when the audit's findings are known and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-25 Foundation Audit and Internal Readiness]]
- **Next:** [[STEP-27 Product-wide UI Rebuild]]
- **Parent:** [[Build Plan]]
