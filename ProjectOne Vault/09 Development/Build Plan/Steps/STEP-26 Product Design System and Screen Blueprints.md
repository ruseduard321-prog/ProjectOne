---
title: STEP-26 Product Design System and Screen Blueprints (Superseded)
category: Development/Build Step
status: superseded
version: "2.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, superseded, history]
step_status: Superseded
detail_level: historical
superseded_by: "[[STEP-26 Product Design System Foundation]]"
---

# STEP-26 Product Design System and Screen Blueprints (Superseded)

> [!warning] Superseded — kept as history, binding on nothing
> This outline was replaced by owner decision on 2026-08-15, following the [[Product Coverage Audit]]. It is **not** an executable step and holds no status in the [[Build Plan]].
>
> **Successor:** [[STEP-26 Product Design System Foundation]]

## Why This Was Superseded

This outline planned a single step covering **both** the shared design system **and** an approved screen blueprint for every existing application page.

**What changed.** The [[Product Coverage Audit]] established that most of the product does not exist yet: 24 capabilities Missing, whole domains — Video Generation, Analytics, Publishing, Billing — with no implementation at all. Blueprinting those surfaces now would design against a specification rather than a product.

**The owner's decision on 2026-08-15** split this outline in two:

- **[[STEP-26 Product Design System Foundation]]** keeps the number and the design-system half — tokens, typography, spacing, navigation, shared component contracts, accessibility, responsive rules, the four async states and the approved visual direction. It is restricted to the common foundation and the surfaces that genuinely exist today.
- **[[STEP-79 Domain Screen Blueprints]]** takes the blueprint half, and runs once the domains it would design actually exist.

**What did not change.** The approved visual direction — ivory canvas, matte-black navigation, vermilion accent, editorial typography, cinematic production cues, no generic blue/purple AI gradients — carries forward unchanged into [[STEP-26 Product Design System Foundation]], along with the owner-approved reference image and the caution that where image and written direction disagree, the written direction wins.

The ADR checkpoint carries forward too: changing foundational token values or shared component contracts requires an ADR reaching `Accepted` before any step consumes them.

---

## What the Outline Said

The original outline is preserved below, unedited, so the earlier reasoning stays readable. **Nothing in it binds current work** — where it disagrees with the successor step, the successor wins.

<details>
<summary>Original outline (2026-08-14)</summary>


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

- **Previous:** [[STEP-25a Foundation Remediation]]
- **Next:** [[STEP-27 Product-wide UI Rebuild]]
- **Parent:** [[Build Plan]]

</details>

---

## Navigation

- **Parent:** [[Build Plan]]
- **Related Notes:** [[STEP-26 Product Design System Foundation]] · [[Product Coverage Audit]]
