---
title: STEP-89 Private Beta Release
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, testing, security, infrastructure]
step_id: STEP-89
step_status: Not Started
detail_level: outline
phase: "Verification and Release Hardening"
---

# STEP-89 — Private Beta Release

**Status:** Not Started
**Phase:** Verification and Release Hardening — Observability, staging, deployment, full-product verification and the beta itself.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Release to a closed, invite-only group of real users, free of charge.

## Why This Step Exists Now

The owner's decided release strategy: the first usable release is a private, invite-only, free beta. It is the step the [[Build Plan]] has never had, and it exists now because everything it depends on is verified.

## Dependencies

- [[STEP-88 Full Product Verification and Hardening]]

## Scope

- Production deployment using the STEP-85 pipeline.
- Invite-only access control.
- Onboarding for invited users.
- Feedback capture.
- Monitoring and alerting watched actively through the release.
- A documented rollback decision point.

## Out of Scope

- No public sign-up.
- No paid plans — billing exists but is not activated for beta users.
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

- **Previous:** [[STEP-88 Full Product Verification and Hardening]]
- **Next:** —
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
