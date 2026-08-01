---
title: STEP-13 Auth, Users and Workspaces Endpoints
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, backend,api]
step_id: STEP-13
step_status: Not Started
detail_level: outline
---

# STEP-13 — Auth, Users and Workspaces Endpoints

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-12 API Conventions and Middleware]], per [[Execution Protocol]].

## Goal

The first real REST endpoints — authentication, user and workspace operations — built on the STEP-12 conventions.

## Scope

Each endpoint documented with [[API Endpoint Template]]. This is the contract the frontend consumes from STEP-16 onward.

## Prerequisites

- [[STEP-12 API Conventions and Middleware]] — `Done`

## Required Documentation

- [[API Architecture]]
- [[API Endpoint Template]]
- [[RLS Policy Pattern]] — what the database permits a client to do directly
- [[CLAUDE|CLAUDE.md]] §12/§14

## Inherited from earlier steps

Recorded during synchronization, not expansion.

> [!warning] Workspace creation cannot be a plain INSERT
> [[STEP-09 Row Level Security Policies]] made this structural. Creating a workspace requires two rows — the `workspaces` row and the creator's first `workspace_members` row — and the membership INSERT policy requires the caller to *already* be a member of that workspace. The creator is not, because the workspace did not exist a statement ago.
>
> This is deliberate, not an oversight: it forces workspace creation through an audited service path rather than letting a client assemble a tenant boundary row by row. **This step owns building that path.** Expect it to need a privileged, explicitly audited operation rather than the ordinary request-scoped connection — and see [[RLS Policy Pattern#What RLS Cannot Enforce]] before reaching for the service key, because using it casually would defeat every policy at once.

## Tasks

Not yet expanded. [[STEP-12 API Conventions and Middleware]] writes this section, when the surrounding code exists and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-12 API Conventions and Middleware]]
- **Next:** [[STEP-14 Design System Tokens]]
- **Parent:** [[Build Plan]]
