---
title: STEP-71 Platform Metrics Ingestion
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, analytics, backend]
step_id: STEP-71
step_status: Not Started
detail_level: outline
phase: "Analytics and Optimization"
---

# STEP-71 — Platform Metrics Ingestion

**Status:** Not Started
**Phase:** Analytics and Optimization — Event data first, then metrics, then the agents that reason over them.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Pull performance data from connected platforms into the analytics store.

## Why This Step Exists Now

[[Analytics]]'s core metrics — views, watch time, engagement, subscribers — exist only on the platforms. Without ingestion, analytics can report what ProjectOne did but nothing about how it performed.

## Dependencies

- [[STEP-70 Analytics Schema and Event Ingestion]]

## Scope

- Scheduled metric pulls from connected platforms.
- Normalisation across platforms into one metric vocabulary.
- Rate-limit and quota handling per platform.
- Gap and failure handling — a missed pull is visible, not silently absent.

## Out of Scope

- No metric computation or presentation.
- No AI analysis.

## Surfaces Affected

**Backend:** ingestion adapters, scheduled jobs. **Database:** normalised metric storage.

## Required Tests and Proofs

- Normalisation is correct per platform against fixtures.
- Rate limits are respected and backoff is bounded.
- A failed pull is recorded as a gap rather than a zero.
- Metrics are tenant-scoped.

## Definition of Done

Platform metrics are ingested on a schedule, normalised, tenant-scoped, with gaps visible rather than silently rendered as zero.

## Risks and Governance Gates

**Critical** — external integration and tenant data. A zero that actually means *unknown* is a lie the whole analytics surface would inherit.

## Audit Gaps Closed

**Platform metrics** — *Missing, P2, no step*

---

## Navigation

- **Previous:** [[STEP-70 Analytics Schema and Event Ingestion]]
- **Next:** [[STEP-72 Analytics Metrics and Surfaces]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
