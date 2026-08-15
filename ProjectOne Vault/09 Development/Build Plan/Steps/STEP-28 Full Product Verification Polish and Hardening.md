---
title: STEP-28 Full Product Verification, Polish and Hardening (Superseded — renumbered)
category: Development/Build Step
status: superseded
version: "2.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, superseded, history]
step_status: Superseded
detail_level: historical
superseded_by: "[[STEP-88 Full Product Verification and Hardening]]"
---

# STEP-28 Full Product Verification, Polish and Hardening (Superseded — renumbered)

> [!warning] Superseded — kept as history, binding on nothing
> This outline was replaced by owner decision on 2026-08-15, following the [[Product Coverage Audit]]. It is **not** an executable step and holds no status in the [[Build Plan]].
>
> **Successor:** [[STEP-88 Full Product Verification and Hardening]]

## Why This Was Superseded

This step was not cancelled — it **moved**, by owner decision on 2026-08-15, and is now [[STEP-88 Full Product Verification and Hardening]].

**Why it moved.** Its own goal is the reason: *verify the whole product, once, as a product.* At STEP-28 the assembled system was the Foundation loop; verifying there would have answered the question for a fraction of the product and left everything built afterwards unverified as a whole. Moving it to the end of the sequence is what makes its stated purpose achievable.

**Its scope carries forward and expands** to cover every domain built between: media generation, video assembly, publishing, analytics, memory, automation and billing, alongside the authentication, isolation, AI-governance, performance, accessibility and backup checks it always carried.

**Its defect policy carries forward unchanged** — small, bounded defects may be fixed inside the step; anything requiring new architecture becomes its own step rather than being improvised inside a verification pass.

Two concerns it previously carried are now **separate, earlier steps**, because the audit showed each was large enough to need its own: [[STEP-84 Observability and Alerting]] and [[STEP-85 Staging Environment and Deployment Pipeline]]. A dedicated [[STEP-87 Security Review and Penetration Testing]] now precedes it, so security findings have somewhere to land before final verification.

---

## What the Outline Said

The original outline is preserved below, unedited, so the earlier reasoning stays readable. **Nothing in it binds current work** — where it disagrees with the successor step, the successor wins.

<details>
<summary>Original outline (2026-08-14)</summary>


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

</details>

---

## Navigation

- **Parent:** [[Build Plan]]
- **Related Notes:** [[STEP-88 Full Product Verification and Hardening]] · [[Product Coverage Audit]]
