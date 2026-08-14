---
title: STEP-25 Foundation Audit & Internal Readiness
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-14
tags: [engineering, workflow, build-step, process, security, quality]
step_id: STEP-25
step_status: Not Started
detail_level: outline
---

# STEP-25 — Foundation Audit & Internal Readiness

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-24 Dashboard]], per [[Execution Protocol]].

## Goal

Establish what the Foundation build actually is, before anything is rebuilt on top of it. Every step from STEP-01 to STEP-24 shipped against its own Definition of Done; none of them audited the whole. This step is that audit: a single honest assessment of architecture, security, data integrity, cost controls, observability, performance and unfinished behaviour across the entire product.

## Scope

An audit produces **findings**, not fixes. Its output is a written, prioritised record of what is sound, what is weak, and what is missing — with severity assigned, so [[STEP-26 Product Design System and Screen Blueprints]] and [[STEP-27 Product-wide UI Rebuild]] are built on a known foundation rather than an assumed one.

Areas in scope, each assessed against the canonical document that governs it:

- **Architecture and technical debt** — where the shipped shape diverges from [[Backend Architecture]], [[Frontend Architecture]] and the [[Engineering Handbook MOC|Engineering Handbook]], and what that divergence costs.
- **Authentication and session handling** — token lifetime, refresh, revocation, and the session boundary as built.
- **Multi-tenancy and RLS** — every tenant-scoped table carries a policy, and no path bypasses it ([[CLAUDE|CLAUDE.md]] §16).
- **Database integrity and migrations** — constraint coverage, migration reversibility, and expand/contract compliance ([[CLAUDE|CLAUDE.md]] §13).
- **AI spend and provider failure controls** — budgets, circuit breakers, retry ceilings and fallback behaviour as actually implemented ([[CLAUDE|CLAUDE.md]] §15a, [[AI Cost Governance]]).
- **Security** — against [[Security Architecture]] and current OWASP guidance.
- **Backup and restore** — restore proven by execution, not by the existence of a backup ([[Backup and Disaster Recovery]]).
- **Observability** — whether a failure in each subsystem would actually be noticed.
- **Performance** — measured baselines for the primary journeys, not estimates.
- **Accessibility risks** — recorded as findings that feed STEP-26's accessibility rules.
- **Incomplete product behaviour** — every stub, deferred item and honest-placeholder shipped during Foundation, collected in one place.

### Findings carried in from earlier steps

Recorded where they were found, so the audit begins from what is already known rather than rediscovering it:

- **The root error boundary's retry does not retry.** `app/error.tsx` wires its button to `reset()` alone, which clears client state and re-renders the cached payload — the failure is still in it, so nothing recovers. [[STEP-24 Dashboard]] found this defect, fixed it in the four route boundaries it owns, and deliberately left the root boundary alone as another step's code ([[CLAUDE|CLAUDE.md]] §29/§35). It matters more than the others: it is the boundary [[STEP-16b Auth Refresh Outage Handling]] relies on for outage recovery, and its manual checklist recorded "a working retry control" against the same wiring now known to be inert. The fix is the existing `lib/error-recovery.ts`.

**Explicitly out of scope.** This step does **not** publish the application, does **not** deploy to production, and does **not** claim release readiness. Public release is unscheduled and is not a numbered step in this plan — see [[Public Release Draft - Unscheduled]]. Findings that require substantial remediation become their own numbered steps by owner decision; this step does not silently fix them.

## Prerequisites

- [[STEP-24 Dashboard]] — `Done`

## Required Documentation

- [[Security Architecture]]
- [[Database Architecture]]
- [[AI Cost Governance]]
- [[Backup and Disaster Recovery]]
- [[Compliance and Governance]]
- [[Testing Strategy]]

## Tasks

Not yet expanded. [[STEP-24 Dashboard]] writes this section, when the surrounding code exists and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-24 Dashboard]]
- **Next:** [[STEP-26 Product Design System and Screen Blueprints]]
- **Parent:** [[Build Plan]]
