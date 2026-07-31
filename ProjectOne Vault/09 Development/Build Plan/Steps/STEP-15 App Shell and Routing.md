---
title: STEP-15 App Shell and Routing
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, frontend]
step_id: STEP-15
step_status: Not Started
detail_level: outline
---

# STEP-15 — App Shell and Routing

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-14 Design System Tokens]], per [[Execution Protocol]].

## Goal

Base layout, navigation shell and routing structure — Server Components by default.

## Scope

The authenticated shell users land in. No feature screens. Loading, empty and error states defined from this first surface onward ([[CLAUDE|CLAUDE.md]] §11).

**Inherited from [[STEP-03 Web App Skeleton]]:** the root `error.tsx` boundary is still owed. STEP-03 established `loading` and `not-found` but could not add an error boundary — Next.js requires it to be a Client Component, which that step's validation forbade. This is the first step where client components are legitimate, so the error boundary lands here ([[Chapter 05 - NextJS Architecture]] §5.9).

## Prerequisites

- [[STEP-14 Design System Tokens]] — `Done`

## Required Documentation

- [[Frontend Architecture]]
- [[Chapter 05 - NextJS Architecture]]
- [[Design System]] §10

## Tasks

Not yet expanded. [[STEP-14 Design System Tokens]] writes this section, when the surrounding code exists and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-14 Design System Tokens]]
- **Next:** [[STEP-16 Sign Up and Sign In UI]]
- **Parent:** [[Build Plan]]
