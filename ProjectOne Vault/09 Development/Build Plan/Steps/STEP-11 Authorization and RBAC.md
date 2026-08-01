---
title: STEP-11 Authorization and RBAC
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, security,backend]
step_id: STEP-11
step_status: Not Started
detail_level: outline
---

# STEP-11 — Authorization and RBAC

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-10 Authentication Backend]], per [[Execution Protocol]].

## Goal

Role-based access control layered above the RLS policies, so every action is validated against explicit permissions before execution.

## Scope

Includes the structural start of data ownership/export/delete mechanics per [[Privacy and Data Protection]] — retrofitting deletion is expensive ([[CLAUDE|CLAUDE.md]] §16). UI for it comes later.

## Prerequisites

- [[STEP-10 Authentication Backend]] — `Done`

## Required Documentation

- [[Authentication and Authorization]]
- [[Privacy and Data Protection]]
- [[RLS Policy Pattern]] — what the database already enforces, so RBAC does not duplicate it
- [[CLAUDE|CLAUDE.md]] §16

## Inherited from earlier steps

Recorded during synchronization, not expansion.

- **RLS enforces the workspace boundary; it does not distinguish roles.** [[STEP-09 Row Level Security Policies]] wrote policies that ask "is this requester a live member of the workspace", nothing finer. `workspace_members.role` exists and is constrained to `owner`/`admin`/`member`, but **no policy reads it** — an ordinary member can currently update the workspace row exactly like its owner.
- **This step owns closing that gap**, and must decide where: tightening the RLS policies to consult `role`, enforcing in the service layer above them, or both. Defence in depth argues for both ([[CLAUDE|CLAUDE.md]] §16); duplicating a rule in two places argues for care about which is authoritative.
- **Deletion is soft-only at the database layer.** No table has a DELETE policy, deliberately ([[RLS Policy Pattern#DELETE is granted to no one]]). The export/delete mechanics in this step's scope must work with `deleted_at`, not hard deletes.

## Tasks

Not yet expanded. [[STEP-10 Authentication Backend]] writes this section, when the surrounding code exists and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-10 Authentication Backend]]
- **Next:** [[STEP-12 API Conventions and Middleware]]
- **Parent:** [[Build Plan]]
