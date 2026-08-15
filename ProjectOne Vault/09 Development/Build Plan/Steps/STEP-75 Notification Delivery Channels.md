---
title: STEP-75 Notification Delivery Channels
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, automation, backend]
step_id: STEP-75
step_status: Not Started
detail_level: outline
phase: "Automation and Collaboration"
---

# STEP-75 — Notification Delivery Channels

**Status:** Not Started
**Phase:** Automation and Collaboration — Scheduled and triggered execution, richer notification delivery, and the workspace collaboration foundations that depend on it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Deliver notifications outside the application, starting with email.

## Why This Step Exists Now

An approval that waits for the user to open the application is an approval that blocks a workflow overnight, so out-of-app delivery matters — but it **blocks nothing in AI capability, memory or the agent chain**, which is why it moved here by owner decision on 2026-08-15 rather than sitting in the early substrate. It lands beside the step that genuinely needs it: [[STEP-77 Workspace and Collaboration Foundations]] sends invitations by email.

## Dependencies

- [[STEP-34 Notifications Domain]]
- [[STEP-30 Async Job Infrastructure]]

## Scope

- An email delivery adapter behind a channel interface.
- Delivery as an async job with bounded retries.
- Delivery state recorded against the notification.
- Unsubscribe and compliance basics per [[Privacy and Data Protection]].

## Out of Scope

- No push notifications, no SMS.
- No preferences — the next step.

## Surfaces Affected

**Backend:** delivery adapters, job handlers. **Infrastructure:** email provider credentials. **Database:** delivery state.

## Required Tests and Proofs

- A failed send is retried within its ceiling and then recorded as failed, never silently dropped.
- No secret or personal data appears in delivery logs.
- Delivery is attributed to the right tenant.

## Definition of Done

A notification can be delivered by email, asynchronously, with bounded retries and honest failure recording.

## Risks and Governance Gates

**Critical** — external communication on the user's behalf and a new credential. Email content must not leak workspace data to the wrong address.

## Audit Gaps Closed

Notifications delivery — *Missing, P2*

---

## Navigation

- **Previous:** [[STEP-74 Workflow Scheduling and Triggers]]
- **Next:** [[STEP-76 Notification Preferences]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
