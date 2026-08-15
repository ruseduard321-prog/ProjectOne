---
title: STEP-78 Scheduled Publishing
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, automation, backend]
step_id: STEP-78
step_status: Not Started
detail_level: outline
phase: "Automation and Collaboration"
---

# STEP-78 — Scheduled Publishing

**Status:** Not Started
**Phase:** Automation and Collaboration — Scheduled and triggered execution, richer notification delivery, and the workspace collaboration foundations that depend on it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let users schedule a publication for a future time.

## Why This Step Exists Now

[[Dashboard]] specifies upcoming publications as a component, and publishing consistency is one of [[Analytics]]' named metrics. Both presuppose scheduling.

## Dependencies

- [[STEP-74 Workflow Scheduling and Triggers]]

## Scope

- Schedule a publish for a future time.
- Timezone-correct handling.
- Dashboard upcoming-publications component.
- Cancel or reschedule before execution.
- Approval captured at scheduling time, with the scheduled action stated explicitly.

## Out of Scope

- No optimal-time recommendation.
- No recurring publication schedules.

## Surfaces Affected

**Backend:** scheduled publish jobs. **Database:** schedule records. **Frontend:** scheduling and dashboard surfaces.

## Required Tests and Proofs

- A scheduled publish fires at the right time across timezones.
- Cancellation before execution genuinely prevents it.
- A failed scheduled publish notifies rather than failing silently.
- Approval is recorded at scheduling time.

## Definition of Done

A user schedules a publication, sees it on the dashboard, can cancel it, and it publishes on time with approval recorded.

## Risks and Governance Gates

**Critical** — deferred irreversible external action. Approving now for something that happens later must be unambiguous about what was approved.

## Audit Gaps Closed

**Scheduled publication** — *Missing, P2, no step*; [[Dashboard]] upcoming publications

---

## Navigation

- **Previous:** [[STEP-77 Workspace and Collaboration Foundations]]
- **Next:** [[STEP-79 Domain Screen Blueprints]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
