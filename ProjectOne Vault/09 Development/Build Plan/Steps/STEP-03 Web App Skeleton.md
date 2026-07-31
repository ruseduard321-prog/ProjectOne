---
title: STEP-03 Web App Skeleton
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, frontend]
step_id: STEP-03
step_status: Not Started
---

# STEP-03 — Web App Skeleton

**Status:** Not Started

## Goal

A runnable, empty Next.js application at `apps/web` — no features, just a confirmed-working dev server and a health route.

## Prerequisites

- [[STEP-02 Stack Confirmation ADR]] — `Done` **and ADR-001 `Accepted` by the owner**

## Required Documentation

- [[Chapter 05 - NextJS Architecture]] — App Router structure and conventions
- [[Chapter 03 - TypeScript Standards]] — strict mode configuration
- [[CLAUDE|CLAUDE.md]] §11 — Server Components by default

## Tasks

1. Scaffold Next.js (App Router) at `apps/web` with TypeScript.
2. Enable TypeScript **strict mode**, and confirm `any` is rejected by lint ([[CLAUDE|CLAUDE.md]] §35).
3. Configure Tailwind — tokens are not defined here, that is [[STEP-14 Design System Tokens]].
4. Add a root layout and one route rendering a static health indicator. Server Component — no `"use client"` anywhere in this step.
5. Configure lint and format per [[Chapter 05 - NextJS Architecture]].

## Validation

- Dev server starts and the health route renders in a real browser (observed, not assumed).
- `tsc --noEmit` passes with zero errors.
- Lint passes with zero errors.
- No `"use client"` directive exists in the app.

## Definition of Done

`apps/web` starts locally, serves a health route verified in a browser, type-checks clean under strict mode, and lints clean. No feature code, no client components, no design tokens yet.

---

## Navigation

- **Previous:** [[STEP-02 Stack Confirmation ADR]]
- **Next:** [[STEP-04 API App Skeleton]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Chapter 05 - NextJS Architecture]] · [[Frontend Architecture]]
