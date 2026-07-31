---
title: Chapter 06 - FastAPI Architecture
category: Engineering Handbook
status: draft
version: "1.0"
last_updated: 2026-07-30
tags: [engineering, backend, architecture, documentation]
aliases: ["FastAPI Architecture", "Handbook Chapter 6"]
source_pdf: "[[12 Assets/PDF/ProjectOne_Engineering_Handbook_Chapter_06_FastAPI_Architecture_v1.0.pdf|ProjectOne_Engineering_Handbook_Chapter_06_FastAPI_Architecture_v1.0.pdf]]"
---

# ProjectOne Engineering Handbook

## Chapter 6 — FastAPI Architecture

### Objective

FastAPI is the backend framework. Keep routing thin, business logic in services and persistence isolated.

### Language

**Python is the backend language.** TypeScript is the frontend language and is not used in `apps/api`; Python is not used in the frontend. The split is deliberate and is recorded with its reasoning in [[ADR-001 Technology Stack]] — the AI ecosystem ProjectOne depends on (provider SDKs, evaluation and orchestration tooling) is strongest in Python, and the backend is placed where that ecosystem lives.

See [[CLAUDE|CLAUDE.md]] §10 for the full stack table. The specific Python version is settled by [[STEP-04 API App Skeleton]], not here.

### Routers

Routers validate input, call services and return responses only.

### Services

Services implement business rules and never depend on HTTP.

### Dependency Injection

Use FastAPI dependency injection consistently.

### Validation

Validate every external input using schemas.

### Summary

Backend remains modular, testable and scalable.

---

## Navigation

- **Previous:** [[Chapter 05 - NextJS Architecture]]
- **Next:** [[Chapter 07 - Database Standards]]
- **Parent:** [[Engineering Handbook MOC]]
- **Related Notes:** [[Backend Architecture]] · [[Chapter 07 - Database Standards]]
