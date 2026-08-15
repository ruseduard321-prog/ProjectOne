---
title: STEP-33 Storage Quotas and Lifecycle
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-33
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-33 — Storage Quotas and Lifecycle

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Bound what a workspace can store, and define what happens to stored objects over time.

## Why This Step Exists Now

Storage is the second unbounded spend surface after AI. [[CLAUDE|CLAUDE.md]] 15a's reasoning about AI cost applies identically here, and [[Billing]] later needs a usage number that already exists.

## Dependencies

- [[STEP-28 Asset Upload and Download]]

## Scope

- Per-workspace storage accounting.
- A configurable ceiling, enforced at upload.
- Retention and cleanup rules for orphaned and soft-deleted objects.
- A clear, honest message when a ceiling is reached — never a silent failure.

## Out of Scope

- No plan-based limits — that is [[STEP-88 Plan Limits and Quota Enforcement]].
- No billing integration of any kind.

## Surfaces Affected

**Backend:** accounting service, enforcement at upload. **Database:** usage accounting. **Frontend:** usage display in settings.

## Required Tests and Proofs

- An upload exceeding the ceiling is refused with an actionable message.
- Accounting stays correct across delete and restore.
- Cleanup removes orphans without touching live objects.

## Definition of Done

Storage consumption is bounded per workspace, accounted accurately across the asset lifecycle, and communicated honestly when a ceiling is hit.

## Risks and Governance Gates

An accounting error that under-counts is an unbounded cost; one that over-counts blocks legitimate work. Both directions need tests.

## Audit Gaps Closed

[[Settings]] Storage section — *Missing, P2*; [[Billing]] storage usage — *Missing*

---

## Navigation

- **Previous:** [[STEP-32 Media Processing Pipeline]]
- **Next:** [[STEP-34 Notifications Domain]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
