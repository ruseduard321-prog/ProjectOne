---
title: STEP-77 Workspace and Collaboration Foundations
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, automation, backend]
step_id: STEP-77
step_status: Not Started
detail_level: outline
phase: "Automation"
---

# STEP-77 — Workspace and Collaboration Foundations

**Status:** Not Started
**Phase:** Automation — Scheduled and triggered execution, once there is something worth automating.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Complete workspace management: switching, invitations and member administration.

## Why This Step Exists Now

The audit records multiple workspaces as schema-supported but UI-absent, with no switcher and no invitation flow. [[Product Bible]] names Collaboration as a pillar, and this is its foundation rather than its full expression.

## Dependencies

- [[STEP-76 Scheduled Publishing]]
- [[STEP-36 Notification Delivery Channels]]

## Scope

- Workspace switching in the application shell.
- Member invitations by email using the delivery channel from STEP-36.
- Member role administration through the existing RBAC model.
- Workspace settings completion in [[Settings]].

## Out of Scope

- No real-time collaborative editing.
- No presence indicators.
- No enterprise features — [[Roadmap]] Phase 3.

## Surfaces Affected

**Frontend:** workspace switcher, member management. **Backend:** invitation flow. **Database:** invitation records with RLS.

## Required Tests and Proofs

- Switching workspaces changes tenant context everywhere, proven across surfaces.
- An invitation cannot escalate privilege beyond the inviter's role.
- An expired or revoked invitation cannot be redeemed.
- Member removal follows the STEP-11a membership policy.

## Definition of Done

Users switch between workspaces, invite members by email and administer roles, with privilege escalation impossible and the existing membership policy respected.

## Risks and Governance Gates

**Critical** — authorization and tenant boundaries. Invitations are a classic privilege-escalation surface.

## Audit Gaps Closed

**Multiple workspaces per user** — *Foundation / Partial, P2*; [[Settings]] Workspace section; Collaboration pillar foundation

---

## Navigation

- **Previous:** [[STEP-76 Scheduled Publishing]]
- **Next:** [[STEP-78 Prompt Store and Versioning]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
