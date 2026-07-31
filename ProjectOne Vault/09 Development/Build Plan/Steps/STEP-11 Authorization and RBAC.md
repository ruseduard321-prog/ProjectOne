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
- [[CLAUDE|CLAUDE.md]] §16

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
