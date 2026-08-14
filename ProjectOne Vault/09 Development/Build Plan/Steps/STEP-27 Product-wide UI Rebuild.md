---
title: STEP-27 Product-wide UI Rebuild
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-14
tags: [engineering, workflow, build-step, design, frontend]
step_id: STEP-27
step_status: Not Started
detail_level: outline
---

# STEP-27 — Product-wide UI Rebuild

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-26 Product Design System and Screen Blueprints]], per [[Execution Protocol]].

## Goal

Implement the design approved in [[STEP-26 Product Design System and Screen Blueprints]] across the entire product, in one consistent pass — every page, every state.

One pass rather than screen-by-screen is deliberate: a product restyled incrementally is a product that is inconsistent for the whole duration of the work, and consistency is the only reason to rebuild at all.

## Scope

- **Implement the complete approved design** — tokens, typography, spacing, navigation and shared components as [[STEP-26 Product Design System and Screen Blueprints]] specifies them.
- **Cover every existing page and every state** — including the loading, empty, error and success states that [[CLAUDE|CLAUDE.md]] §11 requires of every async surface. A page whose happy path is rebuilt and whose empty state is not is a page half-rebuilt.
- **Preserve existing functional behaviour.** This is a presentation change. Business logic, API contracts, authentication, AI routing, database schema and authorization behaviour are untouched ([[CLAUDE|CLAUDE.md]] §29/§35). Where the rebuild appears to require a behavioural change, that is a finding to surface, not a change to make quietly.

### The design is not revised during implementation

**Binding.** If implementation reveals that a blueprint is wrong, unbuildable, or worse than it looked on paper, the response is to **stop, update [[STEP-26 Product Design System and Screen Blueprints]], and obtain the owner's re-approval** — not to improvise a better design at the keyboard.

This is the rule that makes the STEP-26/STEP-27 split worth having. Redesigning during implementation reintroduces exactly the per-screen drift the split exists to prevent, and leaves the approved blueprint describing a product that no longer matches it ([[CLAUDE|CLAUDE.md]] §19).

### Regression protection

Existing behavioural tests are the safety net for "functional behaviour preserved" and must stay green throughout. A rebuild that requires deleting assertions about behaviour is a rebuild that changed behaviour.

## Prerequisites

- [[STEP-26 Product Design System and Screen Blueprints]] — `Done`, with its ADR checkpoint cleared where one was required.

## Required Documentation

- [[Design System]]
- [[Frontend Architecture]]
- [[Chapter 04 - React Standards]]
- [[Chapter 05 - NextJS Architecture]]

## Tasks

Not yet expanded. [[STEP-26 Product Design System and Screen Blueprints]] writes this section, when the approved blueprints exist and the tasks can name real screens rather than imagined ones.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-26 Product Design System and Screen Blueprints]]
- **Next:** [[STEP-28 Full Product Verification Polish and Hardening]]
- **Parent:** [[Build Plan]]
