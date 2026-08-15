---
title: STEP-75 Workflow Scheduling and Triggers
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, automation, backend]
step_id: STEP-75
step_status: Not Started
detail_level: outline
phase: "Automation"
---

# STEP-75 — Workflow Scheduling and Triggers

**Status:** Not Started
**Phase:** Automation — Scheduled and triggered execution, once there is something worth automating.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let workflows start on a schedule or in response to an event, rather than only on a click.

## Why This Step Exists Now

[[Workflow Engine]] names scheduling among its core capabilities and it is the last unbuilt one. It arrives now because a scheduler is only valuable once there are workflows worth running unattended.

## Dependencies

- [[STEP-74 Strategy Agent and Continuous Optimization]]

## Scope

- Scheduled workflow execution with a defined schedule vocabulary.
- Event-based triggers.
- Approval semantics for unattended runs — a gated step still stops and notifies rather than auto-approving.
- Schedule management UI.
- Bounded concurrency so a schedule cannot stampede.

## Out of Scope

- No user-authored workflow definitions.
- No visual automation builder.

## Surfaces Affected

**Backend:** scheduler, trigger evaluation. **Database:** schedule storage with RLS. **Frontend:** schedule management. **Infrastructure:** scheduler process.

## Required Tests and Proofs

- A scheduled run executes at its time and only once, proven against duplicate scheduler ticks.
- A gated step in an unattended run pauses and notifies rather than proceeding.
- Overlapping schedules do not stampede.
- Schedules are tenant-scoped.

## Definition of Done

Workflows run on schedules and triggers, unattended runs still respect approval gates, and concurrency is bounded.

## Risks and Governance Gates

**Critical** — unattended AI spend. A scheduled workflow that spends without a human present is exactly the case 15a's budget ceilings and breakers exist for.

## Audit Gaps Closed

**Workflow scheduling** — *Missing, P2, no step*

---

## Navigation

- **Previous:** [[STEP-74 Strategy Agent and Continuous Optimization]]
- **Next:** [[STEP-76 Scheduled Publishing]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
