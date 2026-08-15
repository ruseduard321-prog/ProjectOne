---
title: STEP-34 Notifications Domain
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-34
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-34 — Notifications Domain

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, notifications.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Create the notification store and delivery path so the product can tell a user something happened.

## Why This Step Exists Now

[[Database Architecture]] names Notifications as a core domain with no schema. More concretely: a workflow that pauses for approval is currently invisible until someone happens to look, and async execution makes that worse.

## Dependencies

- [[STEP-30 Async Job Infrastructure]]

## Scope

- Notification schema with RLS in the same migration.
- A creation path callable from services and workers.
- In-app read/unread state.
- Registration with the erasure path.

## Out of Scope

- No email or push delivery — [[STEP-36 Notification Delivery Channels]].
- No per-user preferences — [[STEP-37 Notification Preferences]].
- No notification UI — [[STEP-35 Notifications UI]].

## Surfaces Affected

**Backend:** service, repository, routes. **Database:** notifications table with RLS. **Frontend:** none.

## Required Tests and Proofs

- Cross-tenant read is impossible through the route layer.
- A notification created from the worker carries the correct tenant.
- Erasure removes notifications with the workspace.

## Definition of Done

Notifications can be created from any service or worker, read only by their owner, and are removed by erasure — with RLS shipped in the creating migration.

## Risks and Governance Gates

**Critical** — new tenant-scoped table, RLS, erasure obligations.

## Audit Gaps Closed

**Notifications domain** — *Missing, P1, no step*

---

## Navigation

- **Previous:** [[STEP-33 Storage Quotas and Lifecycle]]
- **Next:** [[STEP-35 Notifications UI]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
