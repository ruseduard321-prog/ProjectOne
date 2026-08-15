---
title: STEP-73 Analytics Agent
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, analytics, backend]
step_id: STEP-73
step_status: Not Started
detail_level: outline
phase: "Analytics and Optimization"
---

# STEP-73 — Analytics Agent

**Status:** Not Started
**Phase:** Analytics and Optimization — Event data first, then metrics, then the agents that reason over them.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Build the Analytics Agent to interpret performance data and explain what it means.

## Why This Step Exists Now

[[Agent Architecture]] specifies it and [[Analytics]] requires every recommendation to be explained. It arrives only now because an analytics agent without analytics data produces confident-sounding output with no evidence — precisely what [[CLAUDE|CLAUDE.md]] §15 forbids.

## Dependencies

- [[STEP-72 Analytics Metrics and Surfaces]]

## Scope

- An Analytics Agent reasoning over real metric history.
- Findings that cite the data supporting them.
- A measurable success criterion.
- Bounded cost per analysis.

## Out of Scope

- No strategy recommendations — the next step.
- No automatic action on findings.

## Surfaces Affected

**Backend:** analytics agent implementation.

## Required Tests and Proofs

- Findings cite the underlying data and the citation is checkable.
- The agent declines to conclude on insufficient data rather than inventing a trend.
- Cost is bounded per run.

## Definition of Done

An Analytics Agent produces evidence-cited findings over real metrics, declines honestly when data is insufficient, and stays within budget.

## Risks and Governance Gates

**Critical** — agent architecture. The specific hazard is fabricated insight: an agent that always finds a pattern is worse than none.

## Audit Gaps Closed

**Analytics Agent** — *Missing, P2, no step*; [[Analytics]] AI insights

---

## Navigation

- **Previous:** [[STEP-72 Analytics Metrics and Surfaces]]
- **Next:** [[STEP-74 Strategy Agent and Continuous Optimization]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
