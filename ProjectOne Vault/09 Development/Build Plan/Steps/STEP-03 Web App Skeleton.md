---
title: STEP-03 Web App Skeleton
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, frontend]
step_id: STEP-03
step_status: Done
---

# STEP-03 — Web App Skeleton

**Status:** Done

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

## Outcome

Next.js **16.2.12** with React 19.2.4, TypeScript strict, Tailwind v4 and ESLint 9 at `apps/web`. Routes: `/` (placeholder), `/health` (static indicator), plus root `loading` and `not-found` states. All three prerender as static — the production build reports zero client JavaScript.

Notes for later steps:

- **`error.tsx` is deliberately absent.** [[Chapter 05 - NextJS Architecture]] §5.9 wants loading, error and not-found states on every route, but Next.js error boundaries are inherently Client Components (`'use client'` is required), which this step's Validation explicitly forbids. `loading` and `not-found` are in place; the error boundary is owed by [[STEP-15 App Shell and Routing]], the first step where client components are legitimate. **This is a known, tracked gap, not an oversight.**
- **`next lint` no longer exists** in Next.js 16. Lint runs as `eslint . --max-warnings=0` via the `lint` script; a `typecheck` script (`tsc --noEmit`) was added alongside it so [[STEP-06 Continuous Integration]] has a stable contract to call.
- **`any` is already an ESLint error** through `eslint-config-next`'s TypeScript preset — verified by probe, no custom rule needed.
- The package is named `@projectone/web` in anticipation of the workspace layout.
- `create-next-app` emits its own `CLAUDE.md` and `AGENTS.md`; both were removed, since a second CLAUDE.md would contradict the single-canonical-source rule established for [[CLAUDE|CLAUDE.md]].

---

## Navigation

- **Previous:** [[STEP-02 Stack Confirmation ADR]]
- **Next:** [[STEP-04 API App Skeleton]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Chapter 05 - NextJS Architecture]] · [[Frontend Architecture]]
