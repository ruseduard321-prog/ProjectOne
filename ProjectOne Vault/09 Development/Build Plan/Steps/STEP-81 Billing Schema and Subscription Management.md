---
title: STEP-81 Billing Schema and Subscription Management
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, billing, backend]
step_id: STEP-81
step_status: Not Started
detail_level: outline
phase: "Commercial Readiness"
---

# STEP-81 — Billing Schema and Subscription Management

**Status:** Not Started
**Phase:** Commercial Readiness — Billing and plan enforcement, immediately before a paid release and not before.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Introduce the billing domain: plans, subscriptions and payment method handling.

## Why This Step Exists Now

Deliberately here and not earlier. The owner's release decision makes the first release a private, invite-only, free beta, for which billing is not a prerequisite. It enters before a commercial paid release, once core product value has been demonstrated — which by this point it has.

## Dependencies

- [[STEP-80 Product-wide UI Rebuild]]

## Scope

- Billing schema with RLS in the creating migration.
- Payment provider integration — the provider handles card data; ProjectOne never stores it.
- Plan definitions, subscription state and lifecycle.
- Webhook handling for provider events, with idempotency.
- Erasure and retention treatment for financial records, which have their own legal retention.

## Out of Scope

- No usage-based metering enforcement — the next step.
- No invoicing UI yet — [[STEP-83 Billing UI and Invoices]].

## Surfaces Affected

**Database:** billing tables with RLS. **Backend:** billing service, webhooks. **Infrastructure:** payment provider credentials.

## Required Tests and Proofs

- No card data reaches ProjectOne's storage or logs.
- Webhooks are idempotent under duplicate delivery.
- Subscription state transitions are correct and auditable.
- Billing records are tenant-scoped.
- Financial retention is treated as the documented exception to erasure it is ([[CLAUDE|CLAUDE.md]] §16).

## Definition of Done

Plans and subscriptions exist with payment handled entirely by the provider, idempotent webhooks, auditable state and correct retention treatment.

## Risks and Governance Gates

**Critical** — billing and payment logic, explicitly named in [[CLAUDE|CLAUDE.md]] §21. PCI scope is avoided by never touching card data, and that boundary must be provable.

## Audit Gaps Closed

**Billing domain** — *Missing, P1-for-paid-release, no step*

---

## Navigation

- **Previous:** [[STEP-80 Product-wide UI Rebuild]]
- **Next:** [[STEP-82 Plan Limits and Quota Enforcement]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
