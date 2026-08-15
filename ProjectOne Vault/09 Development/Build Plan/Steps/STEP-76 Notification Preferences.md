---
title: STEP-76 Notification Preferences
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, automation, backend]
step_id: STEP-76
step_status: Not Started
detail_level: outline
phase: "Automation and Collaboration"
---

# STEP-76 — Notification Preferences

**Status:** Not Started
**Phase:** Automation and Collaboration — Scheduled and triggered execution, richer notification delivery, and the workspace collaboration foundations that depend on it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let users choose what they are notified about and how.

## Why This Step Exists Now

[[Settings]] names Notifications as a core section, currently absent. A product that emails on every event without a control is one users learn to ignore — so preferences follow delivery immediately, and both sit here rather than in the early substrate because neither blocks any AI, memory or agent work.

## Dependencies

- [[STEP-75 Notification Delivery Channels]]
- [[STEP-26 Product Design System Foundation]]

## Scope

- Per-user, per-category, per-channel preferences.
- Sensible defaults that are honest about what they enable.
- Enforcement at send time, not at render time.
- Settings UI section.

## Out of Scope

- No digest or batching logic.
- No workspace-level notification policy.

## Surfaces Affected

**Backend:** preference storage and enforcement. **Database:** preferences with RLS. **Frontend:** Settings section.

## Required Tests and Proofs

- A disabled category is not delivered, proven at the send path.
- Defaults apply to a user who has never set a preference.
- Preferences are per-user and never leak across a workspace.

## Definition of Done

A user controls which notifications they receive and by which channel, enforced where sending happens.

## Risks and Governance Gates

**Critical** — new tenant-scoped table and RLS.

## Audit Gaps Closed

[[Settings]] Notifications section — *Missing, P2*

---

## Navigation

- **Previous:** [[STEP-75 Notification Delivery Channels]]
- **Next:** [[STEP-77 Workspace and Collaboration Foundations]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
