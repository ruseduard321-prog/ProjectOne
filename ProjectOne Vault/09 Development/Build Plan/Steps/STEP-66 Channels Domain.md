---
title: STEP-66 Channels Domain
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, publishing, backend]
step_id: STEP-66
step_status: Not Started
detail_level: outline
phase: "Distribution"
---

# STEP-66 — Channels Domain

**Status:** Not Started
**Phase:** Distribution — Channels, connected accounts and the publishing path that turns finished content into published content.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Create the Channels domain — the destinations a workspace publishes to.

## Why This Step Exists Now

[[Database Architecture]] names Channels as a core domain with no schema, [[Memory System]] specifies a channel memory scope that has nothing to attach to, and [[AI Chat]]'s context awareness references connected channels. Publishing has no destination model without it.

## Dependencies

- [[STEP-65 Video Export and Delivery]]

## Scope

- Channel schema with RLS in the creating migration.
- Channel CRUD scoped to a workspace.
- Channel metadata — platform, handle, display name.
- Erasure registration.

## Out of Scope

- No OAuth or credential storage — [[STEP-67 Connected Accounts and OAuth]].
- No publishing.
- No channel memory population.

## Surfaces Affected

**Database:** channels table with RLS. **Backend:** repository, service, routes. **Frontend:** minimal management surface.

## Required Tests and Proofs

- Cross-tenant channel access is impossible through the route layer.
- Erasure removes channels with the workspace.
- Channel vocabulary is enumerated consistently between database and schema.

## Definition of Done

Channels exist as a tenant-scoped domain with RLS, CRUD and erasure coverage.

## Risks and Governance Gates

**Critical** — new tenant-scoped table and RLS.

## Audit Gaps Closed

**Channels domain** — *Missing, P1, no step*

---

## Navigation

- **Previous:** [[STEP-65 Video Export and Delivery]]
- **Next:** [[STEP-67 Connected Accounts and OAuth]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
