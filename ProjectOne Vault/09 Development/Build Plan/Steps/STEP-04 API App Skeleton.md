---
title: STEP-04 API App Skeleton
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, backend]
step_id: STEP-04
step_status: Done
---

# STEP-04 — API App Skeleton

**Status:** Done

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

## Outcome

FastAPI **0.121.2** on Python **3.14.6** at `apps/api`, with Pydantic 2.12.4, pydantic-settings, Uvicorn, and Ruff + mypy + pytest as dev tooling. `GET /health` returns `{"status":"ok","service":"ProjectOne API","version":"0.1.0","environment":"development"}` through `router → service`.

Decisions and notes for later steps:

- **`requires-python = ">=3.12"`, not `>=3.14`.** The local interpreter is 3.14.6 and every pin resolves on it, but the floor is set where the language features this codebase actually uses are available. Pinning the floor to the newest interpreter that happens to be installed would needlessly constrain CI images and deployment targets ([[STEP-06 Continuous Integration]], [[Infrastructure]]).
- **`disallow_any_explicit` is deliberately off in mypy.** `strict = true` is on, which already forbids implicit `Any`, untyped defs and bare generics. The explicit-Any flag was tried and rejected: Pydantic's `BaseModel` and `BaseSettings` use explicit `Any` in their own signatures, so it reports an error on *every model's class declaration* — code ProjectOne does not own. The reasoning is recorded in `pyproject.toml` so it is not silently re-enabled later.
- **Ruff enforces docstrings (`D`) and annotations (`ANN`).** This is what makes "explicit types on public APIs" ([[CLAUDE|CLAUDE.md]] §11) mechanical rather than a review convention. `tests/` is exempt from both.
- **`repositories/` is empty by design.** The structure is the deliverable; it gains contents when the database exists ([[STEP-07 Supabase Provisioning]]).
- **A dependency-injection seam exists at `app/core/dependencies.py`** rather than services being constructed inline. With one service it looks redundant — it is the override point tests use instead of monkey-patching, and the single readable place wiring accumulates.
- **OpenAPI already generates** at `/openapi.json` with `HealthResponse` as a named schema. This is the contract [[ADR-001 Technology Stack]] records as the future source for TypeScript type generation — no work is owed here yet, but the source now exists and is verified.
- **Tests exist despite not being required by this step's Validation.** Two: one exercising the service with no HTTP at all (proving business logic is framework-independent, [[CLAUDE|CLAUDE.md]] §18) and one through the app. They are the contract [[STEP-06 Continuous Integration]] will call.
- **The virtual environment lives at `apps/api/.venv/`** and is git-ignored by the existing STEP-01 Python rules — no `.gitignore` change was needed.

---

## Navigation

- **Previous:** [[STEP-03 Web App Skeleton]]
- **Next:** [[STEP-05 Environment and Secrets]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Chapter 06 - FastAPI Architecture]] · [[Backend Architecture]]
