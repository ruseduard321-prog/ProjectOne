---
title: STEP-02 Stack Confirmation ADR
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, architecture]
step_id: STEP-02
step_status: Not Started
---

# STEP-02 — Stack Confirmation ADR

**Status:** Not Started

## Goal

Record the technology stack as a formal, owner-accepted architectural decision — the first entry in `08 ADR/`, which is currently empty.

## Prerequisites

- [[STEP-01 Repository Bootstrap]] — `Done`

## Required Documentation

- [[ADR Template]] — the required format
- [[CLAUDE|CLAUDE.md]] §7 (ADR lifecycle) and §10 (technology stack table)
- [[Frontend Architecture]] · [[Backend Architecture]] · [[Database Architecture]] — what the stack must support

## Tasks

1. Write `08 ADR/ADR-001 Technology Stack.md` using [[ADR Template]].
2. State the decision: Next.js App Router + React + TypeScript strict for frontend, FastAPI for backend, Supabase/PostgreSQL for database, Tailwind + [[Design System]] for styling.
3. Record the context and the **alternatives rejected, with reasons** — an ADR without rejected alternatives is a announcement, not a decision ([[CLAUDE|CLAUDE.md]] §6 step 4).
4. Record consequences, explicitly including provider-independence obligations from [[CLAUDE|CLAUDE.md]] §7.
5. Set status `Review` and add the ADR to any relevant index/MOC.

## Validation

- The ADR file exists, follows [[ADR Template]]'s structure, and every section is filled.
- Its stack matches [[CLAUDE|CLAUDE.md]] §10 exactly — any divergence is a conflict to raise, not to write in silently.
- At least two rejected alternatives are named with reasoning.

## Definition of Done

ADR-001 exists at status `Review` and is presented to the project owner for acceptance.

**Owner approval gate.** Per [[CLAUDE|CLAUDE.md]] §7, implementation of later steps may not begin until this ADR is `Accepted`. Claude marks this step `Done` when the ADR is written and presented — then **stops and waits**. STEP-03 does not start on an ADR still in `Review`.

---

## Navigation

- **Previous:** [[STEP-01 Repository Bootstrap]]
- **Next:** [[STEP-03 Web App Skeleton]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[ADR Template]] · [[CLAUDE|CLAUDE.md]]
