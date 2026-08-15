---
title: STEP-89 Billing UI and Invoices
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, billing, backend]
step_id: STEP-89
step_status: Not Started
detail_level: outline
phase: "Commercial Readiness"
---

# STEP-89 — Billing UI and Invoices

**Status:** Not Started
**Phase:** Commercial Readiness — Billing, plan enforcement and invoicing — after the free beta has proven the product, before any paid release.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Give users the billing surface [[Billing]] specifies.

## Why This Step Exists Now

[[Billing]]'s success criterion is that users always understand what they pay for, what they used and what happens next. That is a UI obligation as much as a backend one, and [[Settings]] names Billing as a core section.

## Dependencies

- [[STEP-88 Plan Limits and Quota Enforcement]]

## Scope

- Plan display, comparison and upgrade or downgrade flows.
- Invoice history and payment method management.
- Usage against limits with estimated upcoming charges.
- Cancellation — genuinely available, not buried ([[CLAUDE|CLAUDE.md]] 35 forbids dark patterns).
- Settings Billing section.

## Out of Scope

- No custom or enterprise plan negotiation.
- No dunning or collections flows.

## Surfaces Affected

**Frontend:** billing surfaces, Settings Billing section. **Backend:** billing read routes.

## Required Tests and Proofs

- Estimated charges match actual metering.
- Cancellation is reachable in a comparable number of steps to upgrading.
- No hidden cost is presented anywhere in the flow.
- All four async states render.

## Definition of Done

Users see plans, usage, invoices and estimated charges, can upgrade, downgrade and cancel without obstruction, with estimates matching real metering.

**This is the last step in the plan.** A public paid release remains a separate, unscheduled owner decision, and the step that performs it will be created when that decision is taken — with its own commercial-release verification covering the billing surface that [[STEP-85 Full Product Verification and Hardening]] deliberately excluded.

## Risks and Governance Gates

**Critical** — billing surface. [[CLAUDE|CLAUDE.md]] 35 forbids dark patterns and hidden pricing explicitly; a cancellation flow harder than an upgrade flow violates it.

## Audit Gaps Closed

[[Billing]] core capabilities; [[Settings]] Billing section

---

## Navigation

- **Previous:** [[STEP-88 Plan Limits and Quota Enforcement]]
- **Next:** —
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
