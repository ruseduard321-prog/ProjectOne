---
title: STEP-50 Agent Invocation Safety Ceiling
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-50
step_status: Not Started
detail_level: outline
phase: "Workflow and Agent Infrastructure"
---

# STEP-50 — Agent Invocation Safety Ceiling

**Status:** Not Started
**Phase:** Workflow and Agent Infrastructure — The engine extensions and the agent-safety ceiling that must exist before agents can chain.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Hard-cap chained and recursive agent invocation before any agent can trigger another.

## Why This Step Exists Now

[[CLAUDE|CLAUDE.md]] §15a requires an explicit, low, hard-coded cap on chained or recursive agent invocation. No agent can currently trigger another, so no cap exists — which is correct today and a serious hazard the moment multi-agent work begins. This step must land **before** the first agent chain, not alongside it.

## Dependencies

- [[STEP-31 Workflow Async Execution]]

## Scope

- A hard, low ceiling on chained agent invocations per run, independent of and additional to retry limits.
- A recursion guard for an agent that can re-trigger itself.
- A tripped cap fails the run loudly and records which cap tripped.
- Cap state carried across the async boundary so a worker cannot reset it.

## Out of Scope

- No multi-agent workflow yet — this is the control, not the capability.
- No change to existing single-agent runs.

## Surfaces Affected

**Backend:** `app/workflows/`, `app/ai/governance.py`.

## Required Tests and Proofs

- A chain exceeding the cap fails loudly and names the cap.
- A self-retriggering agent is stopped by the recursion guard.
- The cap survives a process boundary and cannot be reset by re-enqueueing.
- Existing single-agent runs are unaffected.

## Definition of Done

Chained and recursive agent invocation is hard-capped, the cap survives async boundaries, and tripping it fails loudly — proven by test before any agent chain exists.

## Risks and Governance Gates

**Critical, and a 15a hard gate.** This is the step that prevents a runaway agent loop from becoming an unbounded bill. It is deliberately scheduled before the capability it constrains.

## Audit Gaps Closed

**Runaway agent protection (chained-invocation cap)** — *Foundation / Partial, P0, no step*

---

## Navigation

- **Previous:** [[STEP-49 Richer Chat Context]]
- **Next:** [[STEP-51 Workflow Retry and Failure Recovery]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
