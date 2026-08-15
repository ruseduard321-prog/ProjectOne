---
title: STEP-69 Analytics Schema and Event Ingestion
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, analytics, backend]
step_id: STEP-69
step_status: Not Started
detail_level: outline
phase: "Analytics and Optimization"
---

# STEP-69 — Analytics Schema and Event Ingestion

**Status:** Not Started
**Phase:** Analytics and Optimization — Event data first, then metrics, then the agents that reason over them.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Create the analytics domain and start recording events.

## Why This Step Exists Now

[[Database Architecture]] names Analytics as a core domain with no schema. The audit is explicit that analytics built before publishing would measure only workflow runs and AI spend, both already visible elsewhere — so this arrives after there is published content to measure.

## Dependencies

- [[STEP-68 Publishing Agent and Multi-Platform Targeting]]

## Scope

- Analytics event schema with RLS in the creating migration.
- Internal event ingestion — workflow runs, generation costs, publishing outcomes.
- Retention policy, since event volume grows without bound otherwise.
- Erasure registration, including the 16 obligation that analytics logs are part of a deletion request.

## Out of Scope

- No platform metric ingestion — the next step.
- No metrics computation or surfaces.
- No AI insight.

## Surfaces Affected

**Database:** analytics events with RLS and retention. **Backend:** ingestion service.

## Required Tests and Proofs

- Events are tenant-scoped, proven through the route layer.
- Retention prunes without touching live data.
- Erasure removes analytics events for a deleted workspace — an explicit 16 requirement.
- Ingestion does not slow the request path.

## Definition of Done

Analytics events are recorded, tenant-scoped, retained under a stated policy and covered by erasure.

## Risks and Governance Gates

**Critical** — new tenant-scoped schema, RLS, retention and deletion obligations. Event volume is also a storage cost that must be bounded from the start.

## Audit Gaps Closed

**Analytics domain** — *Missing, P1, no step*

---

## Navigation

- **Previous:** [[STEP-68 Publishing Agent and Multi-Platform Targeting]]
- **Next:** [[STEP-70 Platform Metrics Ingestion]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
