---
title: STEP-37 Notification Preferences
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-37
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-37 — Notification Preferences

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, notifications.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Let users choose what they are notified about and how.

## Why This Step Exists Now

[[Settings]] names Notifications as a core section, currently absent. A product that emails on every event without a control is one users learn to ignore.

## Dependencies

- [[STEP-36 Notification Delivery Channels]]
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

- **Previous:** [[STEP-36 Notification Delivery Channels]]
- **Next:** [[STEP-38 AI Capability Contract Expansion]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
