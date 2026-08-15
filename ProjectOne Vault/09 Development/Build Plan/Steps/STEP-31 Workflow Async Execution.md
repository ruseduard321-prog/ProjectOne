---
title: STEP-31 Workflow Async Execution
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-31
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-31 — Workflow Async Execution

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Move workflow runs off the request path and onto the worker, without changing what a run means.

## Why This Step Exists Now

STEP-22 built a runner that is deterministic, resumable and versioned but synchronous. Media workflows cannot run in a request, and the runner's existing persistence model already anticipates this.

## Dependencies

- [[STEP-30 Async Job Infrastructure]]

## Scope

- Starting a run enqueues it rather than executing it inline.
- The runner executes inside the worker, using the persistence it already has.
- Run status reporting for a run that has not finished.
- Approval and resume continue to work across the process boundary.
- Execution budgets and ceilings continue to apply unchanged.

## Out of Scope

- No branching, parallelism or scheduling.
- No new workflow type.

## Surfaces Affected

**Backend:** `app/workflows/runner.py`, routes, job handler. **Database:** none expected. **Frontend:** run status handling for in-flight runs.

## Required Tests and Proofs

- A run started via the API completes in the worker, proven by persisted state.
- An interrupted worker leaves a resumable run, as the synchronous runner already guarantees.
- An approval granted in one process releases a run executing in another.
- Ceilings still trip, and still fail loudly.

## Definition of Done

Workflow runs execute asynchronously with resumability, approvals and ceilings behaving exactly as they did synchronously, proven by the existing STEP-22 test suite plus new cross-process assertions.

## Risks and Governance Gates

**Critical** — AI/agent architecture and public API contract. The API's response shape changes from *finished* to *accepted*, which is a contract change clients must handle.

## Audit Gaps Closed

Background / async execution — *Foundation / Partial, P0*

---

## Navigation

- **Previous:** [[STEP-30 Async Job Infrastructure]]
- **Next:** [[STEP-32 Media Processing Pipeline]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
