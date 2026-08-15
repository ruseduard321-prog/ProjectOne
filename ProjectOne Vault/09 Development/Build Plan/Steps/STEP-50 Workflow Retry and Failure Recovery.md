---
title: STEP-50 Workflow Retry and Failure Recovery
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, workflow, backend]
step_id: STEP-50
step_status: Not Started
detail_level: outline
phase: "Workflow and Agent Infrastructure"
---

# STEP-50 — Workflow Retry and Failure Recovery

**Status:** Not Started
**Phase:** Workflow and Agent Infrastructure — The engine extensions and the agent-safety ceiling that must exist before agents can chain.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Give workflows bounded retry and clearer recovery semantics at the engine level.

## Why This Step Exists Now

[[Workflow Engine]] lists retries among its core capabilities. STEP-22 deliberately left workflow-level retry out because `AIRouter` owned AI retries; with async execution and multi-step media workflows, a transient failure in step seven should not require a manual resume.

## Dependencies

- [[STEP-49 Agent Invocation Safety Ceiling]]

## Scope

- Per-step retry policy with a hard ceiling, never unbounded ([[CLAUDE|CLAUDE.md]] 15a).
- Distinguishing retryable from terminal failures.
- Retry state persisted so it survives a worker restart.
- Interaction with the AI router's own ceiling stated explicitly, so the two do not silently multiply.

## Out of Scope

- No branching or conditional recovery paths.
- No automatic approval on retry — resuming is still not approving.

## Surfaces Affected

**Backend:** `app/workflows/runner.py`. **Database:** retry state on step runs.

## Required Tests and Proofs

- Retries stop at the ceiling and the run fails loudly.
- A terminal failure is not retried at all.
- Combined router and workflow ceilings are bounded and the bound is asserted.
- Retry state survives a worker restart.

## Definition of Done

Workflow steps retry within a hard ceiling, terminal failures fail immediately, and the combined retry bound across router and engine is explicit and tested.

## Risks and Governance Gates

**Critical** — AI/agent architecture and spend. Two retry layers multiplying is precisely the ceiling-nobody-wrote-down failure 15a warns about.

## Audit Gaps Closed

Automatic retries (workflow level) — *Intentionally Deferred* in the audit, now scheduled

---

## Navigation

- **Previous:** [[STEP-49 Agent Invocation Safety Ceiling]]
- **Next:** [[STEP-51 Workflow Branching]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
