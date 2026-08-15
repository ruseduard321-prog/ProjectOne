---
title: STEP-86 Private Beta Release
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, testing, security, infrastructure]
step_id: STEP-86
step_status: Not Started
detail_level: outline
phase: "Beta Readiness and Release"
---

# STEP-86 — Private Beta Release

**Status:** Not Started
**Phase:** Beta Readiness and Release — Observability, staging, recovery, security review, full verification of the beta surface, and the private invite-only free beta itself.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Release to a closed, invite-only group of real users, free of charge.

## Why This Step Exists Now

The owner's decided release strategy: the first usable release is a private, invite-only, free beta. **It is deliberately placed before billing**, corrected by owner decision on 2026-08-15 — a free beta needs no billing, and because steps execute in sequence, leaving billing ahead of it would have made billing a beta prerequisite in practice however the note was worded.

## Dependencies

- [[STEP-85 Full Product Verification and Hardening]]

## Scope

- Production deployment using the STEP-85 pipeline.
- Invite-only access control.
- Onboarding for invited users.
- Feedback capture.
- Monitoring and alerting watched actively through the release.
- A documented rollback decision point.

## Out of Scope

- No public sign-up.
- **No paid plans and no billing** — billing does not exist yet, by design. It is [[STEP-87 Billing Schema and Subscription Management]] onward.
- No marketing launch.

## Surfaces Affected

**Infrastructure:** production. **Backend:** invite gating. **Frontend:** onboarding.

## Required Tests and Proofs

- Invite gating cannot be bypassed, proven by attempting it.
- Onboarding completes for a genuinely new user.
- Monitoring and alerting are live and observed.
- Rollback remains available throughout.

## Definition of Done

Real invited users are using the product in production, with access gating proven, monitoring live, feedback captured and rollback available.

## Risks and Governance Gates

**Critical, and an owner decision** — whether to release is the owner's call, not an engineering outcome. [[Public Release Draft - Unscheduled]] material is folded in here.

## Audit Gaps Closed

First usable release — the invite-only free beta the owner specified

---

## Navigation

- **Previous:** [[STEP-85 Full Product Verification and Hardening]]
- **Next:** [[STEP-87 Billing Schema and Subscription Management]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
