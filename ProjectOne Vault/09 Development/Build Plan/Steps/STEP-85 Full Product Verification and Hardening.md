---
title: STEP-85 Full Product Verification and Hardening
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, testing, security, infrastructure]
step_id: STEP-85
step_status: Not Started
detail_level: outline
phase: "Beta Readiness and Release"
---

# STEP-85 — Full Product Verification and Hardening

**Status:** Not Started
**Phase:** Beta Readiness and Release — Observability, staging, recovery, security review, full verification of the beta surface, and the private invite-only free beta itself.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Verify the assembled **beta product surface** end to end, as a product rather than as sixty-odd steps that each passed their own checks.

## Why This Step Exists Now

This is the former STEP-28, moved to the end of the pre-release sequence by owner decision. Verifying at the old position would have verified a fraction of the product. Its question is unchanged: does the whole system work under realistic conditions?

**Its scope is the beta surface** — everything shipped to invited users. Billing is deliberately not in it, because billing is not in the beta; that verification belongs to the commercial release and is carried by [[STEP-87 Billing Schema and Subscription Management]] onward and by the public-release step that does not yet exist.

## Dependencies

- [[STEP-84 Security Review and Penetration Testing]]

## Scope

- Every primary user journey end to end, including the complete target product loop from idea to published analytics.
- Authentication, sessions, tenant isolation, projects, workflows, approvals, chat, memory, media, publishing, analytics and automation.
- AI success, failure, retry, budget and spend behaviour, including the failure paths.
- Performance measured against baselines; accessibility and keyboard navigation; browser compatibility; responsive behaviour.
- Backup and restore executed, not assumed.
- Documentation accuracy — the vault describes the product that now exists ([[CLAUDE|CLAUDE.md]] §19).
- Manual exploratory testing, deliberately unscripted.

## Out of Scope

- **Billing is out of scope**, because it is not part of the beta. It ships after the beta and carries its own verification.
- No new features. Bounded defect fixes only; anything requiring new architecture becomes its own step.

## Surfaces Affected

**All.**

## Required Tests and Proofs

- The full target product loop completes end to end in a production-like environment.
- Every failure path behaves as designed, including provider outage and budget exhaustion.
- Performance meets recorded baselines.
- Accessibility verified across the product.
- An honest defect record is produced with severities.

## Definition of Done

The beta product surface is verified end to end under realistic conditions, with an honest defect record, no unresolved Critical defects, and documentation matching the product that exists.

## Risks and Governance Gates

**Critical** — the last gate before real users. The defect policy is binding: bounded fixes land here, architectural ones become their own steps rather than being improvised.

## Audit Gaps Closed

Closes the verification obligation across every capability in this roadmap

---

## Navigation

- **Previous:** [[STEP-84 Security Review and Penetration Testing]]
- **Next:** [[STEP-86 Private Beta Release]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
