---
title: STEP-73 Strategy Agent and Continuous Optimization
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, analytics, backend]
step_id: STEP-73
step_status: Not Started
detail_level: outline
phase: "Analytics and Optimization"
---

# STEP-73 — Strategy Agent and Continuous Optimization

**Status:** Not Started
**Phase:** Analytics and Optimization — Event data first, then metrics, then the agents that reason over them.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Close [[Agent Architecture]]'s feedback loop: strategy recommendations that inform future planning.

## Why This Step Exists Now

This completes the target product loop and [[Product Bible]]'s Continuous Optimization pillar. It is last among the agents because it depends on analytics history, memory and the planning agent all existing.

## Dependencies

- [[STEP-72 Analytics Agent]]
- [[STEP-47 Memory Inspection and Control]]

## Scope

- A Strategy Agent producing recommendations from analytics findings and memory.
- The feedback edge into planning that [[Agent Architecture]] draws.
- Recommendations surfaced for user decision, never auto-applied.
- The chained-invocation cap enforced on the Strategy-to-Planning edge.

## Out of Scope

- No autonomous strategy execution.
- No cross-workspace learning — forbidden by [[CLAUDE|CLAUDE.md]] 16 without an ADR.

## Surfaces Affected

**Backend:** strategy agent, planning integration. **Frontend:** recommendation surface.

## Required Tests and Proofs

- The feedback edge respects the invocation cap and cannot loop.
- Recommendations are explained, per [[Analytics]]' design principle.
- No cross-workspace data informs any recommendation.
- The user decides — nothing is auto-applied.

## Definition of Done

A Strategy Agent produces explained recommendations from analytics and memory, feeding planning under user control and inside the invocation cap.

## Risks and Governance Gates

**Critical** — closes a feedback loop between agents, which is exactly the recursion 15a bounds. The cap from STEP-50 is what permits this step to exist.

## Audit Gaps Closed

**Strategy Agent** — *Missing, P3*; [[Product Bible]] Continuous Optimization pillar

---

## Navigation

- **Previous:** [[STEP-72 Analytics Agent]]
- **Next:** [[STEP-74 Workflow Scheduling and Triggers]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
