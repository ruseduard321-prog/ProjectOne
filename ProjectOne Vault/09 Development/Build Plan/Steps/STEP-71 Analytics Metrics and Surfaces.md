---
title: STEP-71 Analytics Metrics and Surfaces
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, analytics, backend]
step_id: STEP-71
step_status: Not Started
detail_level: outline
phase: "Analytics and Optimization"
---

# STEP-71 — Analytics Metrics and Surfaces

**Status:** Not Started
**Phase:** Analytics and Optimization — Event data first, then metrics, then the agents that reason over them.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Compute the metrics [[Analytics]] specifies and present them in the product.

## Why This Step Exists Now

With events and platform data flowing, this is where the data becomes answers. [[Dashboard]] also specifies an analytics summary that currently cannot exist.

## Dependencies

- [[STEP-70 Platform Metrics Ingestion]]
- [[STEP-26 Product Design System Foundation]]

## Scope

- Metric computation — views, watch time, engagement, publishing consistency, AI cost, workflow duration.
- An analytics surface presenting them.
- Dashboard analytics summary replacing the current absence.
- Aggregation performance considered against realistic volume, per [[CLAUDE|CLAUDE.md]] 17.

## Out of Scope

- No AI insights or recommendations — the next step.
- No revenue or ROI estimation — [[STEP-71 Analytics Metrics and Surfaces]].

## Surfaces Affected

**Backend:** aggregation service. **Database:** aggregation indexes measured, not guessed. **Frontend:** analytics surfaces and dashboard integration.

## Required Tests and Proofs

- Metric computation is correct against fixtures.
- Aggregation performs acceptably at realistic volume, measured.
- All four async states render.
- Metrics never cross a tenant boundary.

## Definition of Done

The specified metrics are computed, presented in an analytics surface and summarised on the dashboard, performing acceptably at measured volume.

## Risks and Governance Gates

Performance is the real risk: aggregation over growing event tables is where indexes must be measured rather than speculated ([[CLAUDE|CLAUDE.md]] 13/17).

## Audit Gaps Closed

[[Analytics]] core metrics; [[Dashboard]] analytics summary

---

## Navigation

- **Previous:** [[STEP-70 Platform Metrics Ingestion]]
- **Next:** [[STEP-72 Analytics Agent]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
