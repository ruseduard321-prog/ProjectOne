---
title: STEP-30 Async Job Infrastructure
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-30
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-30 — Async Job Infrastructure

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, notifications.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Introduce a worker and queue so work can outlive the HTTP request that started it.

## Why This Step Exists Now

The audit's second-largest blocker: workflow runs currently execute synchronously inside the request, and a multi-minute render cannot. Every long-running capability in this roadmap depends on this step.

## Dependencies

- [[STEP-27 Storage Provider Abstraction]]

## Scope

- A queue and a worker process, deployed alongside the API.
- A job contract — enqueue, execute, record outcome — with at-least-once semantics stated explicitly.
- Idempotency expectations on handlers, since at-least-once means a handler will eventually run twice.
- Failure, retry ceiling and dead-letter handling, bounded per [[CLAUDE|CLAUDE.md]] §15a.
- Observability: a job's state is inspectable without attaching a debugger.

## Out of Scope

- No workflow engine integration — [[STEP-31 Workflow Async Execution]].
- No scheduling or cron — [[STEP-75 Workflow Scheduling and Triggers]].
- No new product feature.

## Surfaces Affected

**Backend:** `app/jobs/`, worker entrypoint. **Infrastructure:** queue service, worker deployment, CI coverage. **Database:** job state if the queue is database-backed.

## Required Tests and Proofs

- A job survives an API process restart.
- A handler that fails is retried up to its ceiling and then dead-lettered, not retried forever.
- Duplicate delivery does not duplicate effects, proven on a real handler.
- Tenant context is carried into the worker and enforced there.

## Definition of Done

A job can be enqueued, executed by a separate worker, retried within a bounded ceiling, dead-lettered on exhaustion, and observed throughout — with tenant scoping proven inside the worker.

## Risks and Governance Gates

**Critical** — infrastructure and a new execution context where RLS is easy to lose. A worker that runs without tenant context is a cross-tenant bug that no route test would catch.

## Audit Gaps Closed

**Background / async execution** — *Foundation / Partial, P0, no step*

---

## Navigation

- **Previous:** [[STEP-29 Asset Management UI]]
- **Next:** [[STEP-31 Workflow Async Execution]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
