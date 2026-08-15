---
title: STEP-35 Notifications UI
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-35
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-35 — Notifications UI

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, notifications.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Surface notifications in the product, including the approval prompts that currently go unseen.

## Why This Step Exists Now

[[Dashboard]] specifies notifications and currently renders an honest *Not available yet* stub. The approval gate built in STEP-22 has never had a way to reach the user.

## Dependencies

- [[STEP-34 Notifications Domain]]
- [[STEP-26 Product Design System Foundation]]

## Scope

- Notification surface with unread indication.
- Dashboard integration replacing the stub.
- Actionable notifications linking to the thing that needs attention, approvals first.
- All four async states.

## Out of Scope

- No preferences UI.
- No real-time push transport — polling is acceptable here.

## Surfaces Affected

**Frontend:** notification components, dashboard integration. **Backend:** none.

## Required Tests and Proofs

- Unread count is accurate across read transitions.
- An approval notification routes to the waiting run.
- Accessibility: the notification region is announced correctly.

## Definition of Done

A user sees notifications in the product, can act on them, and the [[Dashboard]] stub is replaced by the real thing.

## Risks and Governance Gates

Closes a genuine UX gap where a paused workflow was invisible. Low architectural risk.

## Audit Gaps Closed

[[Dashboard]] notifications stub; **Approval notifications** — *Foundation / Partial, P1*

---

## Navigation

- **Previous:** [[STEP-34 Notifications Domain]]
- **Next:** [[STEP-36 Notification Delivery Channels]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
