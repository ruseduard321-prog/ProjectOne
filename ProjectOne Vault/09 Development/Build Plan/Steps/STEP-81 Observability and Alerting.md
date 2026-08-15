---
title: STEP-81 Observability and Alerting
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, testing, security, infrastructure]
step_id: STEP-81
step_status: Not Started
detail_level: outline
phase: "Beta Readiness and Release"
---

# STEP-81 — Observability and Alerting

**Status:** Not Started
**Phase:** Beta Readiness and Release — Observability, staging, recovery, security review, full verification of the beta surface, and the private invite-only free beta itself.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Make the running system observable: metrics, dashboards and alerts.

## Why This Step Exists Now

The audit records structured logging as present but metrics and alerting as absent, and flags this as a release prerequisite. [[CLAUDE|CLAUDE.md]] 15a specifically requires near-real-time AI spend anomaly alerting, which has been a live obligation since STEP-18.

## Dependencies

- [[STEP-80 Product-wide UI Rebuild]]

## Scope

- Metrics collection across API, worker and AI paths.
- Dashboards for system health.
- Alerting on failure rates, latency and spend anomalies — the 15a requirement specifically.
- Alert routing to a human who can act.

## Out of Scope

- No user-facing status page.
- No incident management tooling.

## Surfaces Affected

**Infrastructure:** metrics, dashboards, alerting. **Backend:** instrumentation.

## Required Tests and Proofs

- A deliberately induced failure produces an alert, verified by inducing one ([[CLAUDE|CLAUDE.md]] 26).
- Spend anomaly alerting fires on a simulated spike.
- No secret or personal data appears in metrics or alerts.
- Alerts reach a human, proven end to end.

## Definition of Done

Failures and spend anomalies are detected and alerted to a human, verified by inducing them rather than by reading configuration.

## Risks and Governance Gates

**Critical** — infrastructure. A system that can fail unnoticed is the observability gap 26 names; this step closes it before real users arrive.

## Audit Gaps Closed

**Observability / monitoring / alerting** — *Foundation / Partial, P0 release prerequisite, no step*

---

## Navigation

- **Previous:** [[STEP-80 Product-wide UI Rebuild]]
- **Next:** [[STEP-82 Staging Environment and Deployment Pipeline]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
