---
title: STEP-04 API App Skeleton
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, backend]
step_id: STEP-04
step_status: Not Started
---

# STEP-04 — API App Skeleton

**Status:** Not Started

## Goal

A runnable, empty FastAPI application at `apps/api` with the layered structure in place — directories and boundaries, no business logic.

## Prerequisites

- [[STEP-03 Web App Skeleton]] — `Done`

## Required Documentation

- [[Chapter 06 - FastAPI Architecture]] — module layout and conventions
- [[Backend Architecture]] — the API → business logic → data access layering
- [[CLAUDE|CLAUDE.md]] §12 — routers validate and delegate, nothing else

## Tasks

1. Scaffold FastAPI at `apps/api` with a pinned Python dependency manifest.
2. Create the layer directories from [[Backend Architecture]]: `routers/`, `services/`, `repositories/`, `schemas/`, `core/`. Empty is correct here — the structure is the deliverable.
3. Add one `/health` router returning service status. It calls a service; even the trivial case establishes that routers never hold logic ([[CLAUDE|CLAUDE.md]] §12).
4. Set up dependency injection wiring per [[Chapter 06 - FastAPI Architecture]] — no global state, no service locator.
5. Configure lint and type-check for Python.

## Validation

- Server starts; `GET /health` returns a success response (observed via a real request).
- Type-check and lint pass with zero errors.
- The health router contains no logic beyond calling its service.
- All five layer directories exist.

## Definition of Done

`apps/api` starts locally, `/health` responds correctly through a router→service path, and lint plus type-check are clean. No database, no auth, no features.

---

## Navigation

- **Previous:** [[STEP-03 Web App Skeleton]]
- **Next:** [[STEP-05 Environment and Secrets]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Chapter 06 - FastAPI Architecture]] · [[Backend Architecture]]
