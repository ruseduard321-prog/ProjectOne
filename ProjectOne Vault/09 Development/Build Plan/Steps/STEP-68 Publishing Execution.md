---
title: STEP-68 Publishing Execution
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, publishing, backend]
step_id: STEP-68
step_status: Not Started
detail_level: outline
phase: "Distribution"
---

# STEP-68 — Publishing Execution

**Status:** Not Started
**Phase:** Distribution — Channels, connected accounts and the publishing path that turns finished content into published content.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Publish a finished video to a connected channel.

## Why This Step Exists Now

`publishing` has existed as a project lifecycle state since STEP-20 with nothing performing it. This is the step that makes [[Product Bible]]'s Multi-Platform Publishing pillar real.

## Dependencies

- [[STEP-67 Connected Accounts and OAuth]]
- [[STEP-35 Notifications UI]]

## Scope

- Publish to one platform using its API.
- Publishing as a bounded async job with status reporting.
- Publish records: what was published, where, when, by whom.
- Approval required by default — publishing is externally visible and irreversible ([[CLAUDE|CLAUDE.md]] §15).
- Notification on completion or failure.
- Project lifecycle transition through `ProjectService`, never a direct status write.

## Out of Scope

- No scheduled publishing — [[STEP-76 Scheduled Publishing]].
- No multi-platform fan-out — [[STEP-69 Publishing Agent and Multi-Platform Targeting]].

## Surfaces Affected

**Backend:** publishing service, platform adapter, job handlers. **Database:** publish records with RLS. **Frontend:** publish surface with approval.

## Required Tests and Proofs

- Publishing without approval is impossible, proven by attempting it.
- A failed publish reports honestly and does not mark the project published.
- The lifecycle transition goes through `ProjectService` and refuses illegal transitions.
- Publish records are tenant-scoped.
- A duplicate publish request does not double-post.

## Definition of Done

An approved video publishes to a connected channel asynchronously, with an honest record, a notification, correct lifecycle transition and no unapproved external action.

## Risks and Governance Gates

**Critical** — the first genuinely irreversible external action the product takes on a user's behalf. Approval is not a UX preference here; it is the 15 requirement that makes the feature permissible.

## Audit Gaps Closed

**Publishing execution** — *Foundation / Partial, P1, no step*; [[Product Bible]] Multi-Platform Publishing pillar

---

## Navigation

- **Previous:** [[STEP-67 Connected Accounts and OAuth]]
- **Next:** [[STEP-69 Publishing Agent and Multi-Platform Targeting]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
