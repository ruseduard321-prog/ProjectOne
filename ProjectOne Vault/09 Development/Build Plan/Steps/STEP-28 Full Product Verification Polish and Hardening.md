---
title: STEP-28 Full Product Verification, Polish & Hardening
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-14
tags: [engineering, workflow, build-step, testing, security, quality]
step_id: STEP-28
step_status: Not Started
detail_level: outline
---

# STEP-28 — Full Product Verification, Polish & Hardening

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-27 Product-wide UI Rebuild]], per [[Execution Protocol]].

## Goal

Verify the whole product, once, as a product — not as twenty-eight steps that each passed their own checks. Every prior step validated its own change against its own Definition of Done; this step asks the different question: does the assembled system work, end to end, under realistic conditions?

## Scope

- **All primary user journeys** — end to end, as a user performs them rather than as endpoints respond.
- **Authentication and sessions** — sign-up, sign-in, refresh, expiry, sign-out, revocation.
- **Tenant isolation and RLS** — verified by attempting cross-tenant access, not by reading the policies.
- **Projects, workflows, approvals and chat** — the Foundation loop under real use.
- **AI success, failure, retry, budget and spend behaviour** — including the failure paths, which are the ones that stay untested until they matter ([[CLAUDE|CLAUDE.md]] §15a).
- **Database integrity** — constraints, transactions and migration state.
- **Responsive behaviour** — across the breakpoints [[STEP-26 Product Design System and Screen Blueprints]] defined.
- **Accessibility and keyboard navigation** — keyboard reachability, focus order, semantics and contrast.
- **Browser compatibility.**
- **Performance** — measured against the baselines recorded in [[STEP-25 Foundation Audit and Internal Readiness]].
- **Security and dependency checks** — including known-vulnerability scanning.
- **Logging and monitoring** — verified by confirming a failure is actually observable ([[CLAUDE|CLAUDE.md]] §26).
- **Backup and restore** — restore executed, not assumed ([[Backup and Disaster Recovery]]).
- **Production-like staging** — validated in an environment shaped like production ([[CLAUDE|CLAUDE.md]] §28a).
- **Manual exploratory and end-to-end testing** — deliberately unscripted, to find what the scripted checks were not written to look for.
- **Documentation accuracy** — the vault describes the product that now exists ([[CLAUDE|CLAUDE.md]] §19).

## Defect Policy

Binding, and stated here so the boundary is decided before defects are found rather than negotiated after:

- **Small, bounded defects may be fixed inside this step.** A defect is bounded when its cause is understood, its fix is local, and it introduces no new architecture.
- **Substantial defects receive additional numbered remediation steps after STEP-28.** A defect requiring schema change, architectural change, or broad rework is its own step by owner decision — not absorbed silently into this one, which is how a verification step becomes an unbounded rewrite.
- **No Critical or High defect may remain open before release consideration.** Lower-severity defects may be accepted with the owner's explicit, recorded decision.
- **Completing this step does not publish the product.** It produces a verified build and an honest defect record. Whether to release, and when, is the owner's decision — see [[#After This Step]].

## After This Step

**Public release is unscheduled and is deliberately not a numbered step in this plan.**

The prior plan ended at a numbered "First Public Release" step, which encoded an assumption that finishing the build meant shipping it. That assumption was withdrawn by owner decision on 2026-08-14. The earlier material is preserved, unnumbered and non-binding, as [[Public Release Draft - Unscheduled]] and may be reused when the release step is created.

A numbered public-release step will be created later, **using the next available number**, and only after the owner decides the application is ready.

## Prerequisites

- [[STEP-27 Product-wide UI Rebuild]] — `Done`

## Required Documentation

- [[Testing Strategy]]
- [[Security Architecture]]
- [[Backup and Disaster Recovery]]
- [[Deployment Strategy]]
- [[Chapter 10 - Testing Standards]]

## Tasks

Not yet expanded. [[STEP-27 Product-wide UI Rebuild]] writes this section, when the rebuilt product exists and the tasks can name real surfaces rather than imagined ones.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-27 Product-wide UI Rebuild]]
- **Next:** — (end of plan; public release is unscheduled — see [[Public Release Draft - Unscheduled]])
- **Parent:** [[Build Plan]]
